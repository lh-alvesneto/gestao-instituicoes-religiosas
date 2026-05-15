"""
=============================================================================
  Inicializador do Sistema
  Arquivo: run.py 
=============================================================================
"""

import os
from core import create_app

app = create_app()

if __name__ == '__main__':
    if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        print("\n============================================================")
        print(" [INFO] Iniciando Sistema de Gestão de Demandas (SGD)...")
        print(" [INFO] Ambiente: DESENVOLVIMENTO (Debug Ativo)")
        print(" [INFO] Acesse no navegador: http://127.0.0.1:5000")
        print(" [AVISO] Pressione CTRL+C no terminal para encerrar.")
        print("============================================================\n")
    
    app.run(debug=True)