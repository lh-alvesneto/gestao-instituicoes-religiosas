from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload

from core.extensions import db
from core.models import SolicitacaoMaterial, ComentarioChamado, Usuario
from core.utils import usuario_ativo_requerido, perfil_requerido, log_auditoria
from core.services import GestaoService

materiais_bp = Blueprint('materiais', __name__)

@materiais_bp.route('/materiais')
@login_required
@usuario_ativo_requerido
def lista():
    termo = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    # Proteção contra manipulação de paginação (DoS)
    per_page = min(request.args.get('per_page', 10, type=int), 100)

    # Otimização N+1 com joinedload
    query = SolicitacaoMaterial.query.options(
        joinedload(SolicitacaoMaterial.solicitante),
        joinedload(SolicitacaoMaterial.responsavel)
    ).filter_by(ativo=True)

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
            try:
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
            except Exception as e:
                db.session.rollback()
                flash('Erro interno ao guardar a solicitação.', 'danger')
                
    return render_template('form_material.html')

@materiais_bp.route('/materiais/<int:mid>')
@login_required
@usuario_ativo_requerido
def detalhe(mid: int):
    sol = SolicitacaoMaterial.query.filter_by(id=mid, ativo=True).first_or_404()
    
    if current_user.is_usuario and sol.id_usuario != current_user.id:
        abort(403)
        
    # Correção: Consulta agora usa as novas chaves estrangeiras (id_material)
    comentarios = ComentarioChamado.query.filter_by(id_material=mid).order_by(ComentarioChamado.data_hora).all()
    return render_template('detalhe_material.html', sol=sol, timeline=comentarios)

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

        try:
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
        except Exception:
            db.session.rollback()
            flash('Erro ao atualizar a solicitação.', 'danger')
            
    return render_template('form_material.html', sol=sol, editando=True)

@materiais_bp.route('/materiais/<int:mid>/status/<novo_status>')
@perfil_requerido('administrador', 'gestor')
@usuario_ativo_requerido
def alterar_status(mid: int, novo_status: str):
    sol = SolicitacaoMaterial.query.filter_by(id=mid, ativo=True).first_or_404()
    
    try:
        sucesso = GestaoService.alterar_status_material(sol, novo_status, current_user.id)
        if sucesso:
            flash(f'Status atualizado para {novo_status}.', 'success')
        else:
            flash('Erro ao atualizar o status.', 'danger')
    except ValueError:
        abort(400) # Se alguém tentar forçar um status malicioso na URL
        
    return redirect(url_for('materiais.lista'))

@materiais_bp.route('/materiais/<int:mid>/comentar', methods=['POST'])
@login_required
@usuario_ativo_requerido
def comentar(mid: int):
    texto = request.form.get('texto', '').strip()
    if texto:
        sucesso = GestaoService.comentar_material(mid, current_user.id, texto)
        if sucesso:
            flash('Comentário adicionado.', 'success')
        else:
            flash('Erro ao gravar o comentário.', 'danger')
            
    return redirect(url_for('materiais.detalhe', mid=mid))

@materiais_bp.route('/materiais/<int:mid>/excluir', methods=['POST'])
@login_required
@usuario_ativo_requerido
def excluir(mid: int):
    sol = SolicitacaoMaterial.query.filter_by(id=mid, ativo=True).first_or_404()
    if current_user.is_usuario and (sol.id_usuario != current_user.id or sol.status != 'pendente'):
        abort(403)
        
    try:
        sol.ativo = False
        log_auditoria('EXCLUIU', 'solicitacao_material', sol.id, {'material': sol.nome_material})
        db.session.commit()
        flash('Solicitação removida.', 'danger')
    except Exception:
        db.session.rollback()
        flash('Erro ao tentar remover a solicitação.', 'danger')
        
    return redirect(url_for('materiais.lista'))