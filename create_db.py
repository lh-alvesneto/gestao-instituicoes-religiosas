"""
=============================================================================
  SGD Corporativo — Script de Inicialização do Banco de Dados
  Arquivo: create_db.py

  O que este script faz:
    1. Cria todas as tabelas definidas nos modelos do app.py
    2. Injeta o Administrador Mestre com senha em HASH (Werkzeug)
    3. Cria um Gestor e um Usuário Comum para testes de RBAC
    4. Insere dados de demonstração para apresentação
    5. Registra as criações na tabela de Auditoria

  Como executar:
    python create_db.py

  ATENÇÃO: Este script verifica se o banco já existe.
           Execute com --reset para recriar do zero.
=============================================================================
"""

import sys
import json
from datetime import datetime, timedelta
from app import app, db
from app import (
    Usuario, SolicitacaoMaterial, SolicitacaoManutencao,
    ComentarioChamado, Auditoria, Anexo
)


# =============================================================================
# CONFIGURAÇÃO DOS USUÁRIOS PADRÃO
# =============================================================================

USUARIOS_PADRAO = [
    {
        'nome'   : 'Administrador do Sistema',
        'email'  : 'admin@igreja.com',
        'senha'  : 'Admin@2024',          # Será convertida para hash
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
    """Registra auditoria sem depender do contexto request."""
    entrada = Auditoria(
        id_ator        = ator_id,
        acao           = acao,
        tabela_afetada = tabela,
        registro_id    = registro_id,
        dados_json     = json.dumps(dados, ensure_ascii=False),
    )
    db.session.add(entrada)


def criar_usuarios() -> dict:
    """Cria os usuários padrão com senha em hash. Retorna dicionário {email: objeto}."""
    separador("CRIANDO USUÁRIOS")
    mapa = {}

    for i, dados in enumerate(USUARIOS_PADRAO):
        if Usuario.query.filter_by(email=dados['email']).first():
            print(f"  ⚠  Já existe: {dados['email']} — pulando.")
            mapa[dados['email']] = Usuario.query.filter_by(email=dados['email']).first()
            continue

        u = Usuario(
            nome          = dados['nome'],
            email         = dados['email'],
            perfil        = dados['perfil'],
            criado_por_id = None,   # será ajustado abaixo
        )
        u.set_senha(dados['senha'])
        db.session.add(u)
        db.session.flush()
        mapa[dados['email']] = u
        print(f"  ✓  [{dados['perfil']:15}] {dados['nome']} <{dados['email']}>")

    db.session.flush()

    # Ajusta criado_por_id para rastreabilidade
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

    # Auditoria das criações
    for email, u in mapa.items():
        log_sistema('CRIOU', 'usuario', u.id,
                    {'email': u.email, 'perfil': u.perfil, 'origem': 'seed'},
                    ator_id=admin.id if admin else u.id)

    return mapa


def criar_materiais(mapa: dict):
    """Insere solicitações de material de demonstração."""
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
        ),
        SolicitacaoMaterial(
            id_usuario            = joao.id,
            id_admin_responsavel  = admin.id if admin else None,
            nome_material         = 'Toner HP LaserJet 85A',
            quantidade            = 2,
            justificativa         = 'Toner atual no fim, necessário para manutenção da impressão.',
            status                = 'entregue',
            ativo                 = True,
            data_criacao          = datetime.utcnow() - timedelta(days=20),
        ),
        SolicitacaoMaterial(
            id_usuario            = maria.id,
            id_admin_responsavel  = None,
            nome_material         = 'Garrafa Térmica 1,8L (Inox)',
            quantidade            = 5,
            justificativa         = 'Para servir café durante os cultos de quarta-feira.',
            status                = 'pendente',
            ativo                 = True,
            data_criacao          = datetime.utcnow() - timedelta(days=1),
        ),
    ]

    for m in materiais:
        db.session.add(m)
        db.session.flush()
        log_sistema('CRIOU', 'solicitacao_material', m.id,
                    {'material': m.nome_material, 'origem': 'seed'},
                    ator_id=m.id_usuario)
        print(f"  ✓  [{m.status:10}] {m.nome_material[:45]}")


