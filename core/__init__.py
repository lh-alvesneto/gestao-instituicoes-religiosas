"""
=============================================================================
  Inicialização da Aplicação e Configurações Globais
  Arquivo: __init__.py 
=============================================================================
"""

import os
import json
from datetime import datetime, timezone
from dotenv import load_dotenv
from flask import Flask, flash, redirect, request, url_for
from sqlalchemy import select, func

from core.extensions import db, login_manager, csrf, limiter, cache, migrate
from core.models import SolicitacaoMaterial, SolicitacaoManutencao, StatusMaterial, StatusManutencao
from core.exceptions import RegraNegocioError, SistemaErro


def create_app():
    load_dotenv()
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    app = Flask(__name__, template_folder='../templates', static_folder='../static')

    app.config.update(
        SECRET_KEY=os.getenv('FLASK_SECRET_KEY', 'dev-key'),
        SQLALCHEMY_DATABASE_URI=os.getenv('DATABASE_URL', f"sqlite:///{os.path.join(base_dir, 'demandas.db')}"),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        UPLOAD_FOLDER=os.path.join(base_dir, 'uploads'),
        MAX_CONTENT_LENGTH=5 * 1024 * 1024,
        ALLOWED_EXTENSIONS={'png', 'jpg', 'jpeg', 'pdf'},
        MAX_IMAGENS_POR_CHAMADO=3,
        CACHE_TYPE='FileSystemCache',
        CACHE_DIR=os.path.join(base_dir, '.flask_cache'),
        CACHE_DEFAULT_TIMEOUT=300
    )

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)
    cache.init_app(app)

    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Por favor, inicie sessão para aceder a esta página.'
    login_manager.login_message_category = 'warning'

    from core.models import Usuario

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(Usuario, int(user_id))

    @login_manager.unauthorized_handler
    def unauthorized():
        if request.path.startswith('/api/'):
            return {"erro": "Não autorizado"}, 401
        flash(login_manager.login_message, login_manager.login_message_category)
        return redirect(url_for(login_manager.login_view, next=request.path))

    # =========================================================================
    # FILTROS DE TEMPLATE (JINJA2)
    # =========================================================================
    
    @app.template_filter('iniciais_avatar')
    def iniciais_avatar(nome):
        """Retorna as iniciais de um nome para o componente de Avatar"""
        if not nome:
            return "U"
        partes = str(nome).strip().split()
        if len(partes) == 1:
            return partes[0][:2].upper()
        return (partes[0][0] + partes[-1][0]).upper()

    @app.template_filter('smart_title')
    def smart_title(s):
        if not s:
            return ""
        excecoes = {'de', 'da', 'do', 'das', 'dos', 'e'}
        palavras = str(s).split()
        resultado = []
        for i, p in enumerate(palavras):
            if i > 0 and p.lower() in excecoes:
                resultado.append(p.lower())
            else:
                resultado.append(p.capitalize())
        return " ".join(resultado)

    @app.template_filter('humanizar_auditoria')
    def humanizar_auditoria(log):
        if not log:
            return ""
        
        acao = log.acao.upper()
        
        try:
            if acao == 'STATUS_ALTERADO':
                novo_status = "Desconhecido"
                if log.dados_json:
                    try:
                        dados = json.loads(log.dados_json)
                        novo_status = dados.get('para', dados.get('status', 'Desconhecido')).replace('_', ' ').title()
                    except json.JSONDecodeError:
                        pass
                return f"Alterou o status para <b>{novo_status}</b>."

            if acao == 'EDITOU':
                corpo = "Alterou informações no registro."
                justificativa = None

                if log.dados_json:
                    try:
                        dados = json.loads(log.dados_json)
                        if 'campos_alterados' in dados and isinstance(dados['campos_alterados'], list):
                            campos = [str(c).replace('_', ' ').title() for c in dados['campos_alterados']]
                            if campos:
                                corpo = f"Atualizou os campos: {', '.join(campos)}."
                        
                        justificativa = dados.get('justificativa')
                    except json.JSONDecodeError:
                        pass

                acao_label = "<b>Editou</b>"
                if justificativa:
                    just_limpa = str(justificativa).replace('"', '&quot;').replace("'", "&#39;")
                    just_curta = justificativa[:60] + '...' if len(justificativa) > 60 else justificativa
                    footer = f"<div class='mt-1 bg-light p-1 px-2 rounded border-start border-3 border-warning small text-dark' style='font-size:0.75rem; cursor: help;' title='{just_limpa}'><strong>Motivo:</strong> {just_curta}</div>"
                else:
                    footer = ""
                
                return f"{acao_label} o registro.<br><small class='lh-sm text-secondary'>{corpo}</small>{footer}"

            if acao in ['CRIOU', 'CRIACAO']:
                return "<b>Criou</b> um novo registro no sistema."
            if acao in ['EXCLUIU', 'EXCLUSAO', 'DELETOU']:
                return "<span class='text-danger fw-bold'>Removeu</span> o registro definitivamente."

            return f"Ação de sistema: <b>{acao.replace('_', ' ').title()}</b>"

        except Exception:
            return f"Ação de sistema: <b>{log.acao.replace('_', ' ').title()}</b>"

    # =========================================================================
    # REGISTRO DE ROTAS E ERROR HANDLERS
    # =========================================================================

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

    @app.errorhandler(404)
    def page_not_found(e):
        if request.path.startswith('/api/'):
            return {"erro": "Endpoint não encontrado"}, 404
        return redirect(url_for('dashboard.index'))

    @app.errorhandler(500)
    def internal_server_error(e):
        if request.path.startswith('/api/'):
            return {"erro": "Ocorreu um erro interno no servidor."}, 500
        from flask import render_template
        return render_template('erro.html', erro="Ocorreu um erro interno no servidor. A nossa equipa já foi notificada."), 500

    @app.errorhandler(RegraNegocioError)
    def handle_regra_negocio(e):
        if request.path.startswith('/api/'):
            return {"erro": e.mensagem}, 400
        flash(e.mensagem, "warning")
        return redirect(request.referrer or url_for('dashboard.index'))

    @app.context_processor
    def inject_now():
        return {'now': datetime.now(timezone.utc)}

    return app