import os
import json
from datetime import datetime
from functools import wraps

from flask import current_app, request, abort, flash, redirect, url_for
from flask_login import current_user, login_required, logout_user
from werkzeug.utils import secure_filename

from core.extensions import db
from core.models import Auditoria

def log_auditoria(acao: str, tabela: str, registro_id: int = None, dados: dict = None, ator_id: int = None):
    try:
        entrada = Auditoria(
            id_ator        = ator_id or (current_user.id if current_user.is_authenticated else None),
            acao           = acao.upper(),
            tabela_afetada = tabela,
            registro_id    = registro_id,
            dados_json     = json.dumps(dados, ensure_ascii=False, default=str) if dados else None,
        )
        db.session.add(entrada)
        db.session.flush()
    except Exception as exc:
        current_app.logger.error(f'[AUDITORIA] Falha ao registrar: {exc}')


def extensao_permitida(filename: str) -> bool:
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    return ext in current_app.config['ALLOWED_EXTENSIONS']


def salvar_arquivo(file_obj) -> str:
    filename = secure_filename(file_obj.filename)
    if not extensao_permitida(filename):
        raise ValueError(f'Tipo de arquivo não permitido: {filename}')
    timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S%f')
    nome_final = f"{timestamp}_{filename}"
    file_obj.save(os.path.join(current_app.config['UPLOAD_FOLDER'], nome_final))
    return nome_final


def perfil_requerido(*perfis):
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated(*args, **kwargs):
            if current_user.perfil not in perfis:
                log_auditoria('NEGADO', 'rota', dados={'url': request.path, 'perfil': current_user.perfil})
                db.session.commit()
                abort(403)
            return f(*args, **kwargs)
        return decorated
    return decorator


def usuario_ativo_requerido(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.ativo:
            logout_user()
            flash('Sua conta foi desativada. Contacte o administrador.', 'danger')
            # Alterado para 'auth.login' para refletir o nosso novo Blueprint
            return redirect(url_for('auth.login')) 
        return f(*args, **kwargs)
    return decorated