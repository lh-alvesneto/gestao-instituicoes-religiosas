"""
=============================================================================
  Script de Inicialização de Banco de Dados
  Arquivo: create_db.py 
=============================================================================
"""

import sys
import json
import random
import argparse
from datetime import datetime, timedelta, timezone

from core import create_app
from core.extensions import db
from core.models import (
    Usuario, SolicitacaoMaterial, SolicitacaoManutencao,
    ComentarioChamado, Auditoria, Anexo
)

app = create_app()

# =============================================================================
# DADOS MOCK (CURADOS PARA APRESENTAÇÃO)
# =============================================================================

NOMES = ["Ana", "Bruno", "Carlos", "Daniela", "Eduardo", "Fernanda", "Gabriel", "Helena", "Lucas", "Mariana"]
SOBRENOMES = ["Silva", "Santos", "Oliveira", "Souza", "Rodrigues", "Ferreira", "Lima", "Costa", "Martins"]

MATERIAIS = [
    "Resma de Papel A4", "Copo Descartável 200ml (Caixa)", "Cartucho de Tinta Preto HP", 
    "Sabonete Líquido 5L", "Papel Toalha Interfolha", "Microfone Dinâmico com Fio", 
    "Cabo XLR 5 metros", "Pilha AA (Caixa)", "Café em Pó 500g", "Açúcar Refinado 1kg",
    "Fita Adesiva Transparente", "Clipes de Papel"
]

LOCAIS = [
    "Salão Principal (Altar)", "Salão Principal (Nave)", "Banheiro Masculino", 
    "Banheiro Feminino", "Cozinha Industrial", "Secretaria", 
    "Sala das Crianças (Kids)", "Sala de Áudio e Vídeo", "Gabinete Pastoral", "Estacionamento"
]

PROBLEMAS = [
    "Ar-condicionado central pingando água.", 
    "Projetor principal com falha na cor vermelha.", 
    "Vazamento na torneira da pia.", 
    "Porta de vidro emperrada, não fecha direito.", 
    "Tomada 220v sem energia perto da mesa de som.", 
    "Cadeira rasgada na fileira do meio.", 
    "Microfone sem fio perdendo sinal frequentemente.", 
    "Lâmpada de LED queimada no corredor.",
    "Ralo entupido voltando cheiro forte.",
    "Fechadura principal com dificuldade para girar a chave."
]

USUARIOS_PADRAO = [
    {'nome': 'Administrador do Sistema', 'email': 'admin@igreja.com', 'senha': 'Admin@2024', 'perfil': 'administrador'},
    {'nome': 'Pr. Carlos Gestor', 'email': 'gestor@igreja.com', 'senha': 'Gestor@123', 'perfil': 'gestor'},
    {'nome': 'João da Silva', 'email': 'joao@igreja.com', 'senha': 'Joao@123', 'perfil': 'usuario'},
    {'nome': 'Maria Souza', 'email': 'maria@igreja.com', 'senha': 'Maria@123', 'perfil': 'usuario'},
]

def obter_agora():
    return datetime.now(timezone.utc)

def gerar_data_aleatoria(dias_atras=30):
    agora = obter_agora()
    segundos_atras = random.randint(0, dias_atras * 24 * 60 * 60)
    return agora - timedelta(seconds=segundos_atras)

def associar_dinamico(obj, nomes_possiveis, valor):
    for attr in nomes_possiveis:
        if hasattr(obj.__class__, attr) or hasattr(obj, attr):
            setattr(obj, attr, valor)
            break

def log_sistema(acao, tabela, registro_id, dados, ator_id, data_hora=None):
    entrada = Auditoria()
    associar_dinamico(entrada, ['id_ator', 'ator_id'], ator_id)
    associar_dinamico(entrada, ['acao'], acao)
    associar_dinamico(entrada, ['tabela_afetada'], tabela)
    associar_dinamico(entrada, ['registro_id'], registro_id)
    associar_dinamico(entrada, ['dados_json'], json.dumps(dados, ensure_ascii=False))
    associar_dinamico(entrada, ['data_hora', 'data', 'criado_em'], data_hora or obter_agora())
    db.session.add(entrada)

def is_gestor_ou_admin(usuario):
    perfil_str = str(getattr(usuario, 'perfil', '')).lower()
    return 'admin' in perfil_str or 'gestor' in perfil_str

