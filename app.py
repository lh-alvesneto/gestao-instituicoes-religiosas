# =============================================================================
#  Sistema de Gestão de Demandas — Instituições Religiosas
#  Versão Corporativa: RBAC + Auditoria + Soft Delete + Upload Seguro
#  Arquivo: app.py
# =============================================================================

import os
import json
from dotenv import load_dotenv
from datetime import datetime
from functools import wraps

from flask import (
    Flask, render_template, redirect, url_for, request,
    session, flash, abort, current_app
)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin, login_user,
    logout_user, login_required, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

load_dotenv()

# =============================================================================
# CONFIGURAÇÃO DA APLICAÇÃO
# =============================================================================
BASE_DIR  = os.path.abspath(os.path.dirname(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'chave-de-emergencia-nao-usar-em-producao')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

@app.template_filter('smart_title')
def smart_title(text):
    if not text:
        return text
    
    excecoes = ['de', 'da', 'do', 'das', 'dos', 'e']
    palavras = text.split()
    resultado = []
    
    for i, palavra in enumerate(palavras):
        palavra_lower = palavra.lower()
        if palavra_lower in excecoes and i > 0:
            resultado.append(palavra_lower)
        else:
            resultado.append(palavra_lower.capitalize())
            
    return ' '.join(resultado)

app.config.update(
    SECRET_KEY              = os.environ.get('SECRET_KEY', 'sgd-chave-secreta-dev-2024'),
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(BASE_DIR, 'demandas.db')}",
    SQLALCHEMY_TRACK_MODIFICATIONS = False,
    UPLOAD_FOLDER           = UPLOAD_DIR,
    MAX_CONTENT_LENGTH      = 5 * 1024 * 1024,   # 5 MB por arquivo
    ALLOWED_EXTENSIONS      = {'png', 'jpg', 'jpeg'},
    MAX_IMAGENS_POR_CHAMADO = 3,
)

# Garante que o diretório de uploads existe na inicialização
os.makedirs(UPLOAD_DIR, exist_ok=True)

db           = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view     = 'login'
login_manager.login_message  = 'Faça login para acessar esta página.'
login_manager.login_message_category = 'warning'


# =============================================================================
# MODELOS — BANCO DE DADOS
# =============================================================================

class Usuario(UserMixin, db.Model):
    """Tabela 1 — Usuários com RBAC de 3 níveis."""
    __tablename__ = 'usuario'

    id             = db.Column(db.Integer, primary_key=True)
    nome           = db.Column(db.String(120), nullable=False)
    email          = db.Column(db.String(150), unique=True, nullable=False)
    senha_hash     = db.Column(db.String(256), nullable=False)
    perfil         = db.Column(
        db.String(20), nullable=False, default='usuario'
    )  # 'administrador' | 'gestor' | 'usuario'
    ativo          = db.Column(db.Boolean, nullable=False, default=True)
    criado_por_id  = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    data_criacao   = db.Column(db.DateTime, default=datetime.utcnow)

    # Relacionamentos internos
    criado_por   = db.relationship('Usuario', remote_side=[id], backref='criados')
    materiais    = db.relationship('SolicitacaoMaterial',    foreign_keys='SolicitacaoMaterial.id_usuario',    backref='solicitante', lazy='dynamic')
    manutencoes  = db.relationship('SolicitacaoManutencao',  foreign_keys='SolicitacaoManutencao.id_usuario',  backref='solicitante', lazy='dynamic')
    comentarios  = db.relationship('ComentarioChamado', backref='autor', lazy='dynamic')
    acoes_audit  = db.relationship('Auditoria', foreign_keys='Auditoria.id_ator', backref='ator', lazy='dynamic')

    # ------------------------------------------------------------------
    # Helpers de senha
    # ------------------------------------------------------------------
    def set_senha(self, senha_plain: str):
        self.senha_hash = generate_password_hash(senha_plain)

    def check_senha(self, senha_plain: str) -> bool:
        return check_password_hash(self.senha_hash, senha_plain)

    # ------------------------------------------------------------------
    # Helpers de papel (RBAC)
    # ------------------------------------------------------------------
    @property
    def is_admin(self):
        return self.perfil == 'administrador'

    @property
    def is_gestor(self):
        return self.perfil == 'gestor'

    @property
    def is_usuario(self):
        return self.perfil == 'usuario'

    @property
    def pode_gerenciar(self):
        """Administrador ou Gestor — podem ver tudo no painel."""
        return self.perfil in ('administrador', 'gestor')

    def __repr__(self):
        return f'<Usuario {self.email} [{self.perfil}]>'


