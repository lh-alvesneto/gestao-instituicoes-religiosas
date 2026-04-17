from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import current_user

from core.extensions import db
from core.models import Usuario, Auditoria
from core.utils import usuario_ativo_requerido, perfil_requerido, log_auditoria

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/usuarios')
@perfil_requerido('administrador', 'gestor')
@usuario_ativo_requerido
def lista_usuarios():
    termo = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)

    query = Usuario.query.filter_by(ativo=True)

    if not current_user.is_admin:
        query = query.filter_by(criado_por_id=current_user.id)

    if termo:
        busca_formatada = f"%{termo}%"
        query = query.filter(db.or_(Usuario.nome.ilike(busca_formatada), Usuario.email.ilike(busca_formatada)))

    usuarios_paginados = query.order_by(Usuario.nome).paginate(page=page, per_page=per_page, error_out=False)

    return render_template('usuarios.html', usuarios=usuarios_paginados, termo=termo, per_page=per_page)


@admin_bp.route('/usuarios/novo', methods=['GET', 'POST'])
@perfil_requerido('administrador', 'gestor')
@usuario_ativo_requerido
def novo_usuario():
    perfis_disponiveis = ['administrador', 'gestor', 'usuario'] if current_user.is_admin else ['usuario']

    if request.method == 'POST':
        nome   = request.form.get('nome', '').strip()
        email  = request.form.get('email', '').strip().lower()
        senha  = request.form.get('senha', '')
        perfil = request.form.get('perfil', 'usuario')

        if not current_user.is_admin and perfil != 'usuario':
            flash('Você não tem permissão para criar este perfil.', 'danger')
            return redirect(url_for('admin.novo_usuario'))

        if not all([nome, email, senha]):
            flash('Preencha todos os campos obrigatórios.', 'warning')
        elif Usuario.query.filter_by(email=email).first():
            flash('Este e-mail já está cadastrado no sistema.', 'danger')
        else:
            novo = Usuario(nome=nome, email=email, perfil=perfil, criado_por_id=current_user.id)
            novo.set_senha(senha)
            db.session.add(novo)
            db.session.flush()

            log_auditoria('CRIOU', 'usuario', novo.id, {
                'nome': nome, 'email': email, 'perfil': perfil, 'criado_por': current_user.email
            })
            db.session.commit()
            flash(f'Usuário "{nome}" criado com sucesso.', 'success')
            return redirect(url_for('admin.lista_usuarios'))

    return render_template('form_usuario.html', perfis=perfis_disponiveis)


@admin_bp.route('/usuarios/<int:uid>/inativar', methods=['POST'])
@perfil_requerido('administrador', 'gestor')
@usuario_ativo_requerido
def inativar_usuario(uid: int):
    alvo = Usuario.query.get_or_404(uid)

    if alvo.id == current_user.id:
        flash('Você não pode inativar sua própria conta.', 'warning')
        return redirect(url_for('admin.lista_usuarios'))

    if current_user.is_gestor and alvo.criado_por_id != current_user.id:
        abort(403)

    if alvo.is_admin and not current_user.is_admin:
        abort(403)

    alvo.ativo = False
    log_auditoria('EXCLUIU', 'usuario', alvo.id, {'email': alvo.email, 'perfil': alvo.perfil, 'inativado_por': current_user.email})
    db.session.commit()
    flash(f'Usuário "{alvo.nome}" foi inativado.', 'warning')
    return redirect(url_for('admin.lista_usuarios'))


@admin_bp.route('/auditoria')
@perfil_requerido('administrador')
@usuario_ativo_requerido
def auditoria():
    page    = request.args.get('page', 1, type=int)
    tabela  = request.args.get('tabela', '')
    acao    = request.args.get('acao', '')

    query = Auditoria.query.order_by(Auditoria.data_hora.desc())

    if tabela:
        query = query.filter(Auditoria.tabela_afetada == tabela)
    if acao:
        query = query.filter(Auditoria.acao == acao.upper())

    registros = query.paginate(page=page, per_page=25, error_out=False)
    tabelas_distintas = db.session.query(Auditoria.tabela_afetada).distinct().all()
    acoes_distintas   = db.session.query(Auditoria.acao).distinct().all()

    return render_template('auditoria.html',
                           registros=registros,
                           tabelas=[t[0] for t in tabelas_distintas],
                           acoes=[a[0] for a in acoes_distintas],
                           filtro_tabela=tabela,
                           filtro_acao=acao)