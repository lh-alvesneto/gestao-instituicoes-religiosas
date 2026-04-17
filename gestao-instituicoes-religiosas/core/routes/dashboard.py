from datetime import datetime
from flask import Blueprint, render_template
from flask_login import login_required, current_user

from core.models import SolicitacaoMaterial, SolicitacaoManutencao
from core.utils import usuario_ativo_requerido

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/dashboard')
@login_required
@usuario_ativo_requerido
def index(): # O endpoint passará a ser 'dashboard.index'
    u = current_user

    if u.pode_gerenciar:
        hoje = datetime.utcnow()
        inicio_mes = datetime(hoje.year, hoje.month, 1)

        kpi = {
            'mat_pendente': SolicitacaoMaterial.query.filter_by(status='pendente', ativo=True).count(),
            'man_aberto': SolicitacaoManutencao.query.filter_by(status='aberto', ativo=True).count(),
            'man_alta': SolicitacaoManutencao.query.filter(
                SolicitacaoManutencao.status.in_(['aberto', 'em_andamento']),
                SolicitacaoManutencao.urgencia == 'alta',
                SolicitacaoManutencao.ativo == True
            ).count(),
            'man_andamento': SolicitacaoManutencao.query.filter_by(status='em_andamento', ativo=True).count(),
            'mat_aprovado': SolicitacaoMaterial.query.filter_by(status='aprovado', ativo=True).count(),
            'concluidos_mes': (
                SolicitacaoMaterial.query.filter(
                    SolicitacaoMaterial.status == 'entregue',
                    SolicitacaoMaterial.ativo == True,
                    SolicitacaoMaterial.data_criacao >= inicio_mes
                ).count() +
                SolicitacaoManutencao.query.filter(
                    SolicitacaoManutencao.status == 'concluido',
                    SolicitacaoManutencao.ativo == True,
                    SolicitacaoManutencao.data_criacao >= inicio_mes
                ).count()
            )
        }
        
        ultimas_mat = SolicitacaoMaterial.query.filter_by(ativo=True).order_by(SolicitacaoMaterial.data_criacao.desc()).limit(6).all()
        ultimas_man = SolicitacaoManutencao.query.filter_by(ativo=True).order_by(SolicitacaoManutencao.data_criacao.desc()).limit(6).all()
        
        return render_template('dashboard.html', kpi=kpi, ultimas_mat=ultimas_mat, ultimas_man=ultimas_man)
    else:
        minhas_mat = SolicitacaoMaterial.query.filter_by(id_usuario=u.id, ativo=True).order_by(SolicitacaoMaterial.data_criacao.desc()).limit(5).all()
        minhas_man = SolicitacaoManutencao.query.filter_by(id_usuario=u.id, ativo=True).order_by(SolicitacaoManutencao.data_criacao.desc()).limit(5).all()
        return render_template('dashboard.html', minhas_mat=minhas_mat, minhas_man=minhas_man)

@dashboard_bp.route('/historico')
@login_required
@usuario_ativo_requerido
def historico():
    u = current_user

    q_mat = SolicitacaoMaterial.query.filter(
        SolicitacaoMaterial.ativo == True,
        SolicitacaoMaterial.status.in_(['entregue', 'cancelado'])
    )
    q_man = SolicitacaoManutencao.query.filter(
        SolicitacaoManutencao.ativo == True,
        SolicitacaoManutencao.status.in_(['concluido', 'cancelado'])
    )

    if u.is_usuario:
        q_mat = q_mat.filter_by(id_usuario=u.id)
        q_man = q_man.filter_by(id_usuario=u.id)

    mat_historico = q_mat.order_by(SolicitacaoMaterial.data_criacao.desc()).all()
    man_historico = q_man.order_by(SolicitacaoManutencao.data_criacao.desc()).all()

    return render_template('historico.html', mat_historico=mat_historico, man_historico=man_historico)