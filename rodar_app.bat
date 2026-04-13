@echo off
color 0A
echo ===================================================
echo     SISTEMA DE GESTAO DE DEMANDAS - INICIALIZADOR
echo ===================================================
echo.

:: 1. Verifica se o Python está instalado
echo [1/4] Verificando Python no sistema...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    color 0E
    echo.
    echo [AVISO] Python nao foi encontrado neste computador.
    echo Iniciando instalacao automatica via Winget...
    echo.
    echo Por favor, aguarde. Se o Windows pedir permissao, clique em SIM.
    echo.
    
    :: Winget instala Python aceitando os termos.
    winget install --id=Python.Python.3.12 -e --source winget --accept-package-agreements --accept-source-agreements
    
    color 0C
    echo.
    echo ===================================================
    echo INSTALACAO DO PYTHON CONCLUIDA!
    echo.
    echo O Windows precisa recarregar as variaveis de sistema.
    echo FECHE ESTA JANELA e de dois cliques neste script novamente.
    echo ===================================================
    pause
    exit /b
)
echo Python encontrado com sucesso!
echo.

:: 2. Instala dependências (se faltar alguma)
echo [2/4] Verificando e instalando dependencias (Flask, SQLAlchemy)...
pip install -r requirements.txt -q
echo Dependencias OK!
echo.

:: 3. Verifica/Cria Banco de Dados
echo [3/4] Preparando banco de dados...
python create_db.py
echo.

:: 4. Inicia o Servidor
echo [4/4] Iniciando o servidor web...
echo.
echo O sistema sera aberto no seu navegador. 
echo NAO FECHE ESTA JANELA enquanto estiver usando o sistema!
echo.
timeout /t 3 >nul
start http://127.0.0.1:5000
python app.py

pause