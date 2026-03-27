"""
Script de inicialização do banco de dados.
Cria as tabelas e insere os usuários padrão para testes.

Execute com:
    python create_db.py
"""

from app import app, db, Usuario, SolicitacaoMaterial, SolicitacaoManutencao
from datetime import datetime, timedelta
import random

def criar_banco():
    with app.app_context():
        print("⏳ Criando tabelas no banco de dados...")
        db.create_all()
        print("✅ Tabelas criadas com sucesso!")

        # Verifica se já existem usuários para não duplicar
        if Usuario.query.count() > 0:
            print("⚠️  Banco já possui dados. Pulando inserção de usuários.")
            return

        # ---------------------------------------------------------
        # Cria usuários padrão
        # ---------------------------------------------------------
        admin = Usuario(
            nome='Administrador',
            email='admin@igreja.com',
            senha='admin',
            perfil='admin'
        )

        usuario_comum = Usuario(
            nome='João da Silva',
            email='user@igreja.com',
            senha='123',
            perfil='usuario'
        )

        db.session.add_all([admin, usuario_comum])
        db.session.commit()
        print("✅ Usuários padrão criados:")
        print("   → admin@igreja.com  / senha: admin  (perfil: Admin)")
        print("   → user@igreja.com   / senha: 123    (perfil: Usuário)")

        # ---------------------------------------------------------
        # Dados de demonstração — Materiais
        # ---------------------------------------------------------
        materiais_demo = [
            SolicitacaoMaterial(
                id_usuario=usuario_comum.id,
                nome_material='Resma de Papel A4',
                quantidade=5,
                justificativa='Para impressão dos folhetos do culto dominical.',
                status='pendente',
                data_criacao=datetime.utcnow() - timedelta(days=3)
            ),
            SolicitacaoMaterial(
                id_usuario=usuario_comum.id,
                nome_material='Canetas BIC Azul',
                quantidade=20,
                justificativa='Reposição do estoque do escritório da secretaria.',
                status='aprovado',
                data_criacao=datetime.utcnow() - timedelta(days=7)
            ),
            SolicitacaoMaterial(
                id_usuario=admin.id,
                nome_material='Toner para Impressora HP',
                quantidade=2,
                justificativa='Toner atual está no fim, necessário para manter a impressão.',
                status='entregue',
                data_criacao=datetime.utcnow() - timedelta(days=15)
            ),
        ]

        # ---------------------------------------------------------
        # Dados de demonstração — Manutenção
        # ---------------------------------------------------------
        manutencoes_demo = [
            SolicitacaoManutencao(
                id_usuario=usuario_comum.id,
                local='Salão Principal',
                descricao_problema='Ar-condicionado não está gelando. Possível falta de gás.',
                urgencia='alta',
                status='aberto',
                data_criacao=datetime.utcnow() - timedelta(days=1)
            ),
            SolicitacaoManutencao(
                id_usuario=usuario_comum.id,
                local='Banheiro Feminino',
                descricao_problema='Torneira com vazamento constante.',
                urgencia='media',
                status='em_andamento',
                data_criacao=datetime.utcnow() - timedelta(days=5)
            ),
            SolicitacaoManutencao(
                id_usuario=admin.id,
                local='Estacionamento',
                descricao_problema='Duas lâmpadas do poste de iluminação queimadas.',
                urgencia='baixa',
                status='concluido',
                data_criacao=datetime.utcnow() - timedelta(days=20)
            ),
        ]

        db.session.add_all(materiais_demo + manutencoes_demo)
        db.session.commit()
        print("✅ Dados de demonstração inseridos com sucesso!")
        print("\n🚀 Banco pronto! Execute: python app.py")


if __name__ == '__main__':
    criar_banco()
