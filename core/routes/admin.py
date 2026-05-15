"""
=============================================================================
  Rotas de Administração e Auditoria do Sistema
  Arquivo: admin.py 
=============================================================================
"""

import json
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import current_user
from sqlalchemy import select, or_, desc, asc
from sqlalchemy.orm import joinedload

from core.services import GestaoService
from core.extensions import db
from core.models import Usuario, Auditoria, PerfilUsuario
from core.utils import usuario_ativo_requerido, perfil_requerido

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/usuarios')
@perfil_requerido(PerfilUsuario.ADMINISTRADOR, PerfilUsuario.GESTOR)
@usuario_ativo_requerido
def lista_usuarios():
    termo = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 10, type=int), 100)
    
    perfil_filtro = request.args.get('perfil', '')
    status_filtro = request.args.get('status', '')
    sort_col = request.args.get('sort', 'nome')
    sort_dir = request.args.get('dir', 'asc')

    colunas_permitidas = ['id', 'nome', 'email', 'perfil', 'ativo', 'data_criacao']
    if sort_col not in colunas_permitidas:
        sort_col = 'nome'

    stmt = select(Usuario)
    if termo:
        stmt = stmt.where(or_(Usuario.nome.ilike(f"%{termo}%"), Usuario.email.ilike(f"%{termo}%")))
    if perfil_filtro:
        stmt = stmt.where(Usuario.perfil == perfil_filtro)
    if status_filtro:
        status_bool = (status_filtro == 'ativo')
        stmt = stmt.where(Usuario.ativo == status_bool)

    coluna = getattr(Usuario, sort_col)
    stmt = stmt.order_by(asc(coluna) if sort_dir == 'asc' else desc(coluna))

    pagination = db.paginate(stmt, page=page, per_page=per_page, error_out=False)
    return render_template('usuarios.html', lista=pagination)

@admin_bp.route('/usuarios/<int:uid>')
@perfil_requerido(PerfilUsuario.ADMINISTRADOR, PerfilUsuario.GESTOR)
@usuario_ativo_requerido
def detalhe_usuario(uid: int):
    if uid == current_user.id:
        return redirect(url_for('auth.perfil'))
        
    usuario = db.session.get(Usuario, uid)
    if not usuario:
        abort(404)
        
    stmt_logs = select(Auditoria).where(Auditoria.id_ator == uid).order_by(desc(Auditoria.data_hora)).limit(15)
    atividades = db.session.scalars(stmt_logs).all()
    
    return render_template('detalhe_usuario.html', u=usuario, atividades=atividades)

@admin_bp.route('/usuarios/novo', methods=['GET', 'POST'])
@perfil_requerido(PerfilUsuario.ADMINISTRADOR, PerfilUsuario.GESTOR)
@usuario_ativo_requerido
def novo_usuario(): 
    perfis_disponiveis = [PerfilUsuario.USUARIO.value, PerfilUsuario.GESTOR.value]
    if current_user.is_admin:
        perfis_disponiveis.append(PerfilUsuario.ADMINISTRADOR.value)

    if request.method == 'POST':
        nome = request.form.get('nome')
        email = request.form.get('email', '').lower()
        senha = request.form.get('senha')
        perfil = request.form.get('perfil')

        GestaoService.criar_usuario(nome, email, senha, perfil, current_user)
        flash(f'Usuário "{nome}" criado com sucesso.', 'success')
        return redirect(url_for('admin.lista_usuarios'))

    return render_template('form_usuario.html', perfis=perfis_disponiveis)

@admin_bp.route('/usuarios/<int:uid>/editar', methods=['GET', 'POST'])
@perfil_requerido(PerfilUsuario.ADMINISTRADOR, PerfilUsuario.GESTOR)
@usuario_ativo_requerido
def editar_usuario(uid: int):
    usuario_alvo = db.session.get(Usuario, uid)
    if not usuario_alvo:
        abort(404)

    if usuario_alvo.id == current_user.id:
        flash("Para alterar seus próprios dados, utilize a opção 'Meu Perfil' no menu lateral.", "warning")
        return redirect(url_for('admin.lista_usuarios'))

    if usuario_alvo.is_admin and not current_user.is_admin:
        flash("Acesso Negado: Apenas administradores podem editar outros administradores.", "danger")
        return redirect(url_for('admin.lista_usuarios'))

    perfis_disponiveis = [PerfilUsuario.USUARIO.value, PerfilUsuario.GESTOR.value]
    if current_user.is_admin:
        perfis_disponiveis.append(PerfilUsuario.ADMINISTRADOR.value)

    if request.method == 'POST':
        nome = request.form.get('nome')
        email = request.form.get('email', '').lower()
        perfil = request.form.get('perfil')
        senha = request.form.get('senha')
        justificativa = request.form.get('justificativa_edicao')

        perfil_atual = usuario_alvo.perfil.value if hasattr(usuario_alvo.perfil, 'value') else usuario_alvo.perfil
        if (usuario_alvo.nome == nome and 
            usuario_alvo.email == email and 
            perfil_atual == perfil and 
            not senha):
            flash('Nenhuma alteração de dados foi detectada para ser salva.', 'warning')
            return redirect(url_for('admin.lista_usuarios'))

        estado_anterior = {
            'nome': usuario_alvo.nome,
            'email': usuario_alvo.email,
            'perfil': usuario_alvo.perfil.value if hasattr(usuario_alvo.perfil, 'value') else usuario_alvo.perfil
        }

        try:
            usuario_alvo.nome = nome
            usuario_alvo.email = email
            if perfil in perfis_disponiveis:
                usuario_alvo.perfil = PerfilUsuario(perfil)
            if senha:
                usuario_alvo.set_senha(senha)

            if justificativa:
                estado_novo = {
                    'nome': usuario_alvo.nome,
                    'email': usuario_alvo.email,
                    'perfil': usuario_alvo.perfil.value if hasattr(usuario_alvo.perfil, 'value') else usuario_alvo.perfil
                }
                
                dados_audit = {
                    'antes': estado_anterior,
                    'depois': estado_novo,
                    'justificativa_edicao': justificativa
                }
                
                nova_auditoria = Auditoria(
                    id_ator=current_user.id,
                    acao='EDITOU',
                    tabela_afetada='usuario',
                    registro_id=usuario_alvo.id,
                    dados_json=json.dumps(dados_audit, ensure_ascii=False)
                )
                db.session.add(nova_auditoria)

            db.session.commit()
            flash(f'Acessos de "{nome}" atualizados com sucesso.', 'success')
            return redirect(url_for('admin.lista_usuarios'))
        except Exception:
            db.session.rollback()
            flash('Erro ao atualizar usuário. Verifique se o e-mail inserido já não pertence a outro cadastro.', 'danger')

    return render_template('form_usuario.html', u=usuario_alvo, perfis=perfis_disponiveis, editando=True)

