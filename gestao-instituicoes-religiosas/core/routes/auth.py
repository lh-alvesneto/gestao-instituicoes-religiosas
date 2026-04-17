from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user

from core.extensions import db
from core.models import Usuario, Auditoria
from core.utils import log_auditoria, usuario_ativo_requerido

# Aqui nasce o nosso Blueprint chamado 'auth'
auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/')
def index():
    if current_user.is_authenticated:
        # ATENÇÃO: Temporariamente vai falhar se estiver logado, pois não criámos a rota 'dashboard' ainda!
        return redirect(url_for('dashboard.index')) 
    return redirect(url_for('auth.login'))

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        senha = request.form.get('senha', '')

        usuario = Usuario.query.filter_by(email=email).first()

        if usuario and usuario.check_senha(senha):
            if not usuario.ativo:
                flash('Conta inativa. Contacte o administrador.', 'danger')
                log_auditoria('LOGIN', 'usuario', usuario.id, {'motivo': 'conta_inativa'}, usuario.id)
                db.session.commit()
                return redirect(url_for('auth.login'))

            login_user(usuario, remember=False)
            log_auditoria('LOGIN', 'usuario', usuario.id, {'email': email, 'ip': request.remote_addr})
            db.session.commit()

            next_page = request.args.get('next')
            flash(f'Bem-vindo(a), {usuario.nome}!', 'success')
            
            # Se tentar fazer login agora, dará erro 404/500 porque não criámos os outros Blueprints
            return redirect(next_page or url_for('dashboard.index'))

        flash('Credenciais inválidas. Tente novamente.', 'danger')
        log_auditoria('NEGADO', 'login', dados={'email': email, 'ip': request.remote_addr}, ator_id=None)
        db.session.commit()

    return render_template('login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    log_auditoria('LOGOUT', 'usuario', current_user.id)
    db.session.commit()
    logout_user()
    flash('Sessão encerrada com segurança.', 'info')
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
            log_auditoria('EDITOU', 'usuario', current_user.id, {'acao': 'troca_senha', 'email': current_user.email})
            db.session.commit()
            flash('Senha alterada com sucesso!', 'success')
            return redirect(url_for('auth.perfil'))

    minhas_acoes = (Auditoria.query
                    .filter_by(id_ator=current_user.id)
                    .order_by(Auditoria.data_hora.desc())
                    .limit(10).all())

    return render_template('perfil.html', minhas_acoes=minhas_acoes)