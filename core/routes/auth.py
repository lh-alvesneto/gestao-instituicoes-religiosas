"""
=============================================================================
  Autenticação e Gestão de Perfil
  Arquivo: auth.py 
=============================================================================
"""

from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy import select, desc
from core.extensions import limiter, db
from core.models import Usuario, Auditoria
from core.utils import log_auditoria, usuario_ativo_requerido

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index')) 
    return redirect(url_for('auth.login'))

@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        senha = request.form.get('senha', '')

        stmt = select(Usuario).filter_by(email=email)
        usuario = db.session.execute(stmt).scalar_one_or_none()

        if usuario and usuario.check_senha(senha):
            if not usuario.ativo:
                flash('Sua conta está inativa. Procure o administrador.', 'danger')
                return render_template('login.html')
            
            login_user(usuario)
            log_auditoria('LOGIN', 'usuario', usuario.id)
            db.session.commit()
            
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('dashboard.index'))
        else:
            flash('E-mail ou senha inválidos.', 'danger')

    return render_template('login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    log_auditoria('LOGOUT', 'usuario', current_user.id)
    db.session.commit()
    logout_user()
    flash('Sessão encerrada.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/perfil', methods=['GET', 'POST'])
@login_required
@usuario_ativo_requerido
def perfil():
    if request.method == 'POST':
        senha_atual   = request.form.get('senha_atual', '')
        nova_senha    = request.form.get('nova_senha', '')
        confirma_senha = request.form.get('confirma_senha', '')

        if not current_user.check_senha(senha_atual):
            flash('Senha atual incorreta.', 'danger')
        elif len(nova_senha) < 6:
            flash('A nova senha deve ter pelo menos 6 caracteres.', 'warning')
        elif nova_senha != confirma_senha:
            flash('A nova senha e a confirmação não coincidem.', 'warning')
        else:
            current_user.set_senha(nova_senha)
            log_auditoria('EDITOU', 'usuario', current_user.id, {'acao': 'troca_senha'})
            db.session.commit()
            flash('Senha alterada com sucesso!', 'success')
            return redirect(url_for('dashboard.index'))

    stmt_logs = select(Auditoria).where(
        Auditoria.id_ator == current_user.id
    ).order_by(desc(Auditoria.data_hora)).limit(15)
    
    atividades = db.session.scalars(stmt_logs).all()

    return render_template('perfil.html', usuario=current_user, atividades=atividades)