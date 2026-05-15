"""
=============================================================================
  Rotas de Gerenciamento de Solicitações de Manutenção
  Arquivo: manutencao.py 
=============================================================================
"""

from datetime import datetime, timedelta, timezone

from flask import Blueprint, abort, current_app, flash, jsonify, redirect, render_template, request, send_from_directory, url_for
from flask_login import current_user, login_required
from sqlalchemy import asc, desc, func, literal_column, or_, select, union_all
from sqlalchemy.orm import joinedload

from core.exceptions import RegraNegocioError
from core.extensions import db
from core.models import Anexo, Auditoria, ComentarioChamado, PerfilUsuario, SolicitacaoManutencao, Usuario
from core.services import GestaoService
from core.utils import perfil_requerido, salvar_arquivo, usuario_ativo_requerido


manutencao_bp = Blueprint('manutencao', __name__)


@manutencao_bp.route('/manutencao')
@login_required
@usuario_ativo_requerido
def lista():
    termo = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 10, type=int), 100)
    status_filtro = request.args.get('status', '')
    urgencia_filtro = request.args.get('urgencia', '')
    sort_col = request.args.get('sort', 'data')
    sort_dir = request.args.get('dir', 'desc')

    stmt = select(SolicitacaoManutencao).options(
        joinedload(SolicitacaoManutencao.solicitante),
        joinedload(SolicitacaoManutencao.responsavel)
    ).filter_by(ativo=True)

    if current_user.is_usuario: 
        stmt = stmt.filter_by(id_usuario=current_user.id)
        
    if termo: 
        stmt = stmt.where(or_(
            SolicitacaoManutencao.local.ilike(f"%{termo}%"), 
            SolicitacaoManutencao.descricao.ilike(f"%{termo}%")
        ))
        
    if status_filtro: 
        stmt = stmt.filter_by(status=status_filtro)
        
    if urgencia_filtro: 
        stmt = stmt.filter_by(urgencia=urgencia_filtro)

    ordem = desc if sort_dir == 'desc' else asc
    coluna = getattr(SolicitacaoManutencao, 'data_criacao' if sort_col == 'data' else sort_col, SolicitacaoManutencao.data_criacao)
    stmt = stmt.order_by(ordem(coluna))

    paginacao = db.paginate(stmt, page=page, per_page=per_page, error_out=False)

    ids_chamados = [c.id for c in paginacao.items]
    contagens = {}
    if ids_chamados:
        stmt_counts = select(ComentarioChamado.id_manutencao, func.count(ComentarioChamado.id)).where(
            ComentarioChamado.id_manutencao.in_(ids_chamados)
        ).group_by(ComentarioChamado.id_manutencao)
        resultados = db.session.execute(stmt_counts).all()
        contagens = {r[0]: r[1] for r in resultados}

    return render_template('manutencao.html', lista=paginacao, contagens=contagens, now=datetime.now(timezone.utc).replace(tzinfo=None), timedelta=timedelta)


@manutencao_bp.route('/manutencao/<int:cid>')
@login_required
@usuario_ativo_requerido
def detalhe(cid: int):
    chamado = db.one_or_404(
        select(SolicitacaoManutencao)
        .options(joinedload(SolicitacaoManutencao.solicitante), joinedload(SolicitacaoManutencao.responsavel))
        .filter_by(id=cid, ativo=True)
    )

    if current_user.is_usuario and chamado.id_usuario != current_user.id:
        abort(403)

    stmt_auditoria = select(
        literal_column("'auditoria'").label('tipo'),
        Auditoria.data_hora.label('data'),
        Usuario.nome.label('ator_nome'),
        Usuario.perfil.label('ator_perfil'),
        Auditoria.acao.label('info'),
        literal_column("NULL").label('extra')
    ).select_from(Auditoria).join(Usuario, Auditoria.id_ator == Usuario.id).filter(
        Auditoria.tabela_afetada == 'solicitacao_manutencao', Auditoria.registro_id == cid
    )

    stmt_comentarios = select(
        literal_column("'comentario'").label('tipo'),
        ComentarioChamado.data_hora.label('data'),
        Usuario.nome.label('ator_nome'),
        Usuario.perfil.label('ator_perfil'),
        ComentarioChamado.texto.label('info'),
        ComentarioChamado.caminho_anexo.label('extra')
    ).select_from(ComentarioChamado).join(Usuario, ComentarioChamado.id_usuario == Usuario.id).filter(
        ComentarioChamado.id_manutencao == cid
    )

    stmt_uniao = union_all(stmt_auditoria, stmt_comentarios).order_by(desc('data'))
    timeline = db.session.execute(stmt_uniao).mappings().all()
    anexos = db.session.scalars(select(Anexo).filter_by(id_chamado=cid)).all()

    return render_template('detalhe_chamado.html', chamado=chamado, timeline=timeline, anexos=anexos)


