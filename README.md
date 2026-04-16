# SGD — Sistema de Gestão de Demandas
### Versão Corporativa · Instituições Religiosas

> Plataforma web de controle de materiais e manutenção com RBAC de 3 níveis,
> Auditoria Append-Only, Soft Delete total e upload seguro de imagens.

---

## Sumário

1. [Visão Geral](#visão-geral)
2. [Arquitetura e Tecnologias](#arquitetura-e-tecnologias)
3. [Estrutura de Pastas](#estrutura-de-pastas)
4. [Banco de Dados (6 Tabelas)](#banco-de-dados)
5. [Modelo RBAC — 3 Perfis](#modelo-rbac)
6. [Regras de Negócio Críticas](#regras-de-negócio-críticas)
7. [Instalação e Execução](#instalação-e-execução)
8. [Mapa de Rotas](#mapa-de-rotas)
9. [Credenciais de Acesso](#credenciais-de-acesso)
10. [Segurança e Compliance](#segurança-e-compliance)
11. [Decisões de Arquitetura](#decisões-de-arquitetura)

---

## Visão Geral

O SGD é um MVP corporativo que substitui processos manuais (WhatsApp, papel)
por um sistema rastreável com:

- **Controle de Materiais**: abertura, aprovação e entrega de pedidos.
- **Chamados de Manutenção**: abertura com fotos, acompanhamento de status e comentários.
- **Auditoria Completa**: cada ação (login, criação, edição, exclusão, status) é gravada
  em uma tabela Append-Only que nunca pode ser apagada via interface.
- **Soft Delete**: registros nunca são removidos fisicamente. O campo `ativo=False`
  os oculta das listagens sem perder o histórico.

---

## Arquitetura e Tecnologias

| Camada | Tecnologia | Versão |
|---|---|---|
| Back-end | Python + Flask | 3.0.x |
| ORM / Banco | Flask-SQLAlchemy + SQLite | 3.1.x |
| Autenticação | Flask-Login | 0.6.x |
| Hash de senhas | Werkzeug `generate_password_hash` | 3.0.x |
| Upload seguro | Werkzeug `secure_filename` | 3.0.x |
| Front-end | Bootstrap 5.3 + Bootstrap Icons (CDN) | — |
| Templates | Jinja2 (nativo Flask) | — |

---

## Estrutura de Pastas

```
sgd_corp/
│
├── app.py                         # Toda a lógica: config, modelos, rotas (≈1.100 linhas)
├── create_db.py                   # Seed: cria tabelas + usuários com hash
├── requirements.txt               # Dependências pip
├── .gitignore                     # Ignora banco, uploads, venv
│
├── uploads/                       # Fotos de chamados de manutenção (criado automaticamente)
│   └── [timestamp_filename.jpg]
│
└── templates/
    ├── base.html                  # Layout mestre: sidebar + topbar + flash messages
    ├── login.html                 # Split-panel institucional (sem herança de base)
    ├── dashboard.html             # KPIs (admin/gestor) / visão pessoal (usuário)
    │
    ├── materiais.html             # Listagem com dropdown de status inline
    ├── form_material.html         # Criar / editar (c/ justificativa de edição para gestores)
    ├── detalhe_material.html      # Ficha completa + thread de comentários
    │
    ├── manutencao.html            # Listagem com contador de imagens (N/3)
    ├── form_manutencao.html       # Criar / editar + upload múltiplo c/ preview JS
    ├── detalhe_chamado.html       # Ficha + thumbnails clicáveis + comentários
    │
    ├── usuarios.html              # Gestão de usuários (admin/gestor)
    ├── form_usuario.html          # Cadastro com perfis filtrados por RBAC
    │
    ├── perfil.html                # Troca de senha + histórico de ações próprias
    ├── historico.html             # Registros finalizados (entregue/cancelado/concluído)
    ├── auditoria.html             # Log paginado + filtros + JSON expandível (só admin)
    └── erro.html                  # Páginas de erro 403 / 404 estilizadas
```

---

## Banco de Dados

### Tabela 1 — `usuario`
| Campo | Tipo | Descrição |
|---|---|---|
| `id` | Integer PK | — |
| `nome` | String(120) | Nome completo |
| `email` | String(150) UNIQUE | Login único |
| `senha_hash` | String(256) | Hash pbkdf2:sha256 via Werkzeug |
| `perfil` | String(20) | `'administrador'`, `'gestor'`, `'usuario'` |
| `ativo` | Boolean | Soft delete — `False` bloqueia acesso |
| `criado_por_id` | FK → usuario.id | Rastreabilidade de criação |
| `data_criacao` | DateTime | UTC |

### Tabela 2 — `solicitacao_material`
| Campo | Tipo | Descrição |
|---|---|---|
| `id` | Integer PK | — |
| `id_usuario` | FK → usuario | Solicitante |
| `id_admin_responsavel` | FK → usuario | Quem aprovou/entregou |
| `nome_material` | String(200) | — |
| `quantidade` | Integer | — |
| `justificativa` | Text | — |
| `status` | String(20) | `pendente` → `aprovado` → `entregue` / `cancelado` |
| `ativo` | Boolean | Soft delete |
| `data_criacao` | DateTime | UTC |

### Tabela 3 — `solicitacao_manutencao`
| Campo | Tipo | Descrição |
|---|---|---|
| `id` | Integer PK | — |
| `id_usuario` | FK → usuario | Solicitante |
| `id_admin_responsavel` | FK → usuario | Quem assumiu |
| `local` | String(200) | Área física do problema |
| `descricao` | Text | Descrição detalhada |
| `urgencia` | String(10) | `baixa` / `media` / `alta` |
| `status` | String(20) | `aberto` → `em_andamento` → `concluido` / `cancelado` |
| `ativo` | Boolean | Soft delete |
| `data_criacao` | DateTime | UTC |

### Tabela 4 — `auditoria` *(Append-Only)*
| Campo | Tipo | Descrição |
|---|---|---|
| `id` | Integer PK | — |
| `id_ator` | FK → usuario | Quem executou a ação |
| `acao` | String(30) | `CRIOU`, `EDITOU`, `EXCLUIU`, `STATUS`, `LOGIN`, `LOGOUT`, `NEGADO` |
| `tabela_afetada` | String(50) | Nome da tabela alvo |
| `registro_id` | Integer | ID do registro afetado |
| `dados_json` | Text | Snapshot JSON dos dados antes/depois |
| `data_hora` | DateTime | UTC (não alterável) |

> ⚠️ **INVARIANTE**: Nenhuma rota do sistema executa `db.session.delete()` em registros
> desta tabela. A interface de Auditoria é somente leitura.

### Tabela 5 — `comentario_chamado`
| Campo | Tipo | Descrição |
|---|---|---|
| `id` | Integer PK | — |
| `id_chamado` | Integer | ID do chamado (material ou manutenção) |
| `tipo_chamado` | String(20) | `'material'` ou `'manutencao'` |
| `id_usuario` | FK → usuario | Autor do comentário |
| `texto` | Text | Conteúdo |
| `data_hora` | DateTime | UTC |

### Tabela 6 — `anexo`
| Campo | Tipo | Descrição |
|---|---|---|
| `id` | Integer PK | — |
| `id_chamado` | FK → solicitacao_manutencao | — |
| `caminho_arquivo` | String(300) | Nome do arquivo salvo em `/uploads/` |
| `nome_original` | String(200) | Nome original enviado pelo usuário |
| `data_upload` | DateTime | UTC |

---

## Modelo RBAC

```
┌──────────────────────────────────────────────────────────────┐
│                    HIERARQUIA DE ACESSO                      │
├─────────────────┬────────────────────┬───────────────────────┤
│  Administrador  │      Gestor        │       Usuário         │
├─────────────────┼────────────────────┼───────────────────────┤
│ Acesso total    │ Cria usuários      │ Cria/edita próprios   │
│ Cria qualquer   │ Inativa usuários   │ chamados (se aberto/  │
│ perfil          │ que ele criou      │ pendente)             │
│ Inativa todos   │ Aprova materiais   │ Não acessa Auditoria  │
│ (exceto admins) │ Muda status de     │ Não acessa Usuários   │
│ Vê Auditoria    │ chamados           │                       │
│ completa        │                    │                       │
└─────────────────┴────────────────────┴───────────────────────┘
```

### Restrições de edição de chamados

| Situação | Usuário Comum | Gestor/Admin |
|---|---|---|
| Status `pendente` / `aberto` | ✅ Pode editar os próprios | ✅ Pode editar qualquer um (c/ justificativa) |
| Status `em_andamento` | ❌ Bloqueado — usar Comentários | ❌ Bloqueado — usar Comentários |
| Status `concluido` / `cancelado` | ❌ Bloqueado | ❌ Bloqueado |

---

## Regras de Negócio Críticas

### 1. Soft Delete
```python
# CORRETO ✅
registro.ativo = False
log_auditoria('EXCLUIU', 'tabela', registro.id, {...})
db.session.commit()

# PROIBIDO ❌ — nunca usar em produção
db.session.delete(registro)
```

### 2. Auditoria Obrigatória
Toda ação relevante chama `log_auditoria()` **antes** do `db.session.commit()`:
- Login / Logout / Acesso negado
- Criação de qualquer registro
- Edição com snapshot antes/depois
- Mudança de status
- Inativação de usuário

### 3. Upload Seguro
- Apenas extensões: `.png`, `.jpg`, `.jpeg`
- Tamanho máximo: **5MB por arquivo** (`MAX_CONTENT_LENGTH`)
- Máximo de **3 imagens por chamado** (validado no back-end)
- Filename sanitizado com `secure_filename()` antes de salvar
- Servido pela rota autenticada `/uploads/<filename>`

---

## Instalação e Execução

```bash
# 1. Clone ou descompacte o projeto
cd sgd_corp

# 2. Crie e ative um ambiente virtual (recomendado)
python -m venv venv
source venv/bin/activate        # Linux/Mac
venv\Scripts\activate           # Windows

# 3. Instale as dependências
pip install -r requirements.txt

# 4. Crie o banco de dados e popule com dados de demonstração
python create_db.py

# 5. Inicie o servidor de desenvolvimento
python app.py

# Acesse: http://127.0.0.1:5000
```

### Reset completo do banco
```bash
python create_db.py --reset
```

### Variáveis de ambiente (produção)
```bash
export SECRET_KEY="sua-chave-secreta-longa-e-aleatoria"
```

---

## Mapa de Rotas

| Método | Rota | Perfis | Descrição |
|---|---|---|---|
| GET | `/` | — | Redireciona para login ou dashboard |
| GET/POST | `/login` | público | Autenticação |
| GET | `/logout` | autenticado | Encerra sessão |
| GET | `/dashboard` | todos | Painel (KPIs ou visão pessoal) |
| GET | `/materiais` | todos | Listagem de materiais |
| GET/POST | `/materiais/novo` | todos | Nova solicitação |
| GET/POST | `/materiais/<id>/editar` | condicional | Editar solicitação |
| GET | `/materiais/<id>/status/<status>` | admin/gestor | Alterar status |
| POST | `/materiais/<id>/excluir` | condicional | Soft delete |
| GET | `/materiais/<id>` | condicional | Detalhe + comentários |
| POST | `/materiais/<id>/comentar` | todos | Adicionar comentário |
| GET | `/manutencao` | todos | Listagem de chamados |
| GET/POST | `/manutencao/novo` | todos | Novo chamado (c/ upload) |
| GET/POST | `/manutencao/<id>/editar` | condicional | Editar chamado |
| GET | `/manutencao/<id>/status/<status>` | admin/gestor | Alterar status |
| POST | `/manutencao/<id>/excluir` | condicional | Soft delete |
| GET | `/manutencao/<id>` | condicional | Detalhe + imagens + comentários |
| POST | `/manutencao/<id>/comentar` | todos | Adicionar comentário |
| GET | `/historico` | todos | Registros finalizados |
| GET | `/usuarios` | admin/gestor | Lista de usuários |
| GET/POST | `/usuarios/novo` | admin/gestor | Novo usuário |
| POST | `/usuarios/<id>/inativar` | admin/gestor | Inativar (soft delete) |
| GET/POST | `/perfil` | autenticado | Troca de senha + histórico |
| GET | `/auditoria` | admin | Log completo paginado |
| GET | `/uploads/<filename>` | autenticado | Servir imagem de upload |

---

## Credenciais de Acesso

| E-mail | Senha | Perfil | Criado por |
|---|---|---|---|
| `admin@igreja.com` | `Admin@2024` | Administrador | Sistema (seed) |
| `gestor@igreja.com` | `Gestor@123` | Gestor | Admin |
| `joao@igreja.com` | `Joao@123` | Usuário | Gestor |
| `maria@igreja.com` | `Maria@123` | Usuário | Gestor |

> Todas as senhas são armazenadas como hash **pbkdf2:sha256** via Werkzeug.
> Nenhuma senha em texto puro é persisted no banco.

---

## Segurança e Compliance

| Controle | Implementação |
|---|---|
| Autenticação | Flask-Login com `@login_required` e verificação `ativo` em cada request |
| Hash de senhas | `generate_password_hash` / `check_password_hash` (Werkzeug) |
| RBAC | Decorator `@perfil_requerido(*perfis)` composto com `@login_required` |
| Sessão | `SESSION_COOKIE_HTTPONLY=True` (default Flask) |
| Upload | `secure_filename` + whitelist de extensões + tamanho máximo 5MB |
| Path Traversal | Validação `secure_filename(x) == x` na rota `/uploads/<filename>` |
| Soft Delete | Invariante: zero `db.session.delete()` fora da tabela de Auditoria |
| Auditoria | Append-Only: interface não expõe rota de deleção de logs |
| Acesso negado | Registrado na Auditoria com ação `NEGADO` antes do `abort(403)` |

---

## Decisões de Arquitetura

**Por que tudo em `app.py`?**
Para um MVP acadêmico, blueprints adicionam complexidade sem ganho perceptível.
A estrutura está comentada por seções (MODELOS, HELPERS, ROTAS) facilitando
a migração futura para `blueprints/`.

**Por que SQLite?**
Sem necessidade de servidor externo — ideal para apresentação.
A troca para PostgreSQL/MySQL exige apenas alterar `SQLALCHEMY_DATABASE_URI`.

**Por que sem Flask-WTF / CSRF?**
Para não adicionar dependências além do escopo solicitado.
Em produção real, adicionar `flask-wtf` e `WTF_CSRF_ENABLED = True`.

**Por que sem Blueprint de autenticação separado?**
Escopo MVP. A separação seria a próxima etapa de refatoração.
