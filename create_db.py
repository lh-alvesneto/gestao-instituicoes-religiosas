"""
=============================================================================
  SGD Corporativo — Script de Inicialização do Banco de Dados
  Arquivo: create_db.py (Adaptado para a Arquitetura Modular)
=============================================================================
"""

import sys
import json
import argparse
from datetime import datetime, timedelta

from core import create_app
from core.extensions import db
from core.models import (
    Usuario, SolicitacaoMaterial, SolicitacaoManutencao,
    ComentarioChamado, Auditoria, Anexo
)

# Cria a aplicação para termos o contexto do Flask
app = create_app()

# =============================================================================
# CONFIGURAÇÃO DOS USUÁRIOS PADRÃO
# =============================================================================

USUARIOS_PADRAO = [
    {
        'nome'   : 'Administrador do Sistema',
        'email'  : 'admin@igreja.com',
        'senha'  : 'Admin@2024',
        'perfil' : 'administrador',
    },
    {
        'nome'   : 'Pr. Carlos Gestor',
        'email'  : 'gestor@igreja.com',
        'senha'  : 'Gestor@123',
        'perfil' : 'gestor',
    },
    {
        'nome'   : 'João da Silva',
        'email'  : 'joao@igreja.com',
        'senha'  : 'Joao@123',
        'perfil' : 'usuario',
    },
    {
        'nome'   : 'Maria Souza',
        'email'  : 'maria@igreja.com',
        'senha'  : 'Maria@123',
        'perfil' : 'usuario',
    },
]


def separador(titulo: str):
    print(f"\n{'─' * 60}")
    print(f"  {titulo}")
    print('─' * 60)


def log_sistema(acao, tabela, registro_id, dados, ator_id):
    """Registra auditoria sem depender do contexto de requisição web (para o CLI)."""
    entrada = Auditoria(
        id_ator        = ator_id,
        acao           = acao,
        tabela_afetada = tabela,
        registro_id    = registro_id,
        dados_json     = json.dumps(dados, ensure_ascii=False),
    )
    db.session.add(entrada)


def criar_usuarios() -> dict:
    separador("CRIANDO USUÁRIOS")
    mapa = {}

    for dados in USUARIOS_PADRAO:
        if Usuario.query.filter_by(email=dados['email']).first():
            print(f"  ⚠  Já existe: {dados['email']} — pulando.")
            mapa[dados['email']] = Usuario.query.filter_by(email=dados['email']).first()
            continue

        u = Usuario(
            nome          = dados['nome'],
            email         = dados['email'],
            perfil        = dados['perfil'],
            criado_por_id = None,
        )
        u.set_senha(dados['senha'])
        db.session.add(u)
        db.session.flush()
        mapa[dados['email']] = u
        print(f"  ✓  [{dados['perfil']:15}] {dados['nome']} <{dados['email']}>")

    db.session.flush()

    admin  = mapa.get('admin@igreja.com')
    gestor = mapa.get('gestor@igreja.com')
    joao   = mapa.get('joao@igreja.com')
    maria  = mapa.get('maria@igreja.com')

    if admin and gestor and not gestor.criado_por_id:
        gestor.criado_por_id = admin.id
    if admin and joao and not joao.criado_por_id:
        joao.criado_por_id = gestor.id if gestor else admin.id
    if admin and maria and not maria.criado_por_id:
        maria.criado_por_id = gestor.id if gestor else admin.id

    db.session.flush()

    for email, u in mapa.items():
        log_sistema('CRIOU', 'usuario', u.id,
                    {'email': u.email, 'perfil': u.perfil, 'origem': 'seed'},
                    ator_id=admin.id if admin else u.id)

    return mapa


