"""
=============================================================================
  Modelos de Dados e Enumerações do Sistema
  Arquivo: models.py 
=============================================================================
"""

import enum
from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from core.extensions import db


class PerfilUsuario(str, enum.Enum):
    USUARIO = 'usuario'
    GESTOR = 'gestor'
    ADMINISTRADOR = 'administrador'


class StatusMaterial(str, enum.Enum):
    PENDENTE = 'pendente'
    APROVADO = 'aprovado'
    ENTREGUE = 'entregue'
    CANCELADO = 'cancelado'


class StatusManutencao(str, enum.Enum):
    ABERTO = 'aberto'
    EM_ANDAMENTO = 'em_andamento'
    CONCLUIDO = 'concluido'
    CANCELADO = 'cancelado'


class UrgenciaManutencao(str, enum.Enum):
    BAIXA = 'baixa'
    MEDIA = 'media'
    ALTA = 'alta'


class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuario'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    senha_hash = db.Column(db.String(256), nullable=False)
    perfil = db.Column(db.Enum(PerfilUsuario), nullable=False, default=PerfilUsuario.USUARIO)
    ativo = db.Column(db.Boolean, default=True, nullable=False)
    data_criacao = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    criado_por_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)

    # Alterado para lazy=True para permitir contagem direta nos templates
    materiais = db.relationship('SolicitacaoMaterial', backref='solicitante', lazy=True, foreign_keys='SolicitacaoMaterial.id_usuario')
    manutencoes = db.relationship('SolicitacaoManutencao', backref='solicitante', lazy=True, foreign_keys='SolicitacaoManutencao.id_usuario')

    def set_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def check_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)

    @property
    def is_admin(self):
        return self.perfil == PerfilUsuario.ADMINISTRADOR

    @property
    def pode_gerenciar(self):
        return self.perfil in [PerfilUsuario.ADMINISTRADOR, PerfilUsuario.GESTOR]

    @property
    def is_usuario(self):
        return self.perfil == PerfilUsuario.USUARIO


class SolicitacaoMaterial(db.Model):
    __tablename__ = 'solicitacao_material'

    id = db.Column(db.Integer, primary_key=True)
    id_usuario = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False, index=True)
    id_admin_responsavel = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    
    nome_material = db.Column(db.String(150), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    justificativa = db.Column(db.Text, nullable=False)
    status = db.Column(db.Enum(StatusMaterial), nullable=False, default=StatusMaterial.PENDENTE)
    ativo = db.Column(db.Boolean, default=True, nullable=False)
    
    data_criacao = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    data_conclusao = db.Column(db.DateTime, nullable=True)

    responsavel = db.relationship('Usuario', foreign_keys=[id_admin_responsavel])
    comentarios = db.relationship('ComentarioChamado', backref='material', lazy=True, cascade='all, delete-orphan', foreign_keys='ComentarioChamado.id_material')


class SolicitacaoManutencao(db.Model):
    __tablename__ = 'solicitacao_manutencao'

    id = db.Column(db.Integer, primary_key=True)
    id_usuario = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False, index=True)
    id_admin_responsavel = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    
    local = db.Column(db.String(150), nullable=False)
    descricao = db.Column(db.Text, nullable=False)
    urgencia = db.Column(db.Enum(UrgenciaManutencao), nullable=False, default=UrgenciaManutencao.BAIXA)
    status = db.Column(db.Enum(StatusManutencao), nullable=False, default=StatusManutencao.ABERTO)
    ativo = db.Column(db.Boolean, default=True, nullable=False)
    
    data_criacao = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    data_conclusao = db.Column(db.DateTime, nullable=True)

    responsavel = db.relationship('Usuario', foreign_keys=[id_admin_responsavel])
    comentarios = db.relationship('ComentarioChamado', backref='manutencao', lazy=True, cascade='all, delete-orphan', foreign_keys='ComentarioChamado.id_manutencao')
    anexos = db.relationship('Anexo', backref='manutencao', lazy=True, cascade='all, delete-orphan')


class Auditoria(db.Model):
    __tablename__ = 'auditoria'

    id = db.Column(db.Integer, primary_key=True)
    id_ator = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True, index=True)
    acao = db.Column(db.String(50), nullable=False)
    tabela_afetada = db.Column(db.String(50), nullable=False)
    registro_id = db.Column(db.Integer, nullable=True)
    dados_json = db.Column(db.Text, nullable=True)
    data_hora = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    ator = db.relationship('Usuario', backref=db.backref('acoes_auditoria', lazy=True))


class ComentarioChamado(db.Model):
    __tablename__ = 'comentario_chamado'
    
    __table_args__ = (
        db.CheckConstraint(
            '(id_material IS NOT NULL AND id_manutencao IS NULL) OR '
            '(id_material IS NULL AND id_manutencao IS NOT NULL)',
            name='check_comentario_alvo'
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    id_material = db.Column(db.Integer, db.ForeignKey('solicitacao_material.id'), nullable=True, index=True)
    id_manutencao = db.Column(db.Integer, db.ForeignKey('solicitacao_manutencao.id'), nullable=True, index=True)
    id_usuario = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False, index=True)
    texto = db.Column(db.Text, nullable=False)
    data_hora = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    caminho_anexo = db.Column(db.String(300), nullable=True)

    autor = db.relationship('Usuario', foreign_keys=[id_usuario])


class Anexo(db.Model):
    __tablename__ = 'anexo'

    id = db.Column(db.Integer, primary_key=True)
    id_chamado = db.Column(db.Integer, db.ForeignKey('solicitacao_manutencao.id'), nullable=False, index=True)
    caminho_arquivo = db.Column(db.String(300), nullable=False)
    nome_original = db.Column(db.String(300), nullable=False)
    tabela_origem = db.Column(db.String(50), default='solicitacao_manutencao')
    data_criacao = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))