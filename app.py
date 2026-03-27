from flask import Flask, render_template, redirect, url_for, request, session, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from functools import wraps
import os

# ---------------------------------------------------------------------------
# Configuração do App e Banco de Dados
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.config['SECRET_KEY'] = 'chave-secreta-mvp-2024'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///demandas.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


# ---------------------------------------------------------------------------
# Modelos (Tabelas do Banco de Dados)
# ---------------------------------------------------------------------------
class Usuario(db.Model):
    __tablename__ = 'usuario'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    senha = db.Column(db.String(200), nullable=False)
    perfil = db.Column(db.String(20), nullable=False, default='usuario')  # 'admin' ou 'usuario'

    materiais = db.relationship('SolicitacaoMaterial', backref='usuario', lazy=True)
    manutencoes = db.relationship('SolicitacaoManutencao', backref='usuario', lazy=True)


class SolicitacaoMaterial(db.Model):
    __tablename__ = 'solicitacao_material'
    id = db.Column(db.Integer, primary_key=True)
    id_usuario = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    nome_material = db.Column(db.String(150), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    justificativa = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='pendente')  # pendente, aprovado, entregue
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)


class SolicitacaoManutencao(db.Model):
    __tablename__ = 'solicitacao_manutencao'
    id = db.Column(db.Integer, primary_key=True)
    id_usuario = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    local = db.Column(db.String(150), nullable=False)
    descricao_problema = db.Column(db.Text, nullable=False)
    urgencia = db.Column(db.String(20), nullable=False, default='media')  # baixa, media, alta
    status = db.Column(db.String(20), nullable=False, default='aberto')  # aberto, em_andamento, concluido
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)


