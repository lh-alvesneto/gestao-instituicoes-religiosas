"""
=============================================================================
  Funções Utilitárias e Decoradores de Segurança
  Arquivo: utils.py 
=============================================================================
"""

import json
import os
import uuid
from datetime import datetime, timezone
from functools import wraps

import filetype
from flask import abort, current_app, flash, redirect, request, url_for
from flask_login import current_user, login_required, logout_user
from werkzeug.utils import secure_filename

from core.extensions import db
from core.models import Auditoria, PerfilUsuario


def log_auditoria(acao: str, tabela: str, registro_id: int = None, dados: dict = None, ator_id: int = None):
    try:
        entrada = Auditoria(
            id_ator=ator_id or (current_user.id if current_user.is_authenticated else None),
            acao=acao.upper(),
            tabela_afetada=tabela,
            registro_id=registro_id,
            dados_json=json.dumps(dados, ensure_ascii=False, default=str) if dados else None,
        )
        db.session.add(entrada)
    except Exception as exc:
        current_app.logger.error(f'[AUDITORIA] Falha ao registrar log: {exc}')


def salvar_arquivo(arquivo, destino_dir: str = None) -> str:
    if not arquivo or not arquivo.filename:
        raise ValueError("Nenhum arquivo enviado.")

    cabecalho = arquivo.read(2048)
    arquivo.seek(0)

    tipo = filetype.guess(cabecalho)
    
    tipos_seguros = {
        'image/jpeg': '.jpg',
        'image/png': '.png',
        'image/webp': '.webp',
        'image/gif': '.gif',
        'application/pdf': '.pdf'
    }
    
    if tipo is None or tipo.mime not in tipos_seguros:
        raise ValueError("Formato inválido. Apenas imagens e PDFs reais são aceitos.")

    extensao_segura = tipos_seguros[tipo.mime]
    hash_nome = f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"
    nome_seguro = secure_filename(f"{hash_nome}{extensao_segura}")
    
    pasta_destino = destino_dir or current_app.config['UPLOAD_FOLDER']
    
    os.makedirs(pasta_destino, exist_ok=True)
    
    caminho_completo = os.path.join(pasta_destino, nome_seguro)
    arquivo.save(caminho_completo)
    
    return nome_seguro


def perfil_requerido(*perfis):
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated(*args, **kwargs):
            valores_permitidos = [p.value if isinstance(p, PerfilUsuario) else p for p in perfis]
            perfil_atual = current_user.perfil.value if isinstance(current_user.perfil, PerfilUsuario) else current_user.perfil
            
            if perfil_atual not in valores_permitidos:
                log_auditoria('NEGADO', 'rota', dados={'url': request.path, 'perfil': perfil_atual})
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
            return redirect(url_for('auth.login')) 
        return f(*args, **kwargs)
    return decorated