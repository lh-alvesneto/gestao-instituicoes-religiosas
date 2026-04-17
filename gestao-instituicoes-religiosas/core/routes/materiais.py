from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user

from core.extensions import db
from core.models import SolicitacaoMaterial, ComentarioChamado, Usuario
from core.utils import usuario_ativo_requerido, perfil_requerido, log_auditoria

materiais_bp = Blueprint('materiais', __name__)

@materiais_bp.route('/materiais')
@login_required
@usuario_ativo_requerido
def lista():
    termo = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)

    query = SolicitacaoMaterial.query.filter_by(ativo=True)
    if current_user.is_usuario:
        query = query.filter_by(id_usuario=current_user.id)

    if termo:
        busca = f"%{termo}%"
        query = query.join(Usuario, SolicitacaoMaterial.id_usuario == Usuario.id).filter(
            db.or_(SolicitacaoMaterial.nome_material.ilike(busca), Usuario.nome.ilike(busca))
        )

    lista_paginada = query.order_by(SolicitacaoMaterial.data_criacao.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('materiais.html', lista=lista_paginada, termo=termo, per_page=per_page)

@materiais_bp.route('/materiais/novo', methods=['GET', 'POST'])
@login_required
@usuario_ativo_requerido
def novo():
    if request.method == 'POST':
        nome = request.form.get('nome_material', '').strip()
        qtd = request.form.get('quantidade', '').strip()
        just = request.form.get('justificativa', '').strip()

        if not all([nome, qtd, just]):
            flash('Preencha todos os campos.', 'warning')
        else:
            nova = SolicitacaoMaterial(
                id_usuario=current_user.id,
                nome_material=nome,
                quantidade=int(qtd),
                justificativa=just
            )
            db.session.add(nova)
            db.session.flush()
            log_auditoria('CRIOU', 'solicitacao_material', nova.id, {'material': nome, 'qtd': qtd})
            db.session.commit()
            flash('Solicitação enviada!', 'success')
            return redirect(url_for('materiais.lista'))
    return render_template('form_material.html')

@materiais_bp.route('/materiais/<int:mid>')
@login_required
@usuario_ativo_requerido
def detalhe(mid: int):
    sol = SolicitacaoMaterial.query.filter_by(id=mid, ativo=True).first_or_404()
    if current_user.is_usuario and sol.id_usuario != current_user.id:
        abort(403)
    comentarios = ComentarioChamado.query.filter_by(id_chamado=mid, tipo_chamado='material').order_by(ComentarioChamado.data_hora).all()
    return render_template('detalhe_material.html', sol=sol, comentarios=comentarios)

@materiais_bp.route('/materiais/<int:mid>/editar', methods=['GET', 'POST'])
@login_required
@usuario_ativo_requerido
def editar(mid: int):
    sol = SolicitacaoMaterial.query.filter_by(id=mid, ativo=True).first_or_404()
    if sol.status in ['aprovado', 'entregue', 'cancelado']:
        flash('Solicitações finalizadas não podem ser editadas.', 'warning')
        return redirect(url_for('materiais.detalhe', mid=mid))
    
    if current_user.is_usuario and (sol.id_usuario != current_user.id or sol.status != 'pendente'):
        abort(403)

    if request.method == 'POST':
        just_edicao = request.form.get('justificativa_edicao', '').strip()
        if current_user.pode_gerenciar and not just_edicao:
            flash('Gestores devem informar a justificativa da edição.', 'warning')
            return render_template('form_material.html', sol=sol, editando=True)

        antes = {'nome': sol.nome_material, 'qtd': sol.quantidade}
        sol.nome_material = request.form.get('nome_material', sol.nome_material).strip()
        sol.quantidade = int(request.form.get('quantidade', sol.quantidade))
        sol.justificativa = request.form.get('justificativa', sol.justificativa).strip()

        log_auditoria('EDITOU', 'solicitacao_material', sol.id, {
            'antes': antes, 'depois': {'nome': sol.nome_material, 'qtd': sol.quantidade},
            'justificativa': just_edicao or 'N/A'
        })
        db.session.commit()
        flash('Solicitação atualizada.', 'success')
        return redirect(url_for('materiais.lista'))
    return render_template('form_material.html', sol=sol, editando=True)

@materiais_bp.route('/materiais/<int:mid>/status/<novo_status>')
@perfil_requerido('administrador', 'gestor')
@usuario_ativo_requerido
def alterar_status(mid: int, novo_status: str):
    sol = SolicitacaoMaterial.query.filter_by(id=mid, ativo=True).first_or_404()
    status_ant = sol.status
    sol.status = novo_status
    sol.id_admin_responsavel = current_user.id
    log_auditoria('STATUS', 'solicitacao_material', sol.id, {'de': status_ant, 'para': novo_status})
    db.session.commit()
    flash(f'Status atualizado para {novo_status}.', 'success')
    return redirect(url_for('materiais.lista'))

@materiais_bp.route('/materiais/<int:mid>/comentar', methods=['POST'])
@login_required
@usuario_ativo_requerido
def comentar(mid: int):
    texto = request.form.get('texto', '').strip()
    if texto:
        db.session.add(ComentarioChamado(id_chamado=mid, tipo_chamado='material', id_usuario=current_user.id, texto=texto))
        db.session.commit()
        flash('Comentário adicionado.', 'success')
    return redirect(url_for('materiais.detalhe', mid=mid))

@materiais_bp.route('/materiais/<int:mid>/excluir', methods=['POST'])
@login_required
@usuario_ativo_requerido
def excluir(mid: int):
    sol = SolicitacaoMaterial.query.filter_by(id=mid, ativo=True).first_or_404()
    if current_user.is_usuario and (sol.id_usuario != current_user.id or sol.status != 'pendente'):
        abort(403)
    sol.ativo = False
    log_auditoria('EXCLUIU', 'solicitacao_material', sol.id, {'material': sol.nome_material})
    db.session.commit()
    flash('Solicitação removida.', 'danger')
    return redirect(url_for('materiais.lista'))