class SolicitacaoMaterial(db.Model):
    """Tabela 2 — Pedidos de material com Soft Delete."""
    __tablename__ = 'solicitacao_material'

    id                    = db.Column(db.Integer, primary_key=True)
    id_usuario            = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    id_admin_responsavel  = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    nome_material         = db.Column(db.String(200), nullable=False)
    quantidade            = db.Column(db.Integer, nullable=False)
    justificativa         = db.Column(db.Text, nullable=False)
    status                = db.Column(
        db.String(20), nullable=False, default='pendente'
    )  # pendente | aprovado | entregue | cancelado
    ativo                 = db.Column(db.Boolean, nullable=False, default=True)
    data_criacao          = db.Column(db.DateTime, default=datetime.utcnow)

    responsavel = db.relationship(
        'Usuario', foreign_keys=[id_admin_responsavel], backref='materiais_gerenciados'
    )
    comentarios = db.relationship(
        'ComentarioChamado',
        primaryjoin="and_(ComentarioChamado.id_chamado==SolicitacaoMaterial.id, "
                    "ComentarioChamado.tipo_chamado=='material')",
        foreign_keys='ComentarioChamado.id_chamado',
        overlaps='comentarios_manutencao,chamado_manutencao',
        lazy='dynamic'
    )


class SolicitacaoManutencao(db.Model):
    """Tabela 3 — Chamados de manutenção com Soft Delete e Uploads."""
    __tablename__ = 'solicitacao_manutencao'

    id                    = db.Column(db.Integer, primary_key=True)
    id_usuario            = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    id_admin_responsavel  = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    local                 = db.Column(db.String(200), nullable=False)
    descricao             = db.Column(db.Text, nullable=False)
    urgencia              = db.Column(
        db.String(10), nullable=False, default='media'
    )  # baixa | media | alta
    status                = db.Column(
        db.String(20), nullable=False, default='aberto'
    )  # aberto | em_andamento | concluido | cancelado
    ativo                 = db.Column(db.Boolean, nullable=False, default=True)
    data_criacao          = db.Column(db.DateTime, default=datetime.utcnow)

    responsavel = db.relationship(
        'Usuario', foreign_keys=[id_admin_responsavel], backref='manutencoes_gerenciadas'
    )
    anexos = db.relationship(
        'Anexo', backref='chamado', lazy='dynamic', cascade='all, delete-orphan'
    )
    comentarios = db.relationship(
        'ComentarioChamado',
        primaryjoin="and_(ComentarioChamado.id_chamado==SolicitacaoManutencao.id, "
                    "ComentarioChamado.tipo_chamado=='manutencao')",
        foreign_keys='ComentarioChamado.id_chamado',
        overlaps='comentarios,solicitante',
        lazy='dynamic'
    )


class Auditoria(db.Model):
    """
    Tabela 4 — Append-Only. NUNCA deletar registros desta tabela.
    Registra toda ação relevante do sistema.
    """
    __tablename__ = 'auditoria'

    id              = db.Column(db.Integer, primary_key=True)
    id_ator         = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    acao            = db.Column(db.String(30), nullable=False)
    # Valores: CRIOU | EDITOU | EXCLUIU | STATUS | LOGIN | LOGOUT | NEGADO
    tabela_afetada  = db.Column(db.String(50), nullable=False)
    registro_id     = db.Column(db.Integer, nullable=True)
    dados_json      = db.Column(db.Text, nullable=True)   # JSON serializado
    data_hora       = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<Auditoria [{self.acao}] em {self.tabela_afetada} #{self.registro_id}>'


class ComentarioChamado(db.Model):
    """
    Tabela 5 — Comentários em chamados bloqueados para edição.
    tipo_chamado: 'material' ou 'manutencao'
    """
    __tablename__ = 'comentario_chamado'

    id           = db.Column(db.Integer, primary_key=True)
    id_chamado   = db.Column(db.Integer, nullable=False)
    tipo_chamado = db.Column(db.String(20), nullable=False)  # material | manutencao
    id_usuario   = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    texto        = db.Column(db.Text, nullable=False)
    data_hora    = db.Column(db.DateTime, default=datetime.utcnow)
    caminho_anexo = db.Column(db.String(300), nullable=True)


class Anexo(db.Model):
    """Tabela 6 — Fotos anexadas a chamados de manutenção."""
    __tablename__ = 'anexo'

    id              = db.Column(db.Integer, primary_key=True)
    id_chamado      = db.Column(db.Integer, db.ForeignKey('solicitacao_manutencao.id'), nullable=False)
    caminho_arquivo = db.Column(db.String(300), nullable=False)
    nome_original   = db.Column(db.String(200), nullable=True)
    data_upload     = db.Column(db.DateTime, default=datetime.utcnow)


# =============================================================================
# FLASK-LOGIN — CARREGADOR DE USUÁRIO
# =============================================================================

@login_manager.user_loader
def load_user(user_id: str):
    return Usuario.query.get(int(user_id))


# =============================================================================
# HELPERS — AUDITORIA
# =============================================================================

def log_auditoria(
    acao: str,
    tabela: str,
    registro_id: int = None,
    dados: dict = None,
    ator_id: int = None
):
    """
    Registra uma entrada na tabela de Auditoria (Append-Only).
    Nunca lança exceção — falha silenciosamente para não quebrar fluxo principal.
    """
    try:
        entrada = Auditoria(
            id_ator        = ator_id or (current_user.id if current_user.is_authenticated else None),
            acao           = acao.upper(),
            tabela_afetada = tabela,
            registro_id    = registro_id,
            dados_json     = json.dumps(dados, ensure_ascii=False, default=str) if dados else None,
        )
        db.session.add(entrada)
        db.session.flush()   # persiste junto ao commit do contexto pai
    except Exception as exc:
        current_app.logger.error(f'[AUDITORIA] Falha ao registrar: {exc}')


