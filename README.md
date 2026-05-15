# Sistema de Gestão Operacional e Demandas

## Sobre o Projeto
Este sistema web foi desenvolvido como parte do Projeto Integrador da Univesp (Engenharia de Computação / Bacharelado em Tecnologia da Informação / Ciência de Dados) para o polo de São Caetano do Sul.

O objetivo da aplicação é modernizar e centralizar as solicitações administrativas de uma instituição religiosa. Substituindo fluxos informais (como pedidos verbais ou via WhatsApp), o sistema previne duplicidade de demandas, oferece rastreabilidade (SLA e histórico) e facilita o gerenciamento de recursos, manutenções e compras.

## Arquitetura e Tecnologias
O projeto foi construído utilizando a arquitetura MVC adaptada para a web, com separação modular de rotas (Blueprints).
* **Back-end:** Python 3, Flask (Blueprints)
* **Banco de Dados:** SQLite, ORM Flask-SQLAlchemy, Flask-Migrate
* **Segurança e Sessão:** Flask-Login, Flask-WTF (CSRF Protection), Flask-Limiter (Rate Limiting)
* **Performance:** Flask-Caching
* **Front-end:** HTML5, CSS3 Customizado, Jinja2 (Templates), Vanilla JavaScript (AJAX/Fetch API) e Bootstrap 5

## Perfis de Acesso
O sistema possui um controle rigoroso de permissões de acesso:
1. **Colaborador (Usuário Comum):** Pode abrir novos chamados, interagir via comentários, e acompanhar o status das próprias solicitações.
2. **Gestor:** Possui visão ampla para gerenciar as demandas, aprovar/cancelar pedidos e alterar status operacionais, mas com restrições administrativas.
3. **Administrador:** Acesso total ao sistema, incluindo gerenciamento da equipe (ativação/inativação de usuários) e acesso ao painel de rastreabilidade (Auditoria).

## Funcionalidades Principais
* **Gestão de Materiais:** Fluxo completo de aprovação de compras e suprimentos.
* **Gestão de Manutenções:** Abertura de chamados com classificação de urgência (Baixa, Média, Alta), suporte a anexo de imagens e sistema interno de comentários para comunicação com a equipe técnica.
* **Painel de Controle (Dashboard):** Visão estratégica com KPIs, alertas automáticos e contagem de demandas segmentadas por status e urgência.
* **Rastreabilidade e Auditoria:** O sistema possui uma tabela dedicada de auditoria (Log) que registra invisivelmente todas as ações críticas (criação, edição, exclusão e mudança de status), incluindo dados técnicos em JSON e informações do ator da ação.
* **Recursos Assíncronos:** O formulário de manutenção utiliza chamadas API (Fetch) para sugerir locais baseados no histórico do banco de dados (Autocomplete).
* **Exportação de Dados:** Geração de relatórios do histórico operacional no formato CSV.

## Como Executar o Projeto (Ambiente de Testes Windows)
O repositório conta com um script automatizado (`.bat`) planejado para execução _plug-and-play_, ideal para testes locais.

1. Faça o clone deste repositório.
2. Na pasta raiz do projeto, execute o arquivo `iniciar.bat`.
3. O script cuidará automaticamente da:
   - Criação do ambiente virtual (`venv`).
   - Instalação de todas as dependências (`requirements.txt`).
   - Configuração das variáveis de ambiente (`.env`).
   - Criação e sincronização das tabelas no banco de dados SQLite.
4. O navegador será aberto automaticamente na tela de login (`http://127.0.0.1:5000`).
5. As credenciais de teste para o primeiro acesso do administrador serão exibidas diretamente na tela do terminal.

## Equipe de Desenvolvimento
* Anderson Aparecido de Almeida
* Davi Garcia Bosso
* Gustavo Nascimento Silva
* Jhonata dos Santos Martins
* Luiz Henrique Alves Neto
* Pedro Ventola
* Phillip Jose Justino
