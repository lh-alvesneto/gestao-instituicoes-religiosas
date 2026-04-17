from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

# Importamos as extensões
from core.extensions import db, login_manager

class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuario'

    id             = db.Column(db.Integer, primary_key=True)
    nome           = db.Column(db.String(120), nullable=False)
    email          = db.Column(db.String(150), unique=True, nullable=False, index=True)
    senha_hash     = db.Column(db.String(256), nullable=False)
    perfil         = db.Column(db.String(20), nullable=False, default='usuario', index=True)
    ativo          = db.Column(db.Boolean, nullable=False, default=True, index=True)
    criado_por_id  = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    data_criacao   = db.Column(db.DateTime, default=datetime.utcnow)

    criado_por   = db.relationship('Usuario', remote_side=[id], backref='criados')
    materiais    = db.relationship('SolicitacaoMaterial', foreign_keys='SolicitacaoMaterial.id_usuario', backref='solicitante', lazy='dynamic')
    manutencoes  = db.relationship('SolicitacaoManutencao', foreign_keys='SolicitacaoManutencao.id_usuario', backref='solicitante', lazy='dynamic')
    comentarios  = db.relationship('ComentarioChamado', backref='autor', lazy='dynamic')
    acoes_audit  = db.relationship('Auditoria', foreign_keys='Auditoria.id_ator', backref='ator', lazy='dynamic')

    def set_senha(self, senha_plain: str):
        self.senha_hash = generate_password_hash(senha_plain)

    def check_senha(self, senha_plain: str) -> bool:
        return check_password_hash(self.senha_hash, senha_plain)

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
        return self.perfil in ('administrador', 'gestor')

    def __repr__(self):
        return f'<Usuario {self.email} [{self.perfil}]>'


class SolicitacaoMaterial(db.Model):
    __tablename__ = 'solicitacao_material'

    id                    = db.Column(db.Integer, primary_key=True)
    id_usuario            = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False, index=True)
    id_admin_responsavel  = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True, index=True)
    nome_material         = db.Column(db.String(200), nullable=False)
    quantidade            = db.Column(db.Integer, nullable=False)
    justificativa         = db.Column(db.Text, nullable=False)
    status                = db.Column(db.String(20), nullable=False, default='pendente', index=True)
    ativo                 = db.Column(db.Boolean, nullable=False, default=True, index=True)
    data_criacao          = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    responsavel = db.relationship('Usuario', foreign_keys=[id_admin_responsavel], backref='materiais_gerenciados')
    # Relação limpa, sem precisar de foreign_keys ou overlaps
    comentarios = db.relationship('ComentarioChamado', backref='material', lazy='dynamic', cascade='all, delete-orphan')


class SolicitacaoManutencao(db.Model):
    __tablename__ = 'solicitacao_manutencao'

    id                    = db.Column(db.Integer, primary_key=True)
    id_usuario            = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False, index=True)
    id_admin_responsavel  = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True, index=True)
    local                 = db.Column(db.String(200), nullable=False)
    descricao             = db.Column(db.Text, nullable=False)
    urgencia              = db.Column(db.String(10), nullable=False, default='media', index=True)
    status                = db.Column(db.String(20), nullable=False, default='aberto', index=True)
    ativo                 = db.Column(db.Boolean, nullable=False, default=True, index=True)
    data_criacao          = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    responsavel = db.relationship('Usuario', foreign_keys=[id_admin_responsavel], backref='manutencoes_gerenciadas')
    anexos      = db.relationship('Anexo', backref='chamado', lazy='dynamic', cascade='all, delete-orphan')
    # Relação limpa
    comentarios = db.relationship('ComentarioChamado', backref='manutencao', lazy='dynamic', cascade='all, delete-orphan')


class Auditoria(db.Model):
    __tablename__ = 'auditoria'

    id              = db.Column(db.Integer, primary_key=True)
    id_ator         = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True, index=True)
    acao            = db.Column(db.String(30), nullable=False, index=True)
    tabela_afetada  = db.Column(db.String(50), nullable=False, index=True)
    registro_id     = db.Column(db.Integer, nullable=True, index=True)
    dados_json      = db.Column(db.Text, nullable=True)
    data_hora       = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    def __repr__(self):
        return f'<Auditoria [{self.acao}] em {self.tabela_afetada} #{self.registro_id}>'


class ComentarioChamado(db.Model):
    __tablename__ = 'comentario_chamado'
    
    # Garante que o comentário pertence EXATAMENTE a um material OU a uma manutenção
    __table_args__ = (
        db.CheckConstraint(
            '(id_material IS NOT NULL AND id_manutencao IS NULL) OR '
            '(id_material IS NULL AND id_manutencao IS NOT NULL)',
            name='check_comentario_alvo'
        ),
    )

    id            = db.Column(db.Integer, primary_key=True)
    id_material   = db.Column(db.Integer, db.ForeignKey('solicitacao_material.id'), nullable=True, index=True)
    id_manutencao = db.Column(db.Integer, db.ForeignKey('solicitacao_manutencao.id'), nullable=True, index=True)
    id_usuario    = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False, index=True)
    texto         = db.Column(db.Text, nullable=False)
    data_hora     = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    caminho_anexo = db.Column(db.String(300), nullable=True)


class Anexo(db.Model):
    __tablename__ = 'anexo'

    id              = db.Column(db.Integer, primary_key=True)
    id_chamado      = db.Column(db.Integer, db.ForeignKey('solicitacao_manutencao.id'), nullable=False, index=True)
    caminho_arquivo = db.Column(db.String(300), nullable=False)
    nome_original   = db.Column(db.String(200), nullable=True)
    data_upload     = db.Column(db.DateTime, default=datetime.utcnow)


# Regista o carregador de utilizador no Flask-Login (Atualizado para SQLAlchemy 2.0)
@login_manager.user_loader
def load_user(user_id: str):
    return db.session.get(Usuario, int(user_id))