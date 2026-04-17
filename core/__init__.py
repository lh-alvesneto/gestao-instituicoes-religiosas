import os
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask

from core.extensions import db, login_manager
from core.models import Usuario, SolicitacaoMaterial, SolicitacaoManutencao

def create_app():
    load_dotenv()
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    app = Flask(__name__, 
                template_folder=os.path.join(base_dir, 'templates'),
                static_folder=os.path.join(base_dir, 'static'))

    app.config.update(
        SECRET_KEY=os.getenv('FLASK_SECRET_KEY', 'dev-key'),
        SQLALCHEMY_DATABASE_URI=os.getenv('DATABASE_URL', f"sqlite:///{os.path.join(base_dir, 'demandas.db')}"),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        UPLOAD_FOLDER=os.path.join(base_dir, 'uploads'),
        MAX_CONTENT_LENGTH=5 * 1024 * 1024,
        ALLOWED_EXTENSIONS={'png', 'jpg', 'jpeg'},
        MAX_IMAGENS_POR_CHAMADO=3
    )

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    # --- Filtros e Contextos Globais ---
    @app.template_filter('smart_title')
    def smart_title(text):
        if not text: return text
        excecoes = ['de', 'da', 'do', 'das', 'dos', 'e']
        palavras = text.split()
        res = [p.lower() if p.lower() in excecoes and i > 0 else p.capitalize() for i, p in enumerate(palavras)]
        return ' '.join(res)

    @app.context_processor
    def inject_globals():
        p_mat = p_man = 0
        try:
            from flask_login import current_user
            if current_user.is_authenticated and current_user.pode_gerenciar:
                p_mat = SolicitacaoMaterial.query.filter_by(status='pendente', ativo=True).count()
                p_man = SolicitacaoManutencao.query.filter_by(status='aberto', ativo=True).count()
        except Exception:
            pass # Evita quebrar a tela de login se o banco ainda não existir
            
        return dict(pendentes_materiais=p_mat, pendentes_manutencao=p_man, ano_atual=datetime.utcnow().year)

    # --- Registro de Blueprints ---
    from core.routes.auth import auth_bp
    from core.routes.admin import admin_bp
    from core.routes.dashboard import dashboard_bp
    from core.routes.materiais import materiais_bp
    from core.routes.manutencao import manutencao_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(materiais_bp)
    app.register_blueprint(manutencao_bp)
    
    return app