def criar_materiais(mapa: dict):
    separador("CRIANDO SOLICITAÇÕES DE MATERIAL")

    admin  = mapa.get('admin@igreja.com')
    gestor = mapa.get('gestor@igreja.com')
    joao   = mapa.get('joao@igreja.com')
    maria  = mapa.get('maria@igreja.com')

    if not all([joao, maria]):
        print("  ⚠  Usuários não encontrados. Pulando materiais.")
        return

    materiais = [
        SolicitacaoMaterial(
            id_usuario            = joao.id,
            id_admin_responsavel  = None,
            nome_material         = 'Resma de Papel A4 (500 folhas)',
            quantidade            = 10,
            justificativa         = 'Reposição para impressão de folhetos dominicais.',
            status                = 'pendente',
            ativo                 = True,
            data_criacao          = datetime.utcnow() - timedelta(days=2),
        ),
        SolicitacaoMaterial(
            id_usuario            = maria.id,
            id_admin_responsavel  = gestor.id if gestor else admin.id,
            nome_material         = 'Canetas BIC Azul (caixa c/50)',
            quantidade            = 3,
            justificativa         = 'Reposição do estoque da secretaria.',
            status                = 'aprovado',
            ativo                 = True,
            data_criacao          = datetime.utcnow() - timedelta(days=7),
        )
    ]

    for m in materiais:
        db.session.add(m)
        db.session.flush()
        log_sistema('CRIOU', 'solicitacao_material', m.id,
                    {'material': m.nome_material, 'origem': 'seed'},
                    ator_id=m.id_usuario)
        print(f"  ✓  [{m.status:10}] {m.nome_material[:45]}")


def criar_manutencoes(mapa: dict):
    separador("CRIANDO CHAMADOS DE MANUTENÇÃO")

    admin  = mapa.get('admin@igreja.com')
    gestor = mapa.get('gestor@igreja.com')
    joao   = mapa.get('joao@igreja.com')
    maria  = mapa.get('maria@igreja.com')

    if not all([joao, maria]):
        print("  ⚠  Usuários não encontrados. Pulando manutenções.")
        return

    manutencoes = [
        SolicitacaoManutencao(
            id_usuario           = joao.id,
            id_admin_responsavel = None,
            local                = 'Salão Principal',
            descricao            = 'Ar-condicionado não está resfriando. Falta de gás.',
            urgencia             = 'alta',
            status               = 'aberto',
            ativo                = True,
            data_criacao         = datetime.utcnow() - timedelta(hours=5),
        ),
        SolicitacaoManutencao(
            id_usuario           = maria.id,
            id_admin_responsavel = gestor.id if gestor else admin.id,
            local                = 'Banheiro Feminino — 1º andar',
            descricao            = 'Torneira do lavatório com vazamento constante.',
            urgencia             = 'media',
            status               = 'em_andamento',
            ativo                = True,
            data_criacao         = datetime.utcnow() - timedelta(days=4),
        )
    ]

    for c in manutencoes:
        db.session.add(c)
        db.session.flush()
        log_sistema('CRIOU', 'solicitacao_manutencao', c.id,
                    {'local': c.local, 'urgencia': c.urgencia, 'origem': 'seed'},
                    ator_id=c.id_usuario)
        print(f"  ✓  [{c.urgencia:6}] [{c.status:13}] {c.local}")


def inicializar(reset: bool = False):
    with app.app_context():
        if reset:
            separador("⚠  MODO RESET — APAGANDO BANCO EXISTENTE")
            db.drop_all()
            print("  ✓  Tabelas apagadas.")

        separador("CRIANDO TABELAS")
        db.create_all()
        print("  ✓  Todas as tabelas verificadas/criadas.")

        mapa = criar_usuarios()
        criar_materiais(mapa)
        criar_manutencoes(mapa)

        db.session.commit()

        separador("✅  BANCO INICIALIZADO COM SUCESSO")
        print(f"""
  Execute o servidor:  python run.py
  Acesse em:          http://127.0.0.1:5000

  ┌─────────────────────────────────────────────────────┐
  │  CREDENCIAIS DE ACESSO                              │
  ├──────────────────────────┬──────────────┬───────────┤
  │  E-mail                  │  Senha       │  Perfil   │
  ├──────────────────────────┼──────────────┼───────────┤
  │  admin@igreja.com        │  Admin@2024  │  Admin    │
  │  gestor@igreja.com       │  Gestor@123  │  Gestor   │
  │  joao@igreja.com         │  Joao@123    │  Usuário  │
  │  maria@igreja.com        │  Maria@123   │  Usuário  │
  └──────────────────────────┴──────────────┴───────────┘
        """)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Gerenciador do Banco de Dados SGD")
    parser.add_argument('--reset', action='store_true', help="Apaga e recria todo o banco de dados")
    args = parser.parse_args()
    
    if args.reset:
        confirmacao = input("\nTEM CERTEZA? Isso apagará todos os dados! (s/N): ")
        if confirmacao.lower() == 's':
            inicializar(reset=True)
        else:
            print("Operação cancelada.")
    else:
        # Se rodar sem --reset, ele apenas adiciona o que falta (seguro)
        inicializar(reset=False)