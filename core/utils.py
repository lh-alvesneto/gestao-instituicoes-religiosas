import os
import json
import filetype
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

def salvar_arquivo(arquivo) -> str:
    """
    Guarda o ficheiro fisicamente, garantindo que o MIME type real 
    corresponde a imagens ou PDFs, independentemente da extensão no nome.
    """
    if not arquivo or not arquivo.filename:
        raise ValueError("Nenhum arquivo enviado.")

    # 1. Segurança: Ler os primeiros 2048 bytes para inspecionar os "Magic Numbers"
    cabecalho = arquivo.read(2048)
    arquivo.seek(0)  # Volta o cursor ao início para permitir o save() no final

    tipo = filetype.guess(cabecalho)
    tipos_permitidos = ['image/jpeg', 'image/png', 'image/webp', 'image/gif', 'application/pdf']
    
    if tipo is None or tipo.mime not in tipos_permitidos:
        raise ValueError("Formato inválido. Apenas imagens e PDFs reais são aceites (mesmo que a extensão pareça correta).")

    # 2. Gera um nome seguro e irreversível
    extensao = os.path.splitext(arquivo.filename)[1].lower()
    hash_nome = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"
    nome_seguro = secure_filename(f"{hash_nome}{extensao}")
    
    # 3. Guarda fisicamente no disco
    caminho_completo = os.path.join(current_app.config['UPLOAD_FOLDER'], nome_seguro)
    arquivo.save(caminho_completo)
    
    return nome_seguro

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