def criar_manutencoes(mapa: dict):
    """Insere chamados de manutenção de demonstração."""
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
            descricao            = 'Ar-condicionado LG 18000 BTUs não está resfriando. '
                                   'Provavelmente falta de gás ou problema no compressor.',
            urgencia             = 'alta',
            status               = 'aberto',
            ativo                = True,
            data_criacao         = datetime.utcnow() - timedelta(hours=5),
        ),
        SolicitacaoManutencao(
            id_usuario           = maria.id,
            id_admin_responsavel = gestor.id if gestor else admin.id,
            local                = 'Banheiro Feminino — 1º andar',
            descricao            = 'Torneira do lavatório com vazamento constante. '
                                   'Perda de água visível, necessita troca do reparo.',
            urgencia             = 'media',
            status               = 'em_andamento',
            ativo                = True,
            data_criacao         = datetime.utcnow() - timedelta(days=4),
        ),
        SolicitacaoManutencao(
            id_usuario           = joao.id,
            id_admin_responsavel = admin.id if admin else None,
            local                = 'Estacionamento',
            descricao            = 'Dois postes de iluminação com lâmpadas queimadas '
                                   'no setor B do estacionamento.',
            urgencia             = 'baixa',
            status               = 'concluido',
            ativo                = True,
            data_criacao         = datetime.utcnow() - timedelta(days=15),
        ),
        SolicitacaoManutencao(
            id_usuario           = maria.id,
            id_admin_responsavel = None,
            local                = 'Sala de Reuniões 03',
            descricao            = 'Projetor Epson apresentando linha horizontal na imagem. '
                                   'Problema verificado durante a reunião do conselho.',
            urgencia             = 'media',
            status               = 'aberto',
            ativo                = True,
            data_criacao         = datetime.utcnow() - timedelta(days=1),
        ),
    ]

    for c in manutencoes:
        db.session.add(c)
        db.session.flush()
        log_sistema('CRIOU', 'solicitacao_manutencao', c.id,
                    {'local': c.local, 'urgencia': c.urgencia, 'origem': 'seed'},
                    ator_id=c.id_usuario)
        print(f"  ✓  [{c.urgencia:6}] [{c.status:13}] {c.local}")


def criar_comentarios(mapa: dict):
    """Insere comentários de demonstração."""
    separador("CRIANDO COMENTÁRIOS")

    gestor = mapa.get('gestor@igreja.com')
    admin  = mapa.get('admin@igreja.com')

    if not gestor:
        return

    # Chamado em_andamento (id 2) recebe comentário do gestor
    man = SolicitacaoManutencao.query.filter_by(
        local='Banheiro Feminino — 1º andar').first()
    if man:
        c = ComentarioChamado(
            id_chamado   = man.id,
            tipo_chamado = 'manutencao',
            id_usuario   = gestor.id,
            texto        = 'Técnico agendado para amanhã às 09h. '
                           'Peça de reposição já foi adquirida.',
            data_hora    = datetime.utcnow() - timedelta(hours=2),
        )
        db.session.add(c)
        print(f"  ✓  Comentário em [{man.local}] por {gestor.nome}")


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
        criar_comentarios(mapa)

        db.session.commit()

        # ================================================================
        separador("✅  BANCO INICIALIZADO COM SUCESSO")
        # ================================================================
        print(f"""
  Execute o servidor:  python app.py
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

  ATENÇÃO: Senhas armazenadas com hash Werkzeug (pbkdf2:sha256).
        """)


if __name__ == '__main__':
    reset_flag = '--reset' in sys.argv
    inicializar(reset=reset_flag)
