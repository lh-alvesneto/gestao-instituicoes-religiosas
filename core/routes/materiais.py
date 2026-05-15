"""
=============================================================================
  Rotas de Gerenciamento de Solicitações de Materiais
  Arquivo: materiais.py 
=============================================================================
"""

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import asc, desc, literal_column, or_, select, union_all
from sqlalchemy.orm import joinedload

from core.exceptions import RegraNegocioError
from core.extensions import db
from core.models import Auditoria, ComentarioChamado, PerfilUsuario, SolicitacaoMaterial, Usuario
from core.services import GestaoService
from core.utils import perfil_requerido, usuario_ativo_requerido


materiais_bp = Blueprint('materiais', __name__)


@materiais_bp.route('/materiais')
@login_required
@usuario_ativo_requerido
def lista():
    termo = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 10, type=int), 100)
    status_filtro = request.args.get('status', '')
    sort_col = request.args.get('sort', 'data')
    sort_dir = request.args.get('dir', 'desc')

    stmt = select(SolicitacaoMaterial).options(
        joinedload(SolicitacaoMaterial.solicitante),
        joinedload(SolicitacaoMaterial.responsavel)
    ).filter_by(ativo=True)

    if current_user.is_usuario:
        stmt = stmt.filter_by(id_usuario=current_user.id)
        
    if termo:
        stmt = stmt.where(or_(
            SolicitacaoMaterial.nome_material.ilike(f"%{termo}%"), 
            SolicitacaoMaterial.justificativa.ilike(f"%{termo}%")
        ))
        
    if status_filtro:
        stmt = stmt.filter_by(status=status_filtro)

    ordem = desc if sort_dir == 'desc' else asc
    coluna = getattr(SolicitacaoMaterial, 'data_criacao' if sort_col == 'data' else sort_col, SolicitacaoMaterial.data_criacao)
    stmt = stmt.order_by(ordem(coluna))

    paginacao = db.paginate(stmt, page=page, per_page=per_page, error_out=False)
    
    return render_template('materiais.html', lista=paginacao)


@materiais_bp.route('/materiais/<int:mid>')
@login_required
@usuario_ativo_requerido
def detalhe(mid: int):
    sol = db.one_or_404(
        select(SolicitacaoMaterial)
        .options(joinedload(SolicitacaoMaterial.solicitante), joinedload(SolicitacaoMaterial.responsavel))
        .filter_by(id=mid, ativo=True)
    )

    if current_user.is_usuario and sol.id_usuario != current_user.id:
        abort(403)

    stmt_auditoria = select(
        literal_column("'auditoria'").label('tipo'),
        Auditoria.data_hora.label('data'),
        Usuario.nome.label('ator_nome'),
        Usuario.perfil.label('ator_perfil'),
        Auditoria.acao.label('info')
    ).select_from(Auditoria).join(Usuario, Auditoria.id_ator == Usuario.id).filter(
        Auditoria.tabela_afetada == 'solicitacao_material', Auditoria.registro_id == mid
    )

    stmt_comentarios = select(
        literal_column("'comentario'").label('tipo'),
        ComentarioChamado.data_hora.label('data'),
        Usuario.nome.label('ator_nome'),
        Usuario.perfil.label('ator_perfil'),
        ComentarioChamado.texto.label('info')
    ).select_from(ComentarioChamado).join(Usuario, ComentarioChamado.id_usuario == Usuario.id).filter(
        ComentarioChamado.id_material == mid
    )

    stmt_uniao = union_all(stmt_auditoria, stmt_comentarios).order_by(desc('data'))
    timeline = db.session.execute(stmt_uniao).mappings().all()

    return render_template('detalhe_material.html', sol=sol, timeline=timeline)


@materiais_bp.route('/materiais/novo', methods=['GET', 'POST'])
@login_required
@usuario_ativo_requerido
def novo():
    if request.method == 'POST':
        dados = {
            'nome_material': request.form.get('nome_material', '').strip(),
            'quantidade': int(request.form.get('quantidade', 1)),
            'justificativa': request.form.get('justificativa', '').strip()
        }
        GestaoService.criar_material(current_user.id, dados)
        flash("Solicitação criada.", "success")
        return redirect(url_for('materiais.lista'))

    return render_template('form_material.html')