@manutencao_bp.route('/manutencao/novo', methods=['GET', 'POST'])
@login_required
@usuario_ativo_requerido
def novo():
    if request.method == 'POST':
        dados = {
            'local': request.form.get('local', '').strip(),
            'descricao': request.form.get('descricao', '').strip(),
            'urgencia': request.form.get('urgencia', 'baixa'),
            'arquivos': request.files.getlist('imagens')
        }
        
        try:
            GestaoService.criar_manutencao(current_user.id, dados)
            flash("Chamado de manutenção aberto com sucesso.", "success")
            return redirect(url_for('manutencao.lista'))
        except ValueError as e:
            flash(f"Erro no envio de arquivo: {e}", "danger")
        except RegraNegocioError as e:
            flash(str(e), "warning")
            
    return render_template('form_manutencao.html')


@manutencao_bp.route('/manutencao/<int:cid>/editar', methods=['GET', 'POST'])
@login_required
@usuario_ativo_requerido
def editar(cid: int):
    chamado = db.one_or_404(select(SolicitacaoManutencao).filter_by(id=cid, ativo=True))
    
    if current_user.is_usuario and chamado.id_usuario != current_user.id:
        abort(403)

    if chamado.status.value in ['concluido', 'cancelado']:
        flash("Chamados finalizados não podem ser alterados.", "warning")
        return redirect(url_for('manutencao.detalhe', cid=cid))

    if request.method == 'POST':
        dados = {
            'local': request.form.get('local', '').strip(),
            'descricao': request.form.get('descricao', '').strip(),
            'urgencia': request.form.get('urgencia', 'baixa')
        }
        
        try:
            GestaoService.editar_manutencao(chamado, dados, current_user.id)
            flash("Chamado atualizado com sucesso.", "success")
            return redirect(url_for('manutencao.lista'))
        except RegraNegocioError as e:
            flash(str(e), "warning")
            
    return render_template('form_manutencao.html', chamado=chamado, editando=True)


@manutencao_bp.route('/api/manutencao/sugestoes_local')
@login_required
@usuario_ativo_requerido
def api_sugestoes_local():
    termo = request.args.get('q', '').strip()
    
    if len(termo) < 2:
        return jsonify([])

    stmt = select(SolicitacaoManutencao.local).filter(
        SolicitacaoManutencao.ativo == True,
        SolicitacaoManutencao.local.ilike(f"%{termo}%")
    ).distinct().limit(10)

    resultados = db.session.scalars(stmt).all()
    return jsonify(resultados)


@manutencao_bp.route('/api/manutencao/<int:cid>/status', methods=['PATCH'])
@perfil_requerido(PerfilUsuario.ADMINISTRADOR, PerfilUsuario.GESTOR)
@usuario_ativo_requerido
def alterar_status(cid: int):
    dados = request.get_json()
    if not dados or 'novo_status' not in dados:
        return jsonify({'erro': 'Status não fornecido no corpo da requisição.'}), 400

    chamado = db.session.get(SolicitacaoManutencao, cid)
    if not chamado or not chamado.ativo:
        return jsonify({'erro': 'Chamado não encontrado.'}), 404

    try:
        GestaoService.alterar_status_manutencao(chamado, dados['novo_status'], current_user.id)
        return jsonify({'mensagem': 'Status atualizado com sucesso.'}), 200
    except RegraNegocioError as e:
        return jsonify({'erro': str(e)}), 400


@manutencao_bp.route('/api/manutencao/<int:cid>', methods=['DELETE'])
@login_required
@usuario_ativo_requerido
def excluir(cid: int):
    chamado = db.session.get(SolicitacaoManutencao, cid)
    if not chamado or not chamado.ativo:
        return jsonify({'erro': 'Chamado não encontrado.'}), 404
        
    if chamado.status.value.lower() != 'aberto':
        return jsonify({'erro': 'Acesso negado. Apenas chamados recém-abertos podem ser excluídos.'}), 403

    try:
        GestaoService.excluir_manutencao(cid, current_user.id)
        return '', 204
    except RegraNegocioError as e:
        return jsonify({'erro': str(e)}), 400
    except Exception as e:
        return jsonify({'erro': 'Erro interno ao processar a exclusão.'}), 500


@manutencao_bp.route('/manutencao/<int:cid>/comentar', methods=['POST'])
@login_required
@usuario_ativo_requerido
def comentar(cid: int):
    arquivo = request.files.get('anexo')
    try:
        caminho = salvar_arquivo(arquivo) if arquivo and arquivo.filename else None
    except ValueError as e:
        flash(str(e), "danger")
        return redirect(url_for('manutencao.detalhe', cid=cid))
        
    GestaoService.comentar_manutencao(cid, current_user.id, request.form.get('texto', ''), caminho)
    flash("Comentário registrado.", "success")
    return redirect(url_for('manutencao.detalhe', cid=cid))


@manutencao_bp.route('/uploads/<path:filename>')
@login_required
def serve_upload(filename: str):
    if GestaoService.verificar_permissao_acesso_arquivo(filename, current_user):
        return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)
    abort(403)