def criar_usuarios_massa() -> list:
    print("[INFO] Gerando base de usuários...")
    usuarios_criados = []
    
    for dados in USUARIOS_PADRAO:
        u = Usuario.query.filter_by(email=dados['email']).first()
        if not u:
            u = Usuario()
            associar_dinamico(u, ['nome'], dados['nome'])
            associar_dinamico(u, ['email'], dados['email'])
            associar_dinamico(u, ['perfil'], dados['perfil'])
            u.set_senha(dados['senha'])
            db.session.add(u)
        usuarios_criados.append(u)
    
    db.session.flush()

    for i in range(6):
        nome_completo = f"{random.choice(NOMES)} {random.choice(SOBRENOMES)}"
        email_fake = f"{nome_completo.replace(' ', '.').lower()}@igreja.com"
        
        if not Usuario.query.filter_by(email=email_fake).first():
            perfil = random.choices(['gestor', 'usuario'], weights=[1, 5])[0]
            u = Usuario()
            associar_dinamico(u, ['nome'], nome_completo)
            associar_dinamico(u, ['email'], email_fake)
            associar_dinamico(u, ['perfil'], perfil)
            u.set_senha('Senha@123')
            db.session.add(u)
            usuarios_criados.append(u)
            
    db.session.flush()

    admin_id = usuarios_criados[0].id
    for u in usuarios_criados:
        perfil_str = str(getattr(u, 'perfil', ''))
        log_sistema('CRIOU', 'usuario', u.id, {'email': u.email, 'perfil': perfil_str}, ator_id=admin_id)
        
    print(f"       -> {len(usuarios_criados)} usuários cadastrados.")
    return usuarios_criados

def criar_materiais_massa(usuarios, qtd=25):
    print(f"[INFO] Gerando {qtd} solicitações de materiais...")
    admins_e_gestores = [u for u in usuarios if is_gestor_ou_admin(u)]
    comuns = [u for u in usuarios if not is_gestor_ou_admin(u)]
    
    for i in range(qtd):
        solicitante = random.choice(comuns) if comuns else random.choice(usuarios)
        data_criada = gerar_data_aleatoria()
        
        status_escolhido = random.choices(['pendente', 'aprovado', 'entregue', 'cancelado'], weights=[30, 20, 40, 10])[0]
        responsavel_id = random.choice(admins_e_gestores).id if status_escolhido in ['aprovado', 'entregue'] else None
        justificativa = "Estoque do setor acabou." if status_escolhido != 'cancelado' else "Fiz o pedido duplicado sem querer."
        
        m = SolicitacaoMaterial()
        associar_dinamico(m, ['id_usuario', 'usuario_id'], solicitante.id)
        associar_dinamico(m, ['id_admin_responsavel', 'admin_id'], responsavel_id)
        associar_dinamico(m, ['nome_material', 'material'], random.choice(MATERIAIS))
        associar_dinamico(m, ['quantidade'], random.randint(1, 10))
        associar_dinamico(m, ['justificativa'], justificativa)
        associar_dinamico(m, ['status'], status_escolhido)
        associar_dinamico(m, ['ativo'], True)
        associar_dinamico(m, ['data_criacao', 'data'], data_criada)
        
        db.session.add(m)
        db.session.flush()
        
        log_sistema('CRIOU', 'solicitacao_material', m.id, {'material': getattr(m, 'nome_material', 'Item')}, ator_id=solicitante.id, data_hora=data_criada)
        
        if status_escolhido != 'pendente':
            log_sistema('STATUS_ALTERADO', 'solicitacao_material', m.id, {'para': status_escolhido}, ator_id=responsavel_id or solicitante.id, data_hora=data_criada + timedelta(hours=random.randint(1, 12)))

    print("       -> Concluído.")

