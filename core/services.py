from flask import current_app
from core.extensions import db
from core.models import ComentarioChamado, Usuario
from core.utils import log_auditoria

class GestaoService:
    
    @staticmethod
    def comentar_material(id_material: int, id_usuario: int, texto: str) -> bool:
        try:
            novo_comentario = ComentarioChamado(
                id_material=id_material, 
                id_usuario=id_usuario, 
                texto=texto
            )
            db.session.add(novo_comentario)
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"[MATERIAL] Erro ao gravar comentário: {e}")
            return False

    @staticmethod
    def comentar_manutencao(id_manutencao: int, id_usuario: int, texto: str, caminho_anexo: str = None) -> bool:
        try:
            novo_comentario = ComentarioChamado(
                id_manutencao=id_manutencao, 
                id_usuario=id_usuario, 
                texto=texto,
                caminho_anexo=caminho_anexo
            )
            db.session.add(novo_comentario)
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"[MANUTENÇÃO] Erro ao gravar comentário: {e}")
            return False

    @staticmethod
    def alterar_status_material(solicitacao, novo_status: str, admin_id: int) -> bool:
        STATUS_VALIDOS = {'pendente', 'aprovado', 'entregue', 'cancelado'}
        if novo_status not in STATUS_VALIDOS:
            raise ValueError("Status inválido")
            
        try:
            status_ant = solicitacao.status
            solicitacao.status = novo_status
            solicitacao.id_admin_responsavel = admin_id
            
            log_auditoria('STATUS', 'solicitacao_material', solicitacao.id, {'de': status_ant, 'para': novo_status}, ator_id=admin_id)
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"[MATERIAL] Erro de status: {e}")
            return False

    @staticmethod
    def alterar_status_manutencao(chamado, novo_status: str, admin_id: int) -> bool:
        STATUS_VALIDOS = {'aberto', 'em_andamento', 'concluido', 'cancelado'}
        if novo_status not in STATUS_VALIDOS:
            raise ValueError("Status inválido")
            
        try:
            status_ant = chamado.status
            chamado.status = novo_status
            chamado.id_admin_responsavel = admin_id
            
            log_auditoria('STATUS', 'solicitacao_manutencao', chamado.id, {'de': status_ant, 'para': novo_status}, ator_id=admin_id)
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"[MANUTENÇÃO] Erro de status: {e}")
            return False

    @staticmethod
    def criar_usuario(nome, email, senha, perfil, criador_id) -> tuple:
        """Retorna (sucesso: bool, mensagem: str)"""
        try:
            if Usuario.query.filter_by(email=email).first():
                return False, "Este e-mail já está cadastrado."
            
            novo = Usuario(nome=nome, email=email, perfil=perfil, criado_por_id=criador_id)
            novo.set_senha(senha)
            db.session.add(novo)
            db.session.flush() # Para pegar o ID antes do commit para o log

            log_auditoria('CRIOU', 'usuario', novo.id, {
                'nome': nome, 'email': email, 'perfil': perfil
            }, ator_id=criador_id)
            
            db.session.commit()
            return True, f'Usuário "{nome}" criado com sucesso.'
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"[ADMIN] Erro ao criar usuário: {e}")
            return False, "Erro interno ao processar o cadastro."
            
    @staticmethod
    def alternar_status_usuario(usuario_id: int, admin_id: int) -> tuple:
        """Retorna (sucesso: bool, mensagem: str)"""
        try:
            # Trava de segurança: Não pode inativar a si próprio
            if usuario_id == admin_id:
                return False, "Você não pode desativar sua própria conta."
            
            # Importar Usuario aqui dentro se der erro de circular import, 
            # ou certifique-se de que `from core.models import Usuario` está no topo do ficheiro
            from core.models import Usuario 
            
            usuario = Usuario.query.get(usuario_id)
            if not usuario:
                return False, "Usuário não encontrado."
            
            # Alterna o status booleano (Se True vira False, se False vira True)
            status_antigo = usuario.ativo
            usuario.ativo = not usuario.ativo
            
            acao = 'REATIVOU' if usuario.ativo else 'INATIVOU'
            
            log_auditoria(acao, 'usuario', usuario.id, {
                'email': usuario.email, 
                'status_anterior': status_antigo,
                'novo_status': usuario.ativo
            }, ator_id=admin_id)
            
            db.session.commit() # Fase 3: Commit seguro
            
            verbo = 'reativado' if usuario.ativo else 'inativado'
            return True, f"Usuário {verbo} com sucesso."
            
        except Exception as e:
            db.session.rollback() # Fase 3: Rollback em caso de falha SQL
            current_app.logger.error(f"[ADMIN] Erro ao alternar status do usuário: {e}")
            return False, "Erro interno ao processar a solicitação."