@materiais_bp.route('/materiais/<int:mid>/editar', methods=['GET', 'POST'])
@login_required
@usuario_ativo_requerido
def editar(mid: int):
    sol = db.one_or_404(select(SolicitacaoMaterial).filter_by(id=mid, ativo=True))
    
    if current_user.is_usuario and sol.id_usuario != current_user.id:
        abort(403)

    if sol.status.value in ['entregue', 'cancelado']:
        flash("Solicitações finalizadas não podem ser alteradas.", "warning")
        return redirect(url_for('materiais.detalhe', mid=mid))

    if request.method == 'POST':
        dados = {
            'nome_material': request.form.get('nome_material', '').strip(),
            'quantidade': int(request.form.get('quantidade', 1)),
            'justificativa': request.form.get('justificativa', '').strip(),
            'justificativa_edicao': request.form.get('justificativa_edicao', '').strip()
        }
        if not dados['justificativa_edicao']:
            flash("Forneça o motivo da edição.", 'warning')
            return render_template('form_material.html', sol=sol, editando=True)

        GestaoService.editar_material(sol, dados, current_user.id)
        flash("Solicitação atualizada com sucesso.", "success")
        return redirect(url_for('materiais.lista'))
            
    return render_template('form_material.html', sol=sol, editando=True)


@materiais_bp.route('/api/materiais/sugestoes')
@login_required
@usuario_ativo_requerido
def api_sugestoes_materiais():
    termo = request.args.get('q', '').strip()
    
    if len(termo) < 2:
        return jsonify([])

    stmt = select(SolicitacaoMaterial.nome_material).filter(
        SolicitacaoMaterial.ativo == True,
        SolicitacaoMaterial.nome_material.ilike(f"%{termo}%")
    ).distinct().limit(10)

    resultados = db.session.scalars(stmt).all()
    
    return jsonify(resultados)


@materiais_bp.route('/api/materiais/<int:mid>/status', methods=['PATCH'])
@perfil_requerido(PerfilUsuario.ADMINISTRADOR, PerfilUsuario.GESTOR)
@usuario_ativo_requerido
def alterar_status(mid: int):
    dados = request.get_json()
    if not dados or 'novo_status' not in dados:
        return jsonify({'erro': 'Status não fornecido.'}), 400

    sol = db.session.get(SolicitacaoMaterial, mid)
    if not sol or not sol.ativo:
        return jsonify({'erro': 'Solicitação não encontrada.'}), 404

    try:
        GestaoService.alterar_status_material(sol, dados['novo_status'], current_user.id)
        return jsonify({'mensagem': 'Status atualizado com sucesso.'}), 200
    except RegraNegocioError as e:
        return jsonify({'erro': str(e)}), 400


@materiais_bp.route('/api/materiais/<int:mid>', methods=['DELETE'])
@login_required
@usuario_ativo_requerido
def excluir(mid: int):
    sol = db.session.get(SolicitacaoMaterial, mid)
    if not sol or not sol.ativo:
        return jsonify({'erro': 'Solicitação não encontrada.'}), 404
        
    if sol.status.value.lower() != 'pendente':
        return jsonify({'erro': 'Acesso negado. Apenas solicitações pendentes podem ser excluídas.'}), 403

    try:
        GestaoService.excluir_material(mid, current_user.id)
        return '', 204
    except RegraNegocioError as e:
        return jsonify({'erro': str(e)}), 400
    except Exception:
        return jsonify({'erro': 'Erro interno ao tentar remover a solicitação.'}), 500


@materiais_bp.route('/materiais/<int:mid>/comentar', methods=['POST'])
@login_required
@usuario_ativo_requerido
def comentar(mid: int):
    texto = request.form.get('texto', '').strip()
    if texto:
        GestaoService.comentar_material(mid, current_user.id, texto)
        flash("Comentário adicionado.", "success")
        
    return redirect(url_for('materiais.detalhe', mid=mid))