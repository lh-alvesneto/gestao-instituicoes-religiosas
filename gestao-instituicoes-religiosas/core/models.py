from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

# Importamos as extensões que criámos no passo anterior
from core.extensions import db, login_manager

class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuario'

    id             = db.Column(db.Integer, primary_key=True)
    nome           = db.Column(db.String(120), nullable=False)
    email          = db.Column(db.String(150), unique=True, nullable=False)
    senha_hash     = db.Column(db.String(256), nullable=False)
    perfil         = db.Column(db.String(20), nullable=False, default='usuario')
    ativo          = db.Column(db.Boolean, nullable=False, default=True)
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
    id_usuario            = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    id_admin_responsavel  = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    nome_material         = db.Column(db.String(200), nullable=False)
    quantidade            = db.Column(db.Integer, nullable=False)
    justificativa         = db.Column(db.Text, nullable=False)
    status                = db.Column(db.String(20), nullable=False, default='pendente')
    ativo                 = db.Column(db.Boolean, nullable=False, default=True)
    data_criacao          = db.Column(db.DateTime, default=datetime.utcnow)

    responsavel = db.relationship('Usuario', foreign_keys=[id_admin_responsavel], backref='materiais_gerenciados')
    comentarios = db.relationship(
        'ComentarioChamado',
        primaryjoin="and_(ComentarioChamado.id_chamado==SolicitacaoMaterial.id, ComentarioChamado.tipo_chamado=='material')",
        foreign_keys='ComentarioChamado.id_chamado',
        overlaps='comentarios_manutencao,chamado_manutencao',
        lazy='dynamic'
    )


class SolicitacaoManutencao(db.Model):
    __tablename__ = 'solicitacao_manutencao'

    id                    = db.Column(db.Integer, primary_key=True)
    id_usuario            = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    id_admin_responsavel  = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    local                 = db.Column(db.String(200), nullable=False)
    descricao             = db.Column(db.Text, nullable=False)
    urgencia              = db.Column(db.String(10), nullable=False, default='media')
    status                = db.Column(db.String(20), nullable=False, default='aberto')
    ativo                 = db.Column(db.Boolean, nullable=False, default=True)
    data_criacao          = db.Column(db.DateTime, default=datetime.utcnow)

    responsavel = db.relationship('Usuario', foreign_keys=[id_admin_responsavel], backref='manutencoes_gerenciadas')
    anexos = db.relationship('Anexo', backref='chamado', lazy='dynamic', cascade='all, delete-orphan')
    comentarios = db.relationship(
        'ComentarioChamado',
        primaryjoin="and_(ComentarioChamado.id_chamado==SolicitacaoManutencao.id, ComentarioChamado.tipo_chamado=='manutencao')",
        foreign_keys='ComentarioChamado.id_chamado',
        overlaps='comentarios,solicitante',
        lazy='dynamic'
    )


class Auditoria(db.Model):
    __tablename__ = 'auditoria'

    id              = db.Column(db.Integer, primary_key=True)
    id_ator         = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    acao            = db.Column(db.String(30), nullable=False)
    tabela_afetada  = db.Column(db.String(50), nullable=False)
    registro_id     = db.Column(db.Integer, nullable=True)
    dados_json      = db.Column(db.Text, nullable=True)
    data_hora       = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<Auditoria [{self.acao}] em {self.tabela_afetada} #{self.registro_id}>'


class ComentarioChamado(db.Model):
    __tablename__ = 'comentario_chamado'

    id           = db.Column(db.Integer, primary_key=True)
    id_chamado   = db.Column(db.Integer, nullable=False)
    tipo_chamado = db.Column(db.String(20), nullable=False)
    id_usuario   = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    texto        = db.Column(db.Text, nullable=False)
    data_hora    = db.Column(db.DateTime, default=datetime.utcnow)
    caminho_anexo = db.Column(db.String(300), nullable=True)


class Anexo(db.Model):
    __tablename__ = 'anexo'

    id              = db.Column(db.Integer, primary_key=True)
    id_chamado      = db.Column(db.Integer, db.ForeignKey('solicitacao_manutencao.id'), nullable=False)
    caminho_arquivo = db.Column(db.String(300), nullable=False)
    nome_original   = db.Column(db.String(200), nullable=True)
    data_upload     = db.Column(db.DateTime, default=datetime.utcnow)


@login_manager.user_loader
def load_user(user_id: str):
    return db.session.get(Usuario, int(user_id))