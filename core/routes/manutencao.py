import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, send_from_directory, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from sqlalchemy.orm import joinedload

from core.extensions import db
from core.models import SolicitacaoManutencao, ComentarioChamado, Auditoria, Anexo, Usuario
from core.utils import usuario_ativo_requerido, perfil_requerido, log_auditoria, salvar_arquivo
from core.services import GestaoService

manutencao_bp = Blueprint('manutencao', __name__)

@manutencao_bp.route('/manutencao')
@login_required
@usuario_ativo_requerido
def lista():
    termo = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    # Proteção contra manipulação de paginação (DoS)
    per_page = min(request.args.get('per_page', 10, type=int), 100)

    # Otimização N+1 com joinedload
    query = SolicitacaoManutencao.query.options(
        joinedload(SolicitacaoManutencao.solicitante),
        joinedload(SolicitacaoManutencao.responsavel)
    ).filter_by(ativo=True)
    
    if current_user.is_usuario:
        query = query.filter_by(id_usuario=current_user.id)

    if termo:
        busca = f"%{termo}%"
        query = query.join(Usuario, SolicitacaoManutencao.id_usuario == Usuario.id).filter(
            db.or_(SolicitacaoManutencao.local.ilike(busca), SolicitacaoManutencao.descricao.ilike(busca), Usuario.nome.ilike(busca))
        )

    lista_paginada = query.order_by(SolicitacaoManutencao.data_criacao.desc()).paginate(page=page, per_page=per_page, error_out=False)
    return render_template('manutencao.html', lista=lista_paginada, termo=termo, per_page=per_page)

@manutencao_bp.route('/manutencao/novo', methods=['GET', 'POST'])
@login_required
@usuario_ativo_requerido
def novo():
    if request.method == 'POST':
        local = request.form.get('local', '').strip()
        desc = request.form.get('descricao', '').strip()
        urgencia = request.form.get('urgencia', 'media')
        files = request.files.getlist('imagens')

        if not all([local, desc]):
            flash('Preencha os campos obrigatórios.', 'warning')
        else:
            try:
                novo_c = SolicitacaoManutencao(id_usuario=current_user.id, local=local, descricao=desc, urgencia=urgencia)
                db.session.add(novo_c)
                db.session.flush()

                for f in [f for f in files if f and f.filename]:
                    nome_salvo = salvar_arquivo(f)
                    db.session.add(Anexo(id_chamado=novo_c.id, caminho_arquivo=nome_salvo, nome_original=f.filename))

                db.session.commit()
                flash('Chamado aberto!', 'success')
                return redirect(url_for('manutencao.lista'))
            except Exception as e:
                db.session.rollback()
                flash('Erro interno ao guardar o chamado.', 'danger')
                
    return render_template('form_manutencao.html')

@manutencao_bp.route('/manutencao/<int:cid>')
@login_required
@usuario_ativo_requerido
def detalhe(cid: int):
    chamado = SolicitacaoManutencao.query.filter_by(id=cid, ativo=True).first_or_404()
    if current_user.is_usuario and chamado.id_usuario != current_user.id:
        abort(403)

    # Correção do modelo: Usar id_manutencao
    comentarios = ComentarioChamado.query.filter_by(id_manutencao=cid).all()
    auditorias = Auditoria.query.filter_by(tabela_afetada='solicitacao_manutencao', registro_id=cid).all()
    
    timeline = sorted(comentarios + auditorias, key=lambda x: x.data_hora)
    return render_template('detalhe_chamado.html', chamado=chamado, timeline=timeline, anexos=chamado.anexos.all())

@manutencao_bp.route('/manutencao/<int:cid>/editar', methods=['GET', 'POST'])
@login_required
@usuario_ativo_requerido
def editar(cid: int):
    chamado = SolicitacaoManutencao.query.filter_by(id=cid, ativo=True).first_or_404()
    
    if chamado.status in ['em_andamento', 'concluido', 'cancelado']:
        flash('Chamados finalizados não podem ser editados.', 'warning')
        return redirect(url_for('manutencao.detalhe', cid=cid))
    
    if current_user.is_usuario and (chamado.id_usuario != current_user.id or chamado.status != 'aberto'):
        abort(403)
        
    if request.method == 'POST':
        try:
            chamado.local = request.form.get('local', chamado.local).strip()
            chamado.descricao = request.form.get('descricao', chamado.descricao).strip()
            chamado.urgencia = request.form.get('urgencia', chamado.urgencia)
            
            log_auditoria('EDITOU', 'solicitacao_manutencao', chamado.id, {
                'local': chamado.local, 'urgencia': chamado.urgencia
            })
            db.session.commit()
            flash('Chamado atualizado com sucesso.', 'success')
            return redirect(url_for('manutencao.lista'))
        except Exception:
            db.session.rollback()
            flash('Erro ao atualizar o chamado.', 'danger')
            
    return render_template('form_manutencao.html', chamado=chamado, editando=True)

@manutencao_bp.route('/manutencao/<int:cid>/status/<novo_status>')
@perfil_requerido('administrador', 'gestor')
@usuario_ativo_requerido
def alterar_status(cid: int, novo_status: str):
    chamado = SolicitacaoManutencao.query.filter_by(id=cid, ativo=True).first_or_404()
    
    try:
        sucesso = GestaoService.alterar_status_manutencao(chamado, novo_status, current_user.id)
        if sucesso:
            flash('Status atualizado com sucesso.', 'success')
        else:
            flash('Erro ao atualizar o status.', 'danger')
    except ValueError:
        abort(400) # Se alguém tentar forçar um status malicioso na URL
        
    return redirect(url_for('manutencao.lista'))

@manutencao_bp.route('/manutencao/<int:cid>/comentar', methods=['POST'])
@login_required
@usuario_ativo_requerido
def comentar(cid: int):
    texto = request.form.get('texto', '').strip()
    arquivo = request.files.get('anexo')
    
    try:
        nome_salvo = salvar_arquivo(arquivo) if arquivo and arquivo.filename else None
        sucesso = GestaoService.comentar_manutencao(cid, current_user.id, texto, nome_salvo)
        if sucesso:
            flash('Comentário registado.', 'success')
        else:
            flash('Erro ao gravar o comentário.', 'danger')
    except ValueError as e:
        flash(str(e), 'danger') # Ex: Extensão não permitida
        
    return redirect(url_for('manutencao.detalhe', cid=cid))

@manutencao_bp.route('/manutencao/<int:cid>/excluir', methods=['POST'])
@login_required
@usuario_ativo_requerido
def excluir(cid: int):
    chamado = SolicitacaoManutencao.query.filter_by(id=cid, ativo=True).first_or_404()
    if current_user.is_usuario and (chamado.id_usuario != current_user.id or chamado.status != 'aberto'):
        abort(403)
        
    try:
        chamado.ativo = False
        log_auditoria('EXCLUIU', 'solicitacao_manutencao', chamado.id, {'local': chamado.local})
        db.session.commit()
        flash('Chamado removido.', 'danger')
    except Exception:
        db.session.rollback()
        flash('Erro ao tentar remover o chamado.', 'danger')
        
    return redirect(url_for('manutencao.lista'))

@manutencao_bp.route('/uploads/<path:filename>')
@login_required
@usuario_ativo_requerido
def serve_upload(filename: str):
    safe_name = secure_filename(filename)
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], safe_name)