# ---------------------------------------------------------------------------
# Helpers de Autenticação
# ---------------------------------------------------------------------------
def login_required(f):
    """Decorator: redireciona para login se não houver sessão ativa."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario_id' not in session:
            flash('Por favor, faça login para acessar esta página.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def get_usuario_logado():
    """Retorna o objeto Usuario da sessão atual, ou None."""
    if 'usuario_id' in session:
        return Usuario.query.get(session['usuario_id'])
    return None


# ---------------------------------------------------------------------------
# Rotas de Autenticação
# ---------------------------------------------------------------------------
@app.route('/')
def index():
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'usuario_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        senha = request.form.get('senha', '')

        usuario = Usuario.query.filter_by(email=email).first()

        # Comparação direta (sem hash) — aceitável para MVP acadêmico
        if usuario and usuario.senha == senha:
            session['usuario_id'] = usuario.id
            session['usuario_nome'] = usuario.nome
            session['usuario_perfil'] = usuario.perfil
            flash(f'Bem-vindo(a), {usuario.nome}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('E-mail ou senha incorretos. Tente novamente.', 'danger')

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('Você saiu do sistema com sucesso.', 'info')
    return redirect(url_for('login'))


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
@app.route('/dashboard')
@login_required
def dashboard():
    usuario = get_usuario_logado()

    if usuario.perfil == 'admin':
        # Admin vê totais gerais
        total_materiais_pendentes = SolicitacaoMaterial.query.filter_by(status='pendente').count()
        total_manutencao_aberta = SolicitacaoManutencao.query.filter_by(status='aberto').count()
        total_manutencao_andamento = SolicitacaoManutencao.query.filter_by(status='em_andamento').count()
        total_materiais_aprovados = SolicitacaoMaterial.query.filter_by(status='aprovado').count()

        ultimas_materiais = SolicitacaoMaterial.query.order_by(
            SolicitacaoMaterial.data_criacao.desc()).limit(5).all()
        ultimas_manutencoes = SolicitacaoManutencao.query.order_by(
            SolicitacaoManutencao.data_criacao.desc()).limit(5).all()

        return render_template('dashboard.html',
                               usuario=usuario,
                               total_materiais_pendentes=total_materiais_pendentes,
                               total_manutencao_aberta=total_manutencao_aberta,
                               total_manutencao_andamento=total_manutencao_andamento,
                               total_materiais_aprovados=total_materiais_aprovados,
                               ultimas_materiais=ultimas_materiais,
                               ultimas_manutencoes=ultimas_manutencoes)
    else:
        # Usuário comum vê apenas os seus próprios dados
        minhas_materiais = SolicitacaoMaterial.query.filter_by(
            id_usuario=usuario.id).order_by(SolicitacaoMaterial.data_criacao.desc()).limit(5).all()
        minhas_manutencoes = SolicitacaoManutencao.query.filter_by(
            id_usuario=usuario.id).order_by(SolicitacaoManutencao.data_criacao.desc()).limit(5).all()

        return render_template('dashboard.html',
                               usuario=usuario,
                               minhas_materiais=minhas_materiais,
                               minhas_manutencoes=minhas_manutencoes)


# ---------------------------------------------------------------------------
# Solicitações de Material
# ---------------------------------------------------------------------------
@app.route('/materiais', methods=['GET', 'POST'])
@login_required
def materiais():
    usuario = get_usuario_logado()

    if request.method == 'POST':
        nome_material = request.form.get('nome_material', '').strip()
        quantidade = request.form.get('quantidade', 0)
        justificativa = request.form.get('justificativa', '').strip()

        if not nome_material or not quantidade or not justificativa:
            flash('Preencha todos os campos do formulário.', 'warning')
        else:
            nova = SolicitacaoMaterial(
                id_usuario=usuario.id,
                nome_material=nome_material,
                quantidade=int(quantidade),
                justificativa=justificativa,
                status='pendente'
            )
            db.session.add(nova)
            db.session.commit()
            flash('Solicitação de material enviada com sucesso!', 'success')
            return redirect(url_for('materiais'))

    # Listagem
    if usuario.perfil == 'admin':
        lista = SolicitacaoMaterial.query.order_by(SolicitacaoMaterial.data_criacao.desc()).all()
    else:
        lista = SolicitacaoMaterial.query.filter_by(
            id_usuario=usuario.id).order_by(SolicitacaoMaterial.data_criacao.desc()).all()

    return render_template('materiais.html', usuario=usuario, lista=lista)


@app.route('/materiais/status/<int:id>/<novo_status>')
@login_required
def atualizar_status_material(id, novo_status):
    usuario = get_usuario_logado()
    if usuario.perfil != 'admin':
        flash('Acesso negado: apenas administradores podem alterar status.', 'danger')
        return redirect(url_for('materiais'))

    solicitacao = SolicitacaoMaterial.query.get_or_404(id)
    status_validos = ['pendente', 'aprovado', 'entregue']
    if novo_status in status_validos:
        solicitacao.status = novo_status
        db.session.commit()
        flash(f'Status atualizado para "{novo_status}" com sucesso!', 'success')
    else:
        flash('Status inválido.', 'danger')

    return redirect(url_for('materiais'))


# ---------------------------------------------------------------------------
# Solicitações de Manutenção
# ---------------------------------------------------------------------------
@app.route('/manutencao', methods=['GET', 'POST'])
@login_required
def manutencao():
    usuario = get_usuario_logado()

    if request.method == 'POST':
        local = request.form.get('local', '').strip()
        descricao = request.form.get('descricao_problema', '').strip()
        urgencia = request.form.get('urgencia', 'media')

        if not local or not descricao:
            flash('Preencha todos os campos do formulário.', 'warning')
        else:
            novo = SolicitacaoManutencao(
                id_usuario=usuario.id,
                local=local,
                descricao_problema=descricao,
                urgencia=urgencia,
                status='aberto'
            )
            db.session.add(novo)
            db.session.commit()
            flash('Chamado de manutenção aberto com sucesso!', 'success')
            return redirect(url_for('manutencao'))

    # Listagem
    if usuario.perfil == 'admin':
        lista = SolicitacaoManutencao.query.order_by(SolicitacaoManutencao.data_criacao.desc()).all()
    else:
        lista = SolicitacaoManutencao.query.filter_by(
            id_usuario=usuario.id).order_by(SolicitacaoManutencao.data_criacao.desc()).all()

    return render_template('manutencao.html', usuario=usuario, lista=lista)


@app.route('/manutencao/status/<int:id>/<novo_status>')
@login_required
def atualizar_status_manutencao(id, novo_status):
    usuario = get_usuario_logado()
    if usuario.perfil != 'admin':
        flash('Acesso negado: apenas administradores podem alterar status.', 'danger')
        return redirect(url_for('manutencao'))

    chamado = SolicitacaoManutencao.query.get_or_404(id)
    status_validos = ['aberto', 'em_andamento', 'concluido']
    if novo_status in status_validos:
        chamado.status = novo_status
        db.session.commit()
        flash(f'Status atualizado para "{novo_status}" com sucesso!', 'success')
    else:
        flash('Status inválido.', 'danger')

    return redirect(url_for('manutencao'))


# ---------------------------------------------------------------------------
# Histórico
# ---------------------------------------------------------------------------
@app.route('/historico')
@login_required
def historico():
    usuario = get_usuario_logado()

    if usuario.perfil == 'admin':
        materiais_entregues = SolicitacaoMaterial.query.filter_by(status='entregue').order_by(
            SolicitacaoMaterial.data_criacao.desc()).all()
        manutencoes_concluidas = SolicitacaoManutencao.query.filter_by(status='concluido').order_by(
            SolicitacaoManutencao.data_criacao.desc()).all()
    else:
        materiais_entregues = SolicitacaoMaterial.query.filter_by(
            id_usuario=usuario.id, status='entregue').order_by(
            SolicitacaoMaterial.data_criacao.desc()).all()
        manutencoes_concluidas = SolicitacaoManutencao.query.filter_by(
            id_usuario=usuario.id, status='concluido').order_by(
            SolicitacaoManutencao.data_criacao.desc()).all()

    return render_template('historico.html',
                           usuario=usuario,
                           materiais_entregues=materiais_entregues,
                           manutencoes_concluidas=manutencoes_concluidas)


# ---------------------------------------------------------------------------
# Ponto de Entrada
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    app.run(debug=True)