# =============================================================================
# HELPERS — UPLOAD
# =============================================================================

def extensao_permitida(filename: str) -> bool:
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    return ext in current_app.config['ALLOWED_EXTENSIONS']


def salvar_arquivo(file_obj) -> str:
    """
    Valida e salva um arquivo de imagem.
    Retorna o nome seguro do arquivo salvo.
    """
    filename = secure_filename(file_obj.filename)
    if not extensao_permitida(filename):
        raise ValueError(f'Tipo de arquivo não permitido: {filename}')
    timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S%f')
    nome_final = f"{timestamp}_{filename}"
    file_obj.save(os.path.join(current_app.config['UPLOAD_FOLDER'], nome_final))
    return nome_final


# =============================================================================
# DECORADORES — RBAC
# =============================================================================

def perfil_requerido(*perfis):
    """
    Decorator que restringe rota a um ou mais perfis RBAC.
    Uso: @perfil_requerido('administrador', 'gestor')
    """
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated(*args, **kwargs):
            if current_user.perfil not in perfis:
                log_auditoria(
                    'NEGADO', 'rota',
                    dados={'url': request.path, 'perfil': current_user.perfil}
                )
                db.session.commit()
                abort(403)
            return f(*args, **kwargs)
        return decorated
    return decorator


