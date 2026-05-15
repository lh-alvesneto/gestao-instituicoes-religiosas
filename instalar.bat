@echo off
title Inicializador do Sistema IPVP
chcp 65001 >nul
color 0F

:: 1. TRAVA DE DIRETÓRIO (Impede erro se rodar como Administrador)
cd /d "%~dp0"

echo ========================================================
echo          INICIALIZADOR AUTOMÁTICO - IPVP
echo ========================================================
echo.

echo [1/5] Verificando o Python no sistema...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    color 0C
    echo [ERRO] Python nao encontrado!
    echo Para rodar o sistema, e necessario ter o Python instalado.
    echo ATENCAO: Durante a instalacao do Python, lembre-se de 
    echo marcar a caixa "Add python.exe to PATH" na primeira tela.
    echo.
    echo Pressione qualquer tecla para abrir o site de download...
    pause >nul
    start https://www.python.org/downloads/
    exit
)
echo OK: Python detectado.
echo.

echo [2/5] Verificando ambiente virtual (venv)...
if not exist "venv\" (
    echo Criando ambiente isolado... Isso pode levar alguns segundos.
    python -m venv venv
)
echo OK: Ambiente virtual pronto.
echo.

echo Ativando ambiente...
call venv\Scripts\activate

echo [3/5] Instalando dependencias essenciais...
python -m pip install --upgrade pip >nul 2>&1
pip install Flask==3.0.3 Flask-SQLAlchemy==3.1.1 Flask-Login==0.6.3 Werkzeug==3.0.3 filetype==1.2.0 Flask-WTF==1.2.1 Flask-Limiter==3.8.0 Flask-Caching==2.3.0 python-dotenv email-validator Flask-Migrate >nul 2>&1
if exist "requirements.txt" (
    pip install -r requirements.txt >nul 2>&1
)
echo OK: Bibliotecas prontas.
echo.

echo [4/5] Configurando variaveis de ambiente...
if not exist ".env" (
    echo FLASK_APP=core> .env
    echo FLASK_DEBUG=1>> .env
    echo SECRET_KEY=chave-dev-secreta-ipvp-2024>> .env
)
set FLASK_APP=core
set FLASK_DEBUG=1
set PYTHONWARNINGS=ignore
echo OK: Variaveis configuradas.
echo.

echo [5/5] Preparando Banco de Dados e Usuario Admin...
:: Cria um script Python temporario para forcar a criacao do admin
echo from core import create_app > setup_db.py
echo from core.extensions import db >> setup_db.py
echo from core.models import Usuario >> setup_db.py
echo app = create_app() >> setup_db.py
echo with app.app_context(): >> setup_db.py
echo     db.create_all() >> setup_db.py
echo     try: >> setup_db.py
echo         from core.models import PerfilUsuario >> setup_db.py
echo         perfil_admin = PerfilUsuario.ADMINISTRADOR >> setup_db.py
echo     except: >> setup_db.py
echo         perfil_admin = 'administrador' >> setup_db.py
echo     from sqlalchemy import select >> setup_db.py
echo     admin = db.session.execute(select(Usuario).filter_by(email='admin@ipvp.com')).scalar_one_or_none() >> setup_db.py
echo     if not admin: >> setup_db.py
echo         admin = Usuario(nome='Administrador', email='admin@ipvp.com', perfil=perfil_admin) >> setup_db.py
echo         admin.set_senha('123456') >> setup_db.py
echo         db.session.add(admin) >> setup_db.py
echo         db.session.commit() >> setup_db.py
python setup_db.py
del setup_db.py

echo OK: Banco de Dados sincronizado.

cls
echo ========================================================
echo   SISTEMA IPVP PRONTO E RODANDO!
echo ========================================================
echo.
echo DADOS DE ACESSO PARA GRAVAR O VIDEO/TESTAR:
echo --------------------------------------------------------
echo E-mail: admin@ipvp.com
echo Senha:  123456
echo --------------------------------------------------------
echo.
echo O seu navegador sera aberto automaticamente em 3 segundos...
echo (Para desligar o servidor, basta fechar esta janela preta)
echo.

timeout /t 3 >nul
start http://127.0.0.1:5000

:: Executa o flask via modulo python para garantir estabilidade
python -m flask run --host=127.0.0.1 --port=5000

pause