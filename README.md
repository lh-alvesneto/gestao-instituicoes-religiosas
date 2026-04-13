# Sistema de Gestão de Demandas para Instituições Religiosas
Repositório oficial para o desenvolvimento do Projeto Integrador.
Aplicação web voltada para o controle de compras, solicitações de materiais e serviços de manutenção em instituições religiosas.

## O Problema
Atualmente, o controle de demandas da instituição é feito de maneira informal (comunicação verbal ou WhatsApp). Isso gera falhas de comunicação, duplicidade de solicitações (ex: duas pessoas pedindo o mesmo reparo ou material) e ausência de histórico para a administração.

## A Solução
Um sistema web centralizado (CRUD) onde os membros e colaboradores podem registrar e acompanhar o status de solicitações de materiais (ex: canetas, suprimentos) e pedidos de manutenção (ex: reparos elétricos, remoção de pragas), eliminando o retrabalho e mantendo um histórico organizado.

## Tecnologias Utilizadas
* Front-end: HTML5, CSS3, JavaScript (Bootstrap 5)

* Back-end: Python com Framework Web (Flask) e Jinja2 (Renderização no Servidor)

* Banco de Dados: SQLite

* Controle de Versão: Git e GitHub

## Funcionalidades Principais (Em desenvolvimento)

- [ ] Cadastro e autenticação de usuários

- [x] Formulário de solicitação de compras/materiais

- [x] Formulário de solicitação de manutenção

- [x] Painel de controle para visualização e alteração de status das demandas

- [x] Histórico de serviços concluídos

## Como Executar o Projeto Localmente (Ambiente de Testes) - 2 Maneiras:

### Automático

Este método configura todo o ambiente necessário sem exigir conhecimento técnico de quem está operando o computador.

Dê um duplo clique no arquivo rodar_app.bat localizado na raiz do projeto.

**O script executará o seguinte fluxo de forma automática:**

**Verificação de Ambiente:** Checará se o Python já está instalado na máquina.

**Instalação Autônoma:** Caso o Python não seja encontrado, o script fará o download e a instalação da versão oficial de forma silenciosa via gerenciador de pacotes do Windows (winget). Caso o Windows exiba uma tela solicitando permissão de administrador, clique em "Sim".

**Dependências:** Instalará as bibliotecas necessárias contidas no arquivo requirements.txt.

**Banco de Dados:** Rodará o script de inicialização para garantir que o banco de dados e os usuários de teste existam.

**Inicialização:** Subirá o servidor web e abrirá a aplicação diretamente no seu navegador padrão.

*Nota: Se o script instalar o Python pela primeira vez na sua máquina, ele emitirá um aviso pedindo para você fechar a tela preta e executar o rodar_app.bat mais uma vez para recarregar as variáveis do sistema.**

### Manual

**Pré-requisitos:** Python 3.x instalado na máquina.

1. Abra o terminal na pasta do projeto e instale as dependências:

    pip install -r requirements.txt

2. Inicialize o banco de dados e os usuários de teste (rode apenas na primeira vez ou quando quiser "limpar" o sistema):
   
    python create_db.py

3. Inicie o servidor local:

    python app.py
   
4. Abra o navegador e acesse:

    http://127.0.0.1:5000

## Credenciais de Acesso (Testes):

Admin: admin@igreja.com | Senha: admin
Usuário: user@igreja.com | Senha: 123

## Equipe
* Anderson Aparecido de Almeida
* Davi Garcia Bosso
* Gustavo Nascimento Silva
* Jhonata dos Santos Martins
* Luiz Henrique Alves Neto
* Pedro Ventola
* Phillip Jose Justino