def usuario_ativo_requerido(f):
    """Bloqueia usuários inativados que ainda tenham sessão ativa."""
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.ativo:
            logout_user()
            flash('Sua conta foi desativada. Contacte o administrador.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


# =============================================================================
# CONTEXTO GLOBAL — JINJA2
# =============================================================================

@app.context_processor
def inject_globals():
    """Injeta variáveis úteis em todos os templates."""
    pendentes_mat = pendentes_man = 0
    if current_user.is_authenticated and current_user.ativo:
        if current_user.pode_gerenciar:
            pendentes_mat = SolicitacaoMaterial.query.filter_by(
                status='pendente', ativo=True).count()
            pendentes_man = SolicitacaoManutencao.query.filter_by(
                status='aberto', ativo=True).count()
    return dict(
        pendentes_materiais=pendentes_mat,
        pendentes_manutencao=pendentes_man,
        ano_atual=datetime.utcnow().year,
    )


# =============================================================================
# ROTAS — AUTENTICAÇÃO
# =============================================================================

@app.route('/')
def index():
    return redirect(url_for('dashboard') if current_user.is_authenticated else url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        senha = request.form.get('senha', '')

        usuario = Usuario.query.filter_by(email=email).first()

        if usuario and usuario.check_senha(senha):
            if not usuario.ativo:
                flash('Conta inativa. Contacte o administrador.', 'danger')
                log_auditoria('LOGIN', 'usuario', usuario.id,
                              {'motivo': 'conta_inativa'}, usuario.id)
                db.session.commit()
                return redirect(url_for('login'))

            login_user(usuario, remember=False)
            log_auditoria('LOGIN', 'usuario', usuario.id,
                          {'email': email, 'ip': request.remote_addr})
            db.session.commit()

            next_page = request.args.get('next')
            flash(f'Bem-vindo(a), {usuario.nome}!', 'success')
            return redirect(next_page or url_for('dashboard'))

        flash('Credenciais inválidas. Tente novamente.', 'danger')
        log_auditoria('NEGADO', 'login',
                      dados={'email': email, 'ip': request.remote_addr}, ator_id=None)
        db.session.commit()

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    log_auditoria('LOGOUT', 'usuario', current_user.id)
    db.session.commit()
    logout_user()
    flash('Sessão encerrada com segurança.', 'info')
    return redirect(url_for('login'))


# =============================================================================
# ROTAS — DASHBOARD
# =============================================================================

@app.route('/dashboard')
@login_required
@usuario_ativo_requerido
def dashboard():
    u = current_user

    if u.pode_gerenciar:
        # Pega a data do primeiro dia do mês atual para a métrica de produtividade
        hoje = datetime.utcnow()
        inicio_mes = datetime(hoje.year, hoje.month, 1)

        # ---- Contadores KPI Focados na Operação ----
        kpi = {
            # Fila de Trabalho (Ação Imediata)
            'mat_pendente': SolicitacaoMaterial.query.filter_by(status='pendente', ativo=True).count(),
            'man_aberto': SolicitacaoManutencao.query.filter_by(status='aberto', ativo=True).count(),
            'man_alta': SolicitacaoManutencao.query.filter(
                SolicitacaoManutencao.status.in_(['aberto', 'em_andamento']),
                SolicitacaoManutencao.urgencia == 'alta',
                SolicitacaoManutencao.ativo == True
            ).count(),
            
            # Visão Geral (Controle)
            'man_andamento': SolicitacaoManutencao.query.filter_by(status='em_andamento', ativo=True).count(),
            'mat_aprovado': SolicitacaoMaterial.query.filter_by(status='aprovado', ativo=True).count(),
            
            # Produtividade (Entregues/Concluídos no mês atual)
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
        # Usuário comum... (MANTENHA O CÓDIGO ORIGINAL AQUI)
        minhas_mat = SolicitacaoMaterial.query.filter_by(id_usuario=u.id, ativo=True).order_by(SolicitacaoMaterial.data_criacao.desc()).limit(5).all()
        minhas_man = SolicitacaoManutencao.query.filter_by(id_usuario=u.id, ativo=True).order_by(SolicitacaoManutencao.data_criacao.desc()).limit(5).all()
        return render_template('dashboard.html', minhas_mat=minhas_mat, minhas_man=minhas_man)

# =============================================================================
# ROTAS — GESTÃO DE USUÁRIOS (Admin + Gestor)
# =============================================================================

@app.route('/usuarios')
@perfil_requerido('administrador', 'gestor')
@usuario_ativo_requerido
def lista_usuarios():
    # 1. Captura os parâmetros de busca, página e quantidade
    termo = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int) # 10 é o padrão

    # 2. Inicia a query base
    query = Usuario.query.filter_by(ativo=True)

    # 3. Regra RBAC
    if not current_user.is_admin:
        query = query.filter_by(criado_por_id=current_user.id)

    # 4. Aplica o filtro de pesquisa dinâmica
    if termo:
        busca_formatada = f"%{termo}%"
        query = query.filter(
            db.or_(
                Usuario.nome.ilike(busca_formatada),
                Usuario.email.ilike(busca_formatada)
            )
        )

    # 5. Substituímos o .all() pelo .paginate()
    usuarios_paginados = query.order_by(Usuario.nome).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return render_template('usuarios.html', 
                           usuarios=usuarios_paginados, 
                           termo=termo, 
                           per_page=per_page)


@app.route('/usuarios/novo', methods=['GET', 'POST'])
@perfil_requerido('administrador', 'gestor')
@usuario_ativo_requerido
def novo_usuario():
    # Admin pode criar qualquer perfil; Gestor só pode criar 'usuario'
    if current_user.is_admin:
        perfis_disponiveis = ['administrador', 'gestor', 'usuario']
    else:
        perfis_disponiveis = ['usuario']

    if request.method == 'POST':
        nome   = request.form.get('nome', '').strip()
        email  = request.form.get('email', '').strip().lower()
        senha  = request.form.get('senha', '')
        perfil = request.form.get('perfil', 'usuario')

        # Validação RBAC: gestor não pode criar admin/gestor
        if not current_user.is_admin and perfil != 'usuario':
            flash('Você não tem permissão para criar este perfil.', 'danger')
            return redirect(url_for('novo_usuario'))

        if not all([nome, email, senha]):
            flash('Preencha todos os campos obrigatórios.', 'warning')
        elif Usuario.query.filter_by(email=email).first():
            flash('Este e-mail já está cadastrado no sistema.', 'danger')
        else:
            novo = Usuario(
                nome          = nome,
                email         = email,
                perfil        = perfil,
                criado_por_id = current_user.id,
            )
            novo.set_senha(senha)
            db.session.add(novo)
            db.session.flush()   # gera o ID antes do commit

            log_auditoria('CRIOU', 'usuario', novo.id, {
                'nome': nome, 'email': email, 'perfil': perfil,
                'criado_por': current_user.email,
            })
            db.session.commit()
            flash(f'Usuário "{nome}" criado com sucesso.', 'success')
            return redirect(url_for('lista_usuarios'))

    return render_template('form_usuario.html', perfis=perfis_disponiveis)


@app.route('/usuarios/<int:uid>/inativar', methods=['POST'])
@perfil_requerido('administrador', 'gestor')
@usuario_ativo_requerido
def inativar_usuario(uid: int):
    alvo = Usuario.query.get_or_404(uid)

    # Regra: não pode inativar a si mesmo
    if alvo.id == current_user.id:
        flash('Você não pode inativar sua própria conta.', 'warning')
        return redirect(url_for('lista_usuarios'))

    # Regra RBAC: gestor só pode inativar quem ele criou
    if current_user.is_gestor and alvo.criado_por_id != current_user.id:
        abort(403)

    # Admin não pode ser inativado por gestor
    if alvo.is_admin and not current_user.is_admin:
        abort(403)

    alvo.ativo = False
    log_auditoria('EXCLUIU', 'usuario', alvo.id, {
        'email': alvo.email, 'perfil': alvo.perfil,
        'inativado_por': current_user.email,
    })
    db.session.commit()
    flash(f'Usuário "{alvo.nome}" foi inativado.', 'warning')
    return redirect(url_for('lista_usuarios'))


# =============================================================================
# ROTAS — SOLICITAÇÕES DE MATERIAL
# =============================================================================

@app.route('/materiais')
@login_required
@usuario_ativo_requerido
def materiais():
    termo = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)

    u = current_user
    query = SolicitacaoMaterial.query.filter_by(ativo=True)

    # Restringe para usuário comum
    if u.is_usuario:
        query = query.filter_by(id_usuario=u.id)

    # Filtro de Busca Dinâmica (Material ou Solicitante)
    if termo:
        busca_formatada = f"%{termo}%"
        query = query.join(Usuario, SolicitacaoMaterial.id_usuario == Usuario.id).filter(
            db.or_(
                SolicitacaoMaterial.nome_material.ilike(busca_formatada),
                Usuario.nome.ilike(busca_formatada)
            )
        )

    # Paginação em vez de trazer tudo de uma vez
    lista_paginada = query.order_by(SolicitacaoMaterial.data_criacao.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('materiais.html', 
                           lista=lista_paginada, 
                           termo=termo, 
                           per_page=per_page)

@app.route('/materiais/novo', methods=['GET', 'POST'])
@login_required
@usuario_ativo_requerido
def novo_material():
    if request.method == 'POST':
        nome          = request.form.get('nome_material', '').strip()
        quantidade    = request.form.get('quantidade', '').strip()
        justificativa = request.form.get('justificativa', '').strip()

        if not all([nome, quantidade, justificativa]):
            flash('Preencha todos os campos.', 'warning')
        else:
            nova = SolicitacaoMaterial(
                id_usuario    = current_user.id,
                nome_material = nome,
                quantidade    = int(quantidade),
                justificativa = justificativa,
                status        = 'pendente',
                ativo         = True,
            )
            db.session.add(nova)
            db.session.flush()

            log_auditoria('CRIOU', 'solicitacao_material', nova.id, {
                'material': nome, 'qtd': quantidade,
            })
            db.session.commit()
            flash('Solicitação de material enviada!', 'success')
            return redirect(url_for('materiais'))

    return render_template('form_material.html')


@app.route('/materiais/<int:mid>/editar', methods=['GET', 'POST'])
@login_required
@usuario_ativo_requerido
def editar_material(mid: int):
    sol = SolicitacaoMaterial.query.filter_by(id=mid, ativo=True).first_or_404()
    u   = current_user

    # --- REGRA DE NEGÓCIO: Bloqueia edição de estados finais ---
    if sol.status in ['aprovado', 'entregue', 'cancelado']:
        flash('Solicitações aprovadas, entregues ou canceladas não podem ser editadas.', 'warning')
        return redirect(url_for('detalhe_material', mid=mid))

    # Usuário comum: só edita os próprios + status pendente
    if u.is_usuario:
        if sol.id_usuario != u.id:
            abort(403)
        if sol.status != 'pendente':
            flash('Você só pode editar solicitações com status "pendente".', 'warning')
            return redirect(url_for('materiais'))

    if request.method == 'POST':
        justificativa_edicao = request.form.get('justificativa_edicao', '').strip()

        # Admin/Gestor: justificativa de edição obrigatória
        if u.pode_gerenciar and not justificativa_edicao:
            flash('Gestores e Administradores devem informar a justificativa da edição.', 'warning')
            return render_template('form_material.html', sol=sol, editando=True)

        dados_antes = {
            'nome_material': sol.nome_material,
            'quantidade':    sol.quantidade,
            'justificativa': sol.justificativa,
        }

        sol.nome_material = request.form.get('nome_material', sol.nome_material).strip()
        sol.quantidade    = int(request.form.get('quantidade', sol.quantidade))
        sol.justificativa = request.form.get('justificativa', sol.justificativa).strip()

        log_auditoria('EDITOU', 'solicitacao_material', sol.id, {
            'antes': dados_antes,
            'depois': {
                'nome_material': sol.nome_material,
                'quantidade':    sol.quantidade,
                'justificativa': sol.justificativa,
            },
            'justificativa_edicao': justificativa_edicao or 'N/A (usuário comum)',
        })
        db.session.commit()
        flash('Solicitação atualizada com sucesso.', 'success')
        return redirect(url_for('materiais'))

    return render_template('form_material.html', sol=sol, editando=True)

@app.route('/materiais/<int:mid>/status/<novo_status>')
@perfil_requerido('administrador', 'gestor')
@usuario_ativo_requerido
def status_material(mid: int, novo_status: str):
    validos = ('pendente', 'aprovado', 'entregue', 'cancelado')
    if novo_status not in validos:
        abort(400)

    sol = SolicitacaoMaterial.query.filter_by(id=mid, ativo=True).first_or_404()
    status_anterior = sol.status
    sol.status = novo_status
    sol.id_admin_responsavel = current_user.id

    log_auditoria('STATUS', 'solicitacao_material', sol.id, {
        'de': status_anterior, 'para': novo_status,
        'responsavel': current_user.email,
    })
    db.session.commit()
    
    # MUDANÇA AQUI: Dicionário para escolher a cor baseada na ação
    categoria_toast = {
        'pendente': 'warning',   # Amarelo
        'aprovado': 'success',   # Verde
        'entregue': 'success',   # Verde
        'cancelado': 'danger'    # Vermelho
    }
    
    # Pega a cor correspondente (ou 'info' como padrão se algo der errado)
    cor = categoria_toast.get(novo_status, 'info')
    
    flash(f'Status atualizado para "{novo_status.capitalize()}".', cor)
    return redirect(url_for('materiais'))


@app.route('/materiais/<int:mid>/excluir', methods=['POST'])
@login_required
@usuario_ativo_requerido
def excluir_material(mid: int):
    sol = SolicitacaoMaterial.query.filter_by(id=mid, ativo=True).first_or_404()
    u   = current_user

    if u.is_usuario:
        if sol.id_usuario != u.id or sol.status != 'pendente':
            abort(403)

    sol.ativo = False
    log_auditoria('EXCLUIU', 'solicitacao_material', sol.id, {
        'material': sol.nome_material, 'status_antes': sol.status,
    })
    db.session.commit()
    
    # MUDANÇA AQUI: Trocamos 'info' por 'danger' para o Toast ficar vermelho
    flash('Solicitação removida (soft delete).', 'danger')
    return redirect(url_for('materiais'))


@app.route('/materiais/<int:mid>')
@login_required
@usuario_ativo_requerido
def detalhe_material(mid: int):
    sol = SolicitacaoMaterial.query.filter_by(id=mid, ativo=True).first_or_404()
    if current_user.is_usuario and sol.id_usuario != current_user.id:
        abort(403)

    comentarios = ComentarioChamado.query.filter_by(
        id_chamado=mid, tipo_chamado='material'
    ).order_by(ComentarioChamado.data_hora).all()

    return render_template('detalhe_material.html', sol=sol, comentarios=comentarios)


@app.route('/materiais/<int:mid>/comentar', methods=['POST'])
@login_required
@usuario_ativo_requerido
def comentar_material(mid: int):
    sol = SolicitacaoMaterial.query.filter_by(id=mid, ativo=True).first_or_404()
    texto = request.form.get('texto', '').strip()

    if not texto:
        flash('O comentário não pode ser vazio.', 'warning')
        return redirect(url_for('detalhe_material', mid=mid))

    comentario = ComentarioChamado(
        id_chamado   = mid,
        tipo_chamado = 'material',
        id_usuario   = current_user.id,
        texto        = texto,
    )
    db.session.add(comentario)
    db.session.commit()
    flash('Comentário adicionado.', 'success')
    return redirect(url_for('detalhe_material', mid=mid))


# =============================================================================
# ROTAS — CHAMADOS DE MANUTENÇÃO
# =============================================================================

@app.route('/manutencao')
@login_required
@usuario_ativo_requerido
def manutencao():
    termo = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)

    u = current_user
    query = SolicitacaoManutencao.query.filter_by(ativo=True)

    # Restringe para usuário comum
    if u.is_usuario:
        query = query.filter_by(id_usuario=u.id)

    # Filtro de Busca Dinâmica (Local, Descrição ou Solicitante)
    if termo:
        busca_formatada = f"%{termo}%"
        query = query.join(Usuario, SolicitacaoManutencao.id_usuario == Usuario.id).filter(
            db.or_(
                SolicitacaoManutencao.local.ilike(busca_formatada),
                SolicitacaoManutencao.descricao.ilike(busca_formatada),
                Usuario.nome.ilike(busca_formatada)
            )
        )

    # Paginação em vez de trazer tudo de uma vez
    lista_paginada = query.order_by(SolicitacaoManutencao.data_criacao.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('manutencao.html', 
                           lista=lista_paginada, 
                           termo=termo, 
                           per_page=per_page)


@app.route('/manutencao/novo', methods=['GET', 'POST'])
@login_required
@usuario_ativo_requerido
def novo_chamado():
    if request.method == 'POST':
        local    = request.form.get('local', '').strip()
        descricao = request.form.get('descricao', '').strip()
        urgencia  = request.form.get('urgencia', 'media')
        files     = request.files.getlist('imagens')

        if not all([local, descricao]):
            flash('Preencha todos os campos obrigatórios.', 'warning')
            return render_template('form_manutencao.html')

        novo = SolicitacaoManutencao(
            id_usuario = current_user.id,
            local      = local,
            descricao  = descricao,
            urgencia   = urgencia,
            status     = 'aberto',
            ativo      = True,
        )
        db.session.add(novo)
        db.session.flush()  # gera o ID para associar anexos

        # ---- Processamento de uploads ----
        imagens_salvas = []
        arquivos_validos = [f for f in files if f and f.filename]

        if len(arquivos_validos) > current_app.config['MAX_IMAGENS_POR_CHAMADO']:
            flash(f'Máximo de {current_app.config["MAX_IMAGENS_POR_CHAMADO"]} imagens por chamado.', 'warning')
            db.session.rollback()
            return render_template('form_manutencao.html')

        for f in arquivos_validos:
            try:
                nome_salvo = salvar_arquivo(f)
                anexo = Anexo(
                    id_chamado       = novo.id,
                    caminho_arquivo  = nome_salvo,
                    nome_original    = f.filename,
                )
                db.session.add(anexo)
                imagens_salvas.append(nome_salvo)
            except ValueError as exc:
                flash(str(exc), 'danger')
                db.session.rollback()
                return render_template('form_manutencao.html')

        log_auditoria('CRIOU', 'solicitacao_manutencao', novo.id, {
            'local': local, 'urgencia': urgencia,
            'imagens': len(imagens_salvas),
        })
        db.session.commit()
        flash('Chamado de manutenção aberto com sucesso!', 'success')
        return redirect(url_for('manutencao'))

    return render_template('form_manutencao.html')

@app.route('/manutencao/<int:cid>/editar', methods=['GET', 'POST'])
@login_required
@usuario_ativo_requerido
def editar_chamado(cid: int):
    chamado = SolicitacaoManutencao.query.filter_by(id=cid, ativo=True).first_or_404()
    u       = current_user

    # --- REGRA DE NEGÓCIO: Bloqueia andamento e estados finais ---
    if chamado.status in ['em_andamento', 'concluido', 'cancelado']:
        flash('Chamados em andamento ou já finalizados não podem ser editados. Use os comentários.', 'warning')
        return redirect(url_for('detalhe_chamado', cid=cid))

    # Usuário comum: só edita o próprio e quando aberto
    if u.is_usuario:
        if chamado.id_usuario != u.id:
            abort(403)
        if chamado.status != 'aberto':
            flash('Você só pode editar chamados com status "aberto".', 'warning')
            return redirect(url_for('manutencao'))

    if request.method == 'POST':
        justificativa_edicao = request.form.get('justificativa_edicao', '').strip()

        if u.pode_gerenciar and not justificativa_edicao:
            flash('Informe a justificativa da edição.', 'warning')
            return render_template('form_manutencao.html', chamado=chamado, editando=True)

        dados_antes = {
            'local':    chamado.local,
            'descricao': chamado.descricao,
            'urgencia': chamado.urgencia,
        }

        chamado.local     = request.form.get('local', chamado.local).strip()
        chamado.descricao = request.form.get('descricao', chamado.descricao).strip()
        chamado.urgencia  = request.form.get('urgencia', chamado.urgencia)

        # Upload de novas imagens (respeita limite máximo)
        files = request.files.getlist('imagens')
        arquivos_validos = [f for f in files if f and f.filename]
        qtd_atual = chamado.anexos.count()

        if arquivos_validos:
            if qtd_atual + len(arquivos_validos) > current_app.config['MAX_IMAGENS_POR_CHAMADO']:
                flash(
                    f'Limite de {current_app.config["MAX_IMAGENS_POR_CHAMADO"]} imagens atingido. '
                    f'Este chamado já possui {qtd_atual} imagem(ns).', 'warning'
                )
                return render_template('form_manutencao.html', chamado=chamado, editando=True)

            for f in arquivos_validos:
                try:
                    nome_salvo = salvar_arquivo(f)
                    db.session.add(Anexo(
                        id_chamado      = chamado.id,
                        caminho_arquivo = nome_salvo,
                        nome_original   = f.filename,
                    ))
                except ValueError as exc:
                    flash(str(exc), 'danger')
                    return render_template('form_manutencao.html', chamado=chamado, editando=True)

        log_auditoria('EDITOU', 'solicitacao_manutencao', chamado.id, {
            'antes': dados_antes,
            'depois': {'local': chamado.local, 'descricao': chamado.descricao, 'urgencia': chamado.urgencia},
            'justificativa_edicao': justificativa_edicao or 'N/A (usuário comum)',
        })
        db.session.commit()
        flash('Chamado atualizado.', 'success')
        return redirect(url_for('manutencao'))

    return render_template('form_manutencao.html', chamado=chamado, editando=True)


@app.route('/manutencao/<int:cid>/status/<novo_status>')
@perfil_requerido('administrador', 'gestor')
@usuario_ativo_requerido
def status_chamado(cid: int, novo_status: str):
    validos = ('aberto', 'em_andamento', 'concluido', 'cancelado')
    if novo_status not in validos:
        abort(400)

    chamado = SolicitacaoManutencao.query.filter_by(id=cid, ativo=True).first_or_404()
    status_anterior = chamado.status
    chamado.status  = novo_status
    chamado.id_admin_responsavel = current_user.id

    log_auditoria('STATUS', 'solicitacao_manutencao', chamado.id, {
        'de': status_anterior, 'para': novo_status,
        'responsavel': current_user.email,
    })
    db.session.commit()

    # MUDANÇA 1: Dicionário de cores específico para Manutenção
    categoria_toast = {
        'aberto': 'warning',        # Amarelo (Atenção)
        'em_andamento': 'info',     # Azul (Ação ocorrendo)
        'concluido': 'success',     # Verde (Sucesso)
        'cancelado': 'danger'       # Vermelho (Ação destrutiva)
    }
    cor = categoria_toast.get(novo_status, 'info')

    # MUDANÇA 2: Formatação Limpa (Ex: "em_andamento" -> "Em Andamento")
    status_formatado = novo_status.replace('_', ' ').title()

    flash(f'Status atualizado para "{status_formatado}".', cor)
    return redirect(url_for('manutencao'))


@app.route('/manutencao/<int:cid>/excluir', methods=['POST'])
@login_required
@usuario_ativo_requerido
def excluir_chamado(cid: int):
    chamado = SolicitacaoManutencao.query.filter_by(id=cid, ativo=True).first_or_404()
    u       = current_user

    if u.is_usuario:
        if chamado.id_usuario != u.id or chamado.status != 'aberto':
            abort(403)

    chamado.ativo = False   # SOFT DELETE
    log_auditoria('EXCLUIU', 'solicitacao_manutencao', chamado.id, {
        'local': chamado.local, 'status_antes': chamado.status,
    })
    db.session.commit()
    flash('Chamado removido com sucesso.', 'danger')
    return redirect(url_for('manutencao'))


@app.route('/manutencao/<int:cid>')
@login_required
@usuario_ativo_requerido
def detalhe_chamado(cid: int):
    chamado = SolicitacaoManutencao.query.filter_by(id=cid, ativo=True).first_or_404()
    if current_user.is_usuario and chamado.id_usuario != current_user.id:
        abort(403)

    comentarios = ComentarioChamado.query.filter_by(id_chamado=cid, tipo_chamado='manutencao').all()
    auditorias = Auditoria.query.filter_by(tabela_afetada='solicitacao_manutencao', registro_id=cid).all()

    # --- INSERIR ESTAS DUAS LINHAS ---
    timeline_items = comentarios + auditorias
    timeline = sorted(timeline_items, key=lambda x: x.data_hora)
    # ---------------------------------

    return render_template('detalhe_chamado.html', chamado=chamado, timeline=timeline, anexos=chamado.anexos.all())


@app.route('/manutencao/<int:cid>/comentar', methods=['POST'])
@login_required
@usuario_ativo_requerido
def comentar_chamado(cid: int):
    texto = request.form.get('texto', '').strip()
    arquivo = request.files.get('anexo')
    nome_salvo = None

    if arquivo and arquivo.filename:
        nome_salvo = salvar_arquivo(arquivo) # Reaproveitando sua função existente

    db.session.add(ComentarioChamado(
        id_chamado   = cid,
        tipo_chamado = 'manutencao',
        id_usuario   = current_user.id,
        texto        = texto,
        caminho_anexo = nome_salvo # Nova coluna
    ))
    db.session.commit()
    flash('Comentário registrado.', 'success')
    return redirect(url_for('detalhe_chamado', cid=cid))


# =============================================================================
# ROTAS — HISTÓRICO
# =============================================================================

@app.route('/historico')
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

    return render_template('historico.html',
                           mat_historico=mat_historico,
                           man_historico=man_historico)


# =============================================================================
# ROTAS — AUDITORIA (Administrador apenas)
# =============================================================================

@app.route('/auditoria')
@perfil_requerido('administrador')
@usuario_ativo_requerido
def auditoria():
    page    = request.args.get('page', 1, type=int)
    tabela  = request.args.get('tabela', '')
    acao    = request.args.get('acao', '')

    query = Auditoria.query.order_by(Auditoria.data_hora.desc())

    if tabela:
        query = query.filter(Auditoria.tabela_afetada == tabela)
    if acao:
        query = query.filter(Auditoria.acao == acao.upper())

    registros = query.paginate(page=page, per_page=25, error_out=False)

    tabelas_distintas = db.session.query(Auditoria.tabela_afetada).distinct().all()
    acoes_distintas   = db.session.query(Auditoria.acao).distinct().all()

    return render_template('auditoria.html',
                           registros=registros,
                           tabelas=[t[0] for t in tabelas_distintas],
                           acoes=[a[0] for a in acoes_distintas],
                           filtro_tabela=tabela,
                           filtro_acao=acao)


# =============================================================================
# ROTAS — SERVIR ARQUIVOS DE UPLOAD (imagens de manutenção)
# =============================================================================

@app.route('/uploads/<path:filename>')
@login_required
@usuario_ativo_requerido
def serve_upload(filename: str):
    """
    Serve arquivos da pasta de uploads com segurança.
    Apenas usuários autenticados e ativos conseguem acessar.
    Valida que o filename não contém path traversal.
    """
    from flask import send_from_directory
    # Proteção extra: rejeita qualquer tentativa de path traversal
    safe_name = secure_filename(filename)
    if safe_name != filename:
        abort(400)
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], safe_name)