@admin_bp.route('/usuarios/<int:uid>/status', methods=['POST'])
@perfil_requerido(PerfilUsuario.ADMINISTRADOR, PerfilUsuario.GESTOR)
@usuario_ativo_requerido
def alternar_status(uid: int):
    usuario_alvo = db.session.get(Usuario, uid)
    if not usuario_alvo:
        abort(404)
        
    if usuario_alvo.is_admin and not current_user.is_admin:
        flash("Você não tem permissão para alterar o status de um administrador.", "danger")
        return redirect(url_for('admin.lista_usuarios'))

    ficou_ativo = GestaoService.alternar_status_usuario(uid, current_user.id)
    verbo = 'reativado' if ficou_ativo else 'inativado'
    flash(f"Usuário {verbo} com sucesso.", 'success')
        
    return redirect(url_for('admin.lista_usuarios'))

@admin_bp.route('/auditoria')
@perfil_requerido(PerfilUsuario.ADMINISTRADOR)
@usuario_ativo_requerido
def auditoria():
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 10, type=int), 100)
    
    q = request.args.get('q', '').strip()
    tabela = request.args.get('tabela', '').strip()
    acao = request.args.get('acao', '').strip()
    data_inicio = request.args.get('inicio', '').strip()
    data_fim = request.args.get('fim', '').strip()

    stmt = select(Auditoria).options(joinedload(Auditoria.ator))

    if q:
        q_upper = q.upper()
        if q_upper.startswith('MAT-') and q_upper[4:].isdigit():
            stmt = stmt.where(Auditoria.tabela_afetada == 'solicitacao_material', Auditoria.registro_id == int(q_upper[4:]))
        elif q_upper.startswith('MAN-') and q_upper[4:].isdigit():
            stmt = stmt.where(Auditoria.tabela_afetada == 'solicitacao_manutencao', Auditoria.registro_id == int(q_upper[4:]))
        elif q_upper.startswith('USR-') and q_upper[4:].isdigit():
            stmt = stmt.where(Auditoria.tabela_afetada == 'usuario', Auditoria.registro_id == int(q_upper[4:]))
        else:
            condicoes = [
                Auditoria.dados_json.ilike(f"%{q}%"),
                Auditoria.acao.ilike(f"%{q}%")
            ]
            if q.isdigit():
                condicoes.append(Auditoria.registro_id == int(q))
                
            stmt = stmt.where(or_(*condicoes))

    if tabela:
        stmt = stmt.where(Auditoria.tabela_afetada.ilike(f"%{tabela}%"))
    if acao:
        if acao == 'cria':
            stmt = stmt.where(Auditoria.acao.ilike('%CRI%')) 
        elif acao == 'edit':
            stmt = stmt.where(or_(Auditoria.acao.ilike('%EDIT%'), Auditoria.acao.ilike('%STATUS%'))) 
        elif acao == 'exclu':
            stmt = stmt.where(Auditoria.acao.ilike('%EXCLU%')) 
        else:
            stmt = stmt.where(Auditoria.acao.ilike(f"%{acao}%"))
    if data_inicio:
        stmt = stmt.where(Auditoria.data_hora >= f"{data_inicio} 03:00:00")
    if data_fim:
        try:
            fim_dt = datetime.strptime(data_fim, '%Y-%m-%d') + timedelta(days=1)
            stmt = stmt.where(Auditoria.data_hora < fim_dt.strftime('%Y-%m-%d 03:00:00'))
        except ValueError:
            pass

    stmt = stmt.order_by(desc(Auditoria.data_hora))
    lista_paginada = db.paginate(stmt, page=page, per_page=per_page, error_out=False)
    
    return render_template('auditoria.html', lista=lista_paginada, timedelta=timedelta)