def criar_manutencoes_massa(usuarios, qtd=25):
    print(f"[INFO] Gerando {qtd} chamados de manutenção (com histórico visual)...")
    admins_e_gestores = [u for u in usuarios if is_gestor_ou_admin(u)]
    comuns = [u for u in usuarios if not is_gestor_ou_admin(u)]
    
    comentarios_adicionados = 0
    anexos_adicionados = 0

    for i in range(qtd):
        solicitante = random.choice(comuns) if comuns else random.choice(usuarios)
        gestor_resp = random.choice(admins_e_gestores)
        data_criada = gerar_data_aleatoria()
        
        status_escolhido = random.choices(['aberto', 'em_andamento', 'concluido', 'cancelado'], weights=[20, 30, 40, 10])[0]
        urgencia_escolhida = random.choices(['baixa', 'media', 'alta'], weights=[30, 50, 20])[0]
        
        c = SolicitacaoManutencao()
        associar_dinamico(c, ['id_usuario', 'usuario_id'], solicitante.id)
        associar_dinamico(c, ['id_admin_responsavel', 'admin_id'], gestor_resp.id if status_escolhido in ['em_andamento', 'concluido'] else None)
        associar_dinamico(c, ['local'], random.choice(LOCAIS))
        associar_dinamico(c, ['descricao'], random.choice(PROBLEMAS))
        associar_dinamico(c, ['urgencia'], urgencia_escolhida)
        associar_dinamico(c, ['status'], status_escolhido)
        associar_dinamico(c, ['ativo'], True)
        associar_dinamico(c, ['data_criacao', 'data'], data_criada)
        
        db.session.add(c)
        db.session.flush()
        
        log_sistema('CRIOU', 'solicitacao_manutencao', c.id, {'local': getattr(c, 'local', 'Desconhecido')}, ator_id=solicitante.id, data_hora=data_criada)

        def add_comentario(autor_id, texto, delta_horas):
            coment = ComentarioChamado()
            associar_dinamico(coment, ['texto', 'conteudo', 'mensagem'], texto)
            associar_dinamico(coment, ['id_usuario', 'usuario_id', 'autor_id'], autor_id)
            associar_dinamico(coment, ['data_criacao', 'data', 'criado_em', 'data_hora'], data_criada + timedelta(hours=delta_horas))
            associar_dinamico(coment, ['id_chamado', 'id_manutencao', 'solicitacao_manutencao_id'], c.id)
            db.session.add(coment)
            nonlocal comentarios_adicionados
            comentarios_adicionados += 1

        if status_escolhido == 'em_andamento':
            add_comentario(gestor_resp.id, "Recebemos o chamado. A equipe técnica terceirizada foi acionada.", 2)
            if random.choice([True, False]):
                add_comentario(solicitante.id, "Perfeito, estarei no setor para recebê-los.", 3)
                
        elif status_escolhido == 'concluido':
            add_comentario(gestor_resp.id, "Orçamento aprovado. Iniciaremos o reparo.", 5)
            add_comentario(gestor_resp.id, "Serviço finalizado e testado com sucesso.", 48)
            
        elif status_escolhido == 'cancelado':
            add_comentario(gestor_resp.id, "Chamado cancelado por duplicidade.", 1)

        if status_escolhido != 'cancelado':
            for idx in range(random.randint(1, 3)):
                anexo = Anexo()
                img_id = random.randint(10, 200)
                url_img_falsa = f"https://picsum.photos/id/{img_id}/800/600"
                nome_falso = f"foto_ilustrativa_problema_{img_id}.jpg"
                
                associar_dinamico(anexo, ['caminho_arquivo', 'url', 'file_path'], url_img_falsa)
                associar_dinamico(anexo, ['nome_original'], nome_falso)  # <-- Correção do erro AQUI
                associar_dinamico(anexo, ['data_criacao', 'data', 'criado_em'], data_criada + timedelta(minutes=idx*5))
                associar_dinamico(anexo, ['id_chamado', 'id_manutencao', 'solicitacao_manutencao_id', 'registro_id'], c.id)
                associar_dinamico(anexo, ['tabela_origem'], 'solicitacao_manutencao')
                db.session.add(anexo)
                anexos_adicionados += 1

    print(f"       -> Concluído ({comentarios_adicionados} interações e {anexos_adicionados} arquivos processados).")

def imprimir_credenciais():
    print("\n============================================================")
    print(" CREDENCIAIS DE ACESSO PARA TESTE / APRESENTAÇÃO")
    print("============================================================")
    print(f" {'PERFIL':<15} | {'E-MAIL':<20} | {'SENHA'}")
    print("------------------------------------------------------------")
    print(f" {'Administrador':<15} | {'admin@igreja.com':<20} | {'Admin@2024'}")
    print(f" {'Gestor':<15} | {'gestor@igreja.com':<20} | {'Gestor@123'}")
    print(f" {'Usuário Comum':<15} | {'joao@igreja.com':<20} | {'Joao@123'}")
    print("============================================================\n")

def inicializar(reset: bool = False):
    with app.app_context():
        print("\n[INFO] Iniciando configuração do banco de dados ...")
        
        if reset:
            db.drop_all()
            print("[INFO] Banco de dados anterior removido.")

        db.create_all()
        print("[INFO] Estrutura de tabelas criada com sucesso.")

        lista_usuarios = criar_usuarios_massa()
        criar_materiais_massa(lista_usuarios, qtd=25)
        criar_manutencoes_massa(lista_usuarios, qtd=25)

        db.session.commit()
        print("[SUCESSO] Transação finalizada. Banco de dados preparado.")
        
        imprimir_credenciais()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Gerenciador do Banco de Dados SGD")
    parser.add_argument('--reset', action='store_true', help="Apaga e recria todo o banco de dados")
    args = parser.parse_args()
    
    if args.reset:
        confirmacao = input("\n[AVISO] Isso apagará todos os dados atuais. Deseja prosseguir com o reset? (S/N): ")
        if confirmacao.lower() == 's':
            inicializar(reset=True)
        else:
            print("\n[INFO] Operação cancelada.")
    else:
        inicializar(reset=False)