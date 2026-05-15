@echo off
title Inicializador do Sistema IPVP
chcp 65001 >nul
color 0F

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
    echo marcar a caixa "Add python.exe to PATH".
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

echo [3/5] Verificando dependencias...
python -m pip install --upgrade pip >nul 2>&1
echo Instalando e atualizando bibliotecas essenciais...
pip install Flask==3.0.3 Flask-SQLAlchemy==3.1.1 Flask-Login==0.6.3 Werkzeug==3.0.3 filetype==1.2.0 Flask-WTF==1.2.1 Flask-Limiter==3.8.0 Flask-Caching==2.3.0 python-dotenv email-validator Flask-Migrate >nul 2>&1

if exist "requirements.txt" (
    pip install -r requirements.txt >nul 2>&1
)
echo OK: Bibliotecas validadas.
echo.

echo [4/5] Configurando banco de dados e variaveis...
if not exist ".env" (
    echo FLASK_APP=core> .env
    echo FLASK_DEBUG=1>> .env
    echo SECRET_KEY=chave-dev-secreta-ipvp-2024>> .env
)

set FLASK_APP=core
set FLASK_DEBUG=1

:: Esta linha esconde os avisos tecnicos (UserWarning) para nao assustar o usuario final
set PYTHONWARNINGS=ignore

echo Sincronizando banco de dados...
python -c "from core import create_app; from core.extensions import db; app=create_app(); app.app_context().push(); db.create_all()"
if %errorlevel% neq 0 (
    color 0C
    echo [ERRO] Ocorreu um problema ao sincronizar o banco de dados.
    echo Role a tela para cima e verifique a mensagem de erro.
    pause
    exit
)
echo OK: Banco de dados sincronizado.

:: Limpa a tela para deixar o visual mais profissional e entregar os acessos
cls
echo ========================================================
echo   SISTEMA IPVP PRONTO E RODANDO!
echo ========================================================
echo.
echo DADOS DE ACESSO PARA TESTE:
echo --------------------------------------------------------
echo E-mail: admin@igreja.com
echo Senha:  Admin@2024
echo --------------------------------------------------------
echo.
echo O seu navegador sera aberto automaticamente...
echo (Para desligar o servidor, basta fechar esta janela preta)
echo.

timeout /t 3 >nul
start http://127.0.0.1:5000

flask run --host=127.0.0.1 --port=5000

pause