# =============================================================================
# ROTAS — PERFIL DO USUÁRIO (troca de senha)
# =============================================================================

@app.route('/perfil', methods=['GET', 'POST'])
@login_required
@usuario_ativo_requerido
def perfil():
    """Permite que o usuário troque sua própria senha."""
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
            log_auditoria('EDITOU', 'usuario', current_user.id, {
                'acao': 'troca_senha', 'email': current_user.email,
            })
            db.session.commit()
            flash('Senha alterada com sucesso!', 'success')
            return redirect(url_for('perfil'))

    # Últimas ações do usuário na auditoria
    minhas_acoes = (Auditoria.query
                    .filter_by(id_ator=current_user.id)
                    .order_by(Auditoria.data_hora.desc())
                    .limit(10).all())

    return render_template('perfil.html', minhas_acoes=minhas_acoes)


# =============================================================================
# TRATAMENTO DE ERROS
# =============================================================================

@app.errorhandler(403)
def erro_403(e):
    return render_template('erro.html', codigo=403,
                           mensagem='Acesso Negado',
                           detalhe='Você não tem permissão para acessar este recurso.'), 403


@app.errorhandler(404)
def erro_404(e):
    return render_template('erro.html', codigo=404,
                           mensagem='Página Não Encontrada',
                           detalhe='O recurso solicitado não existe ou foi removido.'), 404


@app.errorhandler(413)
def erro_413(e):
    flash('Arquivo muito grande. O tamanho máximo por arquivo é de 5MB.', 'danger')
    return redirect(request.referrer or url_for('manutencao'))


# =============================================================================
# PONTO DE ENTRADA
# =============================================================================

if __name__ == '__main__':
    app.run(debug=True)
