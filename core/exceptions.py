"""
=============================================================================
  Exceções Customizadas do Sistema
  Arquivo: exceptions.py 
=============================================================================
"""

class SistemaErro(Exception):
    pass

class RegraNegocioError(SistemaErro):
    pass

class RegistroNaoEncontradoError(SistemaErro):
    pass