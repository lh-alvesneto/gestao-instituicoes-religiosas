"""
=============================================================================
  Rotas do Painel de Controle e Histórico
  Arquivo: dashboard.py 
=============================================================================
"""

import csv
import io
from datetime import datetime, timedelta, timezone

from flask import Blueprint, Response, jsonify, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func, or_, select
from sqlalchemy.orm import joinedload

from core.extensions import cache, db
from core.models import (
    SolicitacaoManutencao, SolicitacaoMaterial, StatusManutencao,
    StatusMaterial, UrgenciaManutencao
)
from core.utils import usuario_ativo_requerido


dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/api/notificacoes')
@login_required
def notificacoes():
    contadores = cache.get('contadores_globais')
    if contadores is None:
        pendentes_mat = db.session.scalar(select(func.count()).select_from(SolicitacaoMaterial).filter_by(status=StatusMaterial.PENDENTE, ativo=True)) or 0
        pendentes_man = db.session.scalar(select(func.count()).select_from(SolicitacaoManutencao).filter_by(status=StatusManutencao.ABERTO, ativo=True)) or 0
        contadores = {
            'pendentes_materiais': pendentes_mat,
            'pendentes_manutencao': pendentes_man
        }
        cache.set('contadores_globais', contadores, timeout=30)
    return jsonify(contadores)


@dashboard_bp.route('/dashboard')
@login_required
@usuario_ativo_requerido
def index():
    u = current_user

    if u.pode_gerenciar:
        limite_atraso = datetime.now(timezone.utc) - timedelta(hours=48)
        man_atrasada = db.session.scalar(select(SolicitacaoManutencao).filter(
            SolicitacaoManutencao.status == StatusManutencao.ABERTO,
            SolicitacaoManutencao.urgencia == UrgenciaManutencao.ALTA,
            SolicitacaoManutencao.data_criacao < limite_atraso,
            SolicitacaoManutencao.ativo == True
        ).limit(1))
        
        alertas_urgentes = []
        if man_atrasada:
            alertas_urgentes.append({
                'titulo': 'Urgência Não Atendida',
                'texto': f'O chamado crítico para "{man_atrasada.local}" ultrapassou 48h de espera.',
                'link': url_for('manutencao.detalhe', cid=man_atrasada.id)
            })

        man_alta = db.session.scalar(
            select(func.count()).select_from(SolicitacaoManutencao).filter(
                SolicitacaoManutencao.ativo == True,
                SolicitacaoManutencao.urgencia == UrgenciaManutencao.ALTA,
                SolicitacaoManutencao.status.in_([StatusManutencao.ABERTO, StatusManutencao.EM_ANDAMENTO])
            )
        ) or 0

        mat_pendente = db.session.scalar(
            select(func.count()).select_from(SolicitacaoMaterial).filter(
                SolicitacaoMaterial.ativo == True,
                SolicitacaoMaterial.status == StatusMaterial.PENDENTE
            )
        ) or 0

        man_andamento = db.session.scalar(
            select(func.count()).select_from(SolicitacaoManutencao).filter(
                SolicitacaoManutencao.ativo == True,
                SolicitacaoManutencao.status == StatusManutencao.EM_ANDAMENTO
            )
        ) or 0
        
        mat_andamento = db.session.scalar(
            select(func.count()).select_from(SolicitacaoMaterial).filter(
                SolicitacaoMaterial.ativo == True,
                SolicitacaoMaterial.status == StatusMaterial.APROVADO
            )
        ) or 0

        kpi = {
            'man_alta': man_alta,
            'mat_pendente': mat_pendente,
            'man_andamento': man_andamento + mat_andamento
        }

        stmt_mat = select(SolicitacaoMaterial).options(joinedload(SolicitacaoMaterial.solicitante)).filter_by(ativo=True).order_by(SolicitacaoMaterial.data_criacao.desc()).limit(6)
        ultimas_mat = db.session.scalars(stmt_mat).all()
        
        stmt_man = select(SolicitacaoManutencao).options(joinedload(SolicitacaoManutencao.solicitante)).filter_by(ativo=True).order_by(SolicitacaoManutencao.data_criacao.desc()).limit(6)
        ultimas_man = db.session.scalars(stmt_man).all()
        
        return render_template('dashboard.html', alertas_urgentes=alertas_urgentes, kpi=kpi, ultimas_mat=ultimas_mat, ultimas_man=ultimas_man)
    
    else:
        stmt_mat = select(SolicitacaoMaterial).filter_by(id_usuario=u.id, ativo=True).order_by(SolicitacaoMaterial.data_criacao.desc()).limit(5)
        minhas_mat = db.session.scalars(stmt_mat).all()
        stmt_man = select(SolicitacaoManutencao).filter_by(id_usuario=u.id, ativo=True).order_by(SolicitacaoManutencao.data_criacao.desc()).limit(5)
        minhas_man = db.session.scalars(stmt_man).all()
        return render_template('dashboard.html', minhas_mat=minhas_mat, minhas_man=minhas_man)


@dashboard_bp.route('/historico')
@login_required
@usuario_ativo_requerido
def historico():
    return render_template('historico.html')


def aplicar_filtros_historico(stmt, classe, prefixo_rastreio, termo, status_filtro, data_inicio, data_fim):
    if termo:
        termo_upper = termo.upper()
        if termo_upper.startswith(prefixo_rastreio) and termo_upper[4:].isdigit():
            stmt = stmt.where(classe.id == int(termo_upper[4:]))
        else:
            if classe == SolicitacaoMaterial:
                stmt = stmt.where(or_(classe.nome_material.ilike(f"%{termo}%"), classe.justificativa.ilike(f"%{termo}%")))
            else:
                stmt = stmt.where(or_(classe.local.ilike(f"%{termo}%"), classe.descricao.ilike(f"%{termo}%")))

    if status_filtro == 'concluido':
        stmt = stmt.where(classe.status == (StatusMaterial.ENTREGUE if classe == SolicitacaoMaterial else StatusManutencao.CONCLUIDO))
    elif status_filtro == 'cancelado':
        stmt = stmt.where(classe.status == (StatusMaterial.CANCELADO if classe == SolicitacaoMaterial else StatusManutencao.CANCELADO))

    if data_inicio:
        stmt = stmt.where(classe.data_conclusao >= f"{data_inicio} 03:00:00")
    if data_fim:
        try:
            fim_dt = datetime.strptime(data_fim, '%Y-%m-%d') + timedelta(days=1)
            stmt = stmt.where(classe.data_conclusao < fim_dt.strftime('%Y-%m-%d 03:00:00'))
        except ValueError:
            pass
            
    if not current_user.pode_gerenciar:
        stmt = stmt.filter_by(id_usuario=current_user.id)
        
    return stmt


def calcular_sla(data_criacao, data_conclusao):
    if not data_criacao or not data_conclusao:
        return "N/A"
    diff = data_conclusao - data_criacao
    dias = diff.days
    horas = diff.seconds // 3600
    if dias > 0: 
        return f"{dias} dia(s)"
    elif horas > 0: 
        return f"{horas} hora(s)"
    return "Menos de 1h"


@dashboard_bp.route('/api/historico/materiais')
@login_required
def api_historico_materiais():
    page = request.args.get('page', 1, type=int)
    stmt = select(SolicitacaoMaterial).options(joinedload(SolicitacaoMaterial.solicitante)).filter(
        SolicitacaoMaterial.ativo == True,
        SolicitacaoMaterial.status.in_([StatusMaterial.ENTREGUE, StatusMaterial.CANCELADO])
    )
    stmt = aplicar_filtros_historico(stmt, SolicitacaoMaterial, 'MAT-', request.args.get('q', '').strip(), request.args.get('status', '').strip(), request.args.get('inicio', '').strip(), request.args.get('fim', '').strip())
    
    paginated = db.paginate(stmt.order_by(SolicitacaoMaterial.data_conclusao.desc()), page=page, per_page=15, error_out=False)
    
    items = []
    for s in paginated.items:
        items.append({
            'id': s.id,
            'nome_material': s.nome_material,
            'justificativa': s.justificativa,
            'quantidade': s.quantidade,
            'solicitante': s.solicitante.nome if s.solicitante else 'Desconhecido',
            'perfil_solicitante': s.solicitante.perfil.value if s.solicitante and hasattr(s.solicitante.perfil, 'value') else (s.solicitante.perfil if s.solicitante else 'usuario'),
            'data': (s.data_conclusao - timedelta(hours=3)).strftime('%d/%m/%Y %H:%M') if s.data_conclusao else '',
            'status': s.status.value if hasattr(s.status, 'value') else s.status,
            'sla': calcular_sla(s.data_criacao, s.data_conclusao)
        })
        
    return jsonify({'items': items, 'total': paginated.total, 'page': paginated.page, 'pages': paginated.pages, 'has_next': paginated.has_next, 'has_prev': paginated.has_prev})


@dashboard_bp.route('/api/historico/manutencoes')
@login_required
def api_historico_manutencoes():
    page = request.args.get('page', 1, type=int)
    stmt = select(SolicitacaoManutencao).options(joinedload(SolicitacaoManutencao.solicitante)).filter(
        SolicitacaoManutencao.ativo == True,
        SolicitacaoManutencao.status.in_([StatusManutencao.CONCLUIDO, StatusManutencao.CANCELADO])
    )
    stmt = aplicar_filtros_historico(stmt, SolicitacaoManutencao, 'MAN-', request.args.get('q', '').strip(), request.args.get('status', '').strip(), request.args.get('inicio', '').strip(), request.args.get('fim', '').strip())
    
    paginated = db.paginate(stmt.order_by(SolicitacaoManutencao.data_conclusao.desc()), page=page, per_page=15, error_out=False)
    
    items = []
    for m in paginated.items:
        items.append({
            'id': m.id,
            'local': m.local,
            'descricao': m.descricao,
            'urgencia': m.urgencia.value if hasattr(m.urgencia, 'value') else m.urgencia,
            'solicitante': m.solicitante.nome if m.solicitante else 'Desconhecido',
            'perfil_solicitante': m.solicitante.perfil.value if m.solicitante and hasattr(m.solicitante.perfil, 'value') else (m.solicitante.perfil if m.solicitante else 'usuario'),
            'data': (m.data_conclusao - timedelta(hours=3)).strftime('%d/%m/%Y %H:%M') if m.data_conclusao else '',
            'status': m.status.value if hasattr(m.status, 'value') else m.status,
            'sla': calcular_sla(m.data_criacao, m.data_conclusao)
        })
        
    return jsonify({'items': items, 'total': paginated.total, 'page': paginated.page, 'pages': paginated.pages, 'has_next': paginated.has_next, 'has_prev': paginated.has_prev})


@dashboard_bp.route('/api/historico/exportar')
@login_required
def exportar_historico():
    aba = request.args.get('aba', 'materiais')
    termo = request.args.get('q', '').strip()
    status_filtro = request.args.get('status', '').strip()
    data_inicio = request.args.get('inicio', '').strip()
    data_fim = request.args.get('fim', '').strip()

    si = io.StringIO()
    cw = csv.writer(si, delimiter=';') 

    if aba == 'materiais':
        cw.writerow(['Rastreio', 'Data Conclusao', 'Item Solicitado', 'Quantidade', 'Justificativa', 'Solicitante', 'Tempo Resolução (SLA)', 'Status Final'])
        stmt = select(SolicitacaoMaterial).options(joinedload(SolicitacaoMaterial.solicitante)).filter(
            SolicitacaoMaterial.ativo == True,
            SolicitacaoMaterial.status.in_([StatusMaterial.ENTREGUE, StatusMaterial.CANCELADO])
        )
        stmt = aplicar_filtros_historico(stmt, SolicitacaoMaterial, 'MAT-', termo, status_filtro, data_inicio, data_fim)
        registros = db.session.scalars(stmt.order_by(SolicitacaoMaterial.data_conclusao.desc())).all()
        
        for s in registros:
            id_fmt = f"MAT-{s.id:04d}"
            data_fmt = (s.data_conclusao - timedelta(hours=3)).strftime('%d/%m/%Y %H:%M') if s.data_conclusao else ''
            sla = calcular_sla(s.data_criacao, s.data_conclusao)
            status_fmt = s.status.value.upper() if hasattr(s.status, 'value') else s.status.upper()
            solicitante = s.solicitante.nome if s.solicitante else 'Desconhecido'
            cw.writerow([id_fmt, data_fmt, s.nome_material, s.quantidade, s.justificativa, solicitante, sla, status_fmt])

    else:
        cw.writerow(['Rastreio', 'Data Conclusao', 'Local Afetado', 'Descricao do Problema', 'Urgencia', 'Solicitante', 'Tempo Resolução (SLA)', 'Status Final'])
        stmt = select(SolicitacaoManutencao).options(joinedload(SolicitacaoManutencao.solicitante)).filter(
            SolicitacaoManutencao.ativo == True,
            SolicitacaoManutencao.status.in_([StatusManutencao.CONCLUIDO, StatusManutencao.CANCELADO])
        )
        stmt = aplicar_filtros_historico(stmt, SolicitacaoManutencao, 'MAN-', termo, status_filtro, data_inicio, data_fim)
        registros = db.session.scalars(stmt.order_by(SolicitacaoManutencao.data_conclusao.desc())).all()
        
        for m in registros:
            id_fmt = f"MAN-{m.id:04d}"
            data_fmt = (m.data_conclusao - timedelta(hours=3)).strftime('%d/%m/%Y %H:%M') if m.data_conclusao else ''
            sla = calcular_sla(m.data_criacao, m.data_conclusao)
            urgencia = m.urgencia.value.upper() if hasattr(m.urgencia, 'value') else m.urgencia.upper()
            status_fmt = m.status.value.upper() if hasattr(m.status, 'value') else m.status.upper()
            solicitante = m.solicitante.nome if m.solicitante else 'Desconhecido'
            cw.writerow([id_fmt, data_fmt, m.local, m.descricao, urgencia, solicitante, sla, status_fmt])

    output = '\ufeff' + si.getvalue()
    nome_arquivo = f"Relatorio_Historico_{aba}_{datetime.now().strftime('%Y%m%d')}.csv"
    
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename={nome_arquivo}"}
    )