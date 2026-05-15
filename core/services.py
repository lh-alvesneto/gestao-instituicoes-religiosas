"""
=============================================================================
  Lógica de Negócios e Serviços da Aplicação
  Arquivo: services.py 
=============================================================================
"""

import os
from datetime import datetime, timezone

from flask import current_app
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from core.extensions import db
from core.models import (
    Anexo, ComentarioChamado, PerfilUsuario,
    SolicitacaoManutencao, SolicitacaoMaterial, StatusManutencao,
    StatusMaterial, UrgenciaManutencao, Usuario
)
from core.utils import log_auditoria, salvar_arquivo
from core.exceptions import RegraNegocioError, SistemaErro


class GestaoService:

    @staticmethod
    def criar_manutencao(usuario_id: int, dados: dict):
        try:
            urgencia = UrgenciaManutencao(dados['urgencia'])
        except ValueError:
            raise RegraNegocioError("Nível de urgência inválido.")

        arquivos_salvos = []
        sucesso_total = False
        
        try:
            nova = SolicitacaoManutencao(
                id_usuario=usuario_id,
                local=dados['local'],
                descricao=dados['descricao'],
                urgencia=urgencia
            )
            db.session.add(nova)
            db.session.flush()

            for f in [f for f in dados.get('arquivos', []) if f and f.filename]:
                nome_salvo = salvar_arquivo(f, current_app.config['UPLOAD_FOLDER'])
                caminho_absoluto = os.path.join(current_app.config['UPLOAD_FOLDER'], nome_salvo)
                arquivos_salvos.append(caminho_absoluto)
                db.session.add(Anexo(id_chamado=nova.id, caminho_arquivo=nome_salvo, nome_original=f.filename))

            log_auditoria('CRIOU', 'solicitacao_manutencao', nova.id, {'local': nova.local}, ator_id=usuario_id)
            db.session.commit()
            sucesso_total = True
        except Exception as e:
            db.session.rollback()
            if isinstance(e, SQLAlchemyError):
                current_app.logger.exception("[SERVICE] Erro crítico ao criar manutenção")
                raise SistemaErro("Falha interna de banco de dados ao processar a abertura do chamado.") from e
            raise
        finally:
            if not sucesso_total:
                for arquivo_path in arquivos_salvos:
                    if os.path.exists(arquivo_path):
                        os.remove(arquivo_path)

    @staticmethod
    def editar_manutencao(chamado, dados: dict, ator_id: int):
        if (chamado.local == dados['local'] and 
            chamado.descricao == dados['descricao'] and 
            chamado.urgencia.value == dados['urgencia']):
            raise RegraNegocioError("Nenhuma alteração de dados foi detectada para ser salva.")

        try:
            chamado.urgencia = UrgenciaManutencao(dados['urgencia'])
        except ValueError:
            raise RegraNegocioError("Nível de urgência inválido.")

        try:
            antes = {'local': chamado.local, 'urgencia': chamado.urgencia.value, 'descricao': chamado.descricao}
            chamado.local = dados['local']
            chamado.descricao = dados['descricao']
            
            log_auditoria('EDITOU', 'solicitacao_manutencao', chamado.id, {'antes': antes, 'depois': dados}, ator_id=ator_id)
            db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()
            current_app.logger.exception("[SERVICE] Erro crítico ao editar manutenção")
            raise SistemaErro("Erro de banco de dados ao guardar as alterações.") from e

    @staticmethod
    def excluir_manutencao(cid: int, ator_id: int):
        chamado = db.session.get(SolicitacaoManutencao, cid)
        if not chamado or not chamado.ativo:
            raise RegraNegocioError("Chamado não encontrado ou já excluído.")
        try:
            chamado.ativo = False
            log_auditoria('EXCLUIU', 'solicitacao_manutencao', cid, {'local': chamado.local}, ator_id=ator_id)
            db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()
            current_app.logger.exception("[SERVICE] Erro crítico ao excluir manutenção")
            raise SistemaErro("Erro de banco de dados ao tentar excluir.") from e

    @staticmethod
    def comentar_manutencao(id_manutencao: int, id_usuario: int, texto: str, caminho_anexo: str = None):
        try:
            novo = ComentarioChamado(id_manutencao=id_manutencao, id_usuario=id_usuario, texto=texto, caminho_anexo=caminho_anexo)
            db.session.add(novo)
            db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()
            current_app.logger.exception("[SERVICE] Erro crítico ao comentar em manutenção")
            raise SistemaErro("Erro de banco de dados ao gravar comentário.") from e

    @staticmethod
    def alterar_status_manutencao(chamado, novo_status: str, admin_id: int):
        try:
            status_enum = StatusManutencao(novo_status)
        except ValueError:
            raise RegraNegocioError("Status de manutenção inválido fornecido.")

        try:
            status_ant = chamado.status.value if isinstance(chamado.status, StatusManutencao) else chamado.status
            chamado.status = status_enum
            chamado.id_admin_responsavel = admin_id
            
            if status_enum == StatusManutencao.CONCLUIDO and status_ant != StatusManutencao.CONCLUIDO.value:
                chamado.data_conclusao = datetime.now(timezone.utc)
                
            log_auditoria('STATUS', 'solicitacao_manutencao', chamado.id, {'de': status_ant, 'para': status_enum.value}, ator_id=admin_id)
            db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()
            current_app.logger.exception("[SERVICE] Erro crítico ao alterar status de manutenção")
            raise SistemaErro("Erro de banco de dados na atualização de status.") from e
            
    @staticmethod
    def verificar_permissao_acesso_arquivo(filename: str, usuario) -> bool:
        if usuario.pode_gerenciar:
            return True
            
        anexo = db.session.scalar(select(Anexo).filter_by(caminho_arquivo=filename))
        if anexo:
            chamado = db.session.get(SolicitacaoManutencao, anexo.id_chamado)
            return chamado and chamado.id_usuario == usuario.id
            
        comentario = db.session.scalar(select(ComentarioChamado).filter_by(caminho_anexo=filename))
        if comentario and comentario.id_manutencao:
            chamado = db.session.get(SolicitacaoManutencao, comentario.id_manutencao)
            return chamado and chamado.id_usuario == usuario.id
            
        return False

    @staticmethod
    def criar_material(usuario_id: int, dados: dict):
        try:
            nova = SolicitacaoMaterial(
                id_usuario=usuario_id,
                nome_material=dados['nome_material'],
                quantidade=dados['quantidade'],
                justificativa=dados['justificativa']
            )
            db.session.add(nova)
            db.session.flush()
            log_auditoria('CRIOU', 'solicitacao_material', nova.id, {'material': nova.nome_material, 'qtd': nova.quantidade}, ator_id=usuario_id)
            db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()
            current_app.logger.exception("[SERVICE] Erro crítico ao solicitar material")
            raise SistemaErro("Erro de banco de dados ao guardar a solicitação.") from e

    @staticmethod
    def editar_material(solicitacao, dados: dict, ator_id: int):
        if (solicitacao.nome_material == dados['nome_material'] and 
            solicitacao.quantidade == dados['quantidade'] and 
            solicitacao.justificativa == dados['justificativa']):
            raise RegraNegocioError("Nenhuma alteração de dados foi detectada para ser salva.")

        try:
            antes = {'nome': solicitacao.nome_material, 'qtd': solicitacao.quantidade, 'justificativa': solicitacao.justificativa}
            solicitacao.nome_material = dados['nome_material']
            solicitacao.quantidade = dados['quantidade']
            solicitacao.justificativa = dados['justificativa']

            log_auditoria('EDITOU', 'solicitacao_material', solicitacao.id, {
                'antes': antes, 'depois': {'nome': solicitacao.nome_material, 'qtd': solicitacao.quantidade, 'justificativa': solicitacao.justificativa},
                'justificativa_edicao': dados.get('justificativa_edicao', 'N/A')
            }, ator_id=ator_id)
            db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()
            current_app.logger.exception("[SERVICE] Erro crítico ao editar material")
            raise SistemaErro("Erro de banco de dados ao atualizar a solicitação.") from e

    @staticmethod
    def excluir_material(mid: int, ator_id: int):
        sol = db.session.get(SolicitacaoMaterial, mid)
        if not sol or not sol.ativo:
            raise RegraNegocioError("Solicitação não encontrada ou já removida.")
        try:
            sol.ativo = False
            log_auditoria('EXCLUIU', 'solicitacao_material', mid, {'material': sol.nome_material}, ator_id=ator_id)
            db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()
            current_app.logger.exception("[SERVICE] Erro crítico ao excluir material")
            raise SistemaErro("Erro de banco de dados ao tentar remover a solicitação.") from e

    @staticmethod
    def comentar_material(id_material: int, id_usuario: int, texto: str):
        try:
            novo = ComentarioChamado(id_material=id_material, id_usuario=id_usuario, texto=texto)
            db.session.add(novo)
            db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()
            current_app.logger.exception("[SERVICE] Erro crítico ao comentar material")
            raise SistemaErro("Erro de banco de dados ao gravar comentário.") from e

    @staticmethod
    def alterar_status_material(solicitacao, novo_status: str, admin_id: int):
        try:
            status_enum = StatusMaterial(novo_status)
        except ValueError:
            raise RegraNegocioError("Status de material inválido fornecido.")

        try:
            status_ant = solicitacao.status.value if isinstance(solicitacao.status, StatusMaterial) else solicitacao.status
            solicitacao.status = status_enum
            solicitacao.id_admin_responsavel = admin_id
            
            if status_enum == StatusMaterial.ENTREGUE and status_ant != StatusMaterial.ENTREGUE.value:
                solicitacao.data_conclusao = datetime.now(timezone.utc)
                
            log_auditoria('STATUS', 'solicitacao_material', solicitacao.id, {'de': status_ant, 'para': status_enum.value}, ator_id=admin_id)
            db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()
            current_app.logger.exception("[SERVICE] Erro crítico ao alterar status de material")
            raise SistemaErro("Erro de banco de dados na atualização de status.") from e

    @staticmethod
    def criar_usuario(nome, email, senha, perfil_str, ator_logado):
        try:
            perfil = PerfilUsuario(perfil_str)
        except ValueError:
            raise RegraNegocioError("Perfil de usuário inválido fornecido.")

        if perfil == PerfilUsuario.ADMINISTRADOR and not ator_logado.is_admin:
            raise RegraNegocioError("Acesso negado: Apenas administradores podem criar outros administradores.")

        if db.session.execute(db.select(Usuario).filter_by(email=email)).scalar_one_or_none():
            raise RegraNegocioError("Este e-mail já está cadastrado no sistema.")
            
        try:
            novo = Usuario(nome=nome, email=email, perfil=perfil, criado_por_id=ator_logado.id)
            novo.set_senha(senha)
            db.session.add(novo)
            db.session.flush()
            log_auditoria('CRIOU', 'usuario', novo.id, {'nome': nome, 'email': email, 'perfil': perfil.value}, ator_id=ator_logado.id)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            raise RegraNegocioError("Falha de concorrência: Este e-mail já foi registrado por outro utilizador neste instante.")
        except SQLAlchemyError as e:
            db.session.rollback()
            current_app.logger.exception("[SERVICE] Erro crítico ao criar utilizador")
            raise SistemaErro("Erro de banco de dados ao processar o cadastro do utilizador.") from e
            
    @staticmethod
    def alternar_status_usuario(usuario_id: int, admin_id: int):
        if usuario_id == admin_id:
            raise RegraNegocioError("Você não pode desativar a sua própria conta.")
        
        usuario = db.session.get(Usuario, usuario_id)
        if not usuario:
            raise RegraNegocioError("Utilizador não encontrado.")
        
        try:
            status_antigo = usuario.ativo
            usuario.ativo = not usuario.ativo
            acao = 'REATIVOU' if usuario.ativo else 'INATIVOU'
            
            if not usuario.ativo:
                materiais_pendentes = db.session.scalars(select(SolicitacaoMaterial).filter_by(id_usuario=usuario.id, status=StatusMaterial.PENDENTE, ativo=True).with_for_update()).all()
                for mat in materiais_pendentes:
                    mat.status = StatusMaterial.CANCELADO
                    db.session.add(ComentarioChamado(id_material=mat.id, id_usuario=admin_id, texto="Cancelado administrativamente devido à inativação da conta do solicitante."))
                
                manut_pendentes = db.session.scalars(select(SolicitacaoManutencao).filter(SolicitacaoManutencao.id_usuario==usuario.id, SolicitacaoManutencao.status.in_([StatusManutencao.ABERTO, StatusManutencao.EM_ANDAMENTO]), SolicitacaoManutencao.ativo==True).with_for_update()).all()
                for man in manut_pendentes:
                    man.status = StatusManutencao.CANCELADO
                    db.session.add(ComentarioChamado(id_manutencao=man.id, id_usuario=admin_id, texto="Cancelado administrativamente devido à inativação da conta do solicitante."))

            log_auditoria(acao, 'usuario', usuario.id, {'email': usuario.email, 'status_anterior': status_antigo, 'novo_status': usuario.ativo}, ator_id=admin_id)
            db.session.commit()
            return usuario.ativo
        except SQLAlchemyError as e:
            db.session.rollback()
            current_app.logger.exception("[SERVICE] Erro crítico ao alternar status do utilizador")
            raise SistemaErro("Erro de banco de dados ao processar a alteração de estado da conta.") from e