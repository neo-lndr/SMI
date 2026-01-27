"""
Gerenciamento simples de arquivos temporários e JSON.
Propósito:
    Gerenciar operações básicas de I/O para arquivos temporários do módulo,
    com foco em leitura/escrita de JSON e limpeza do diretório temporário.
Responsabilidades principais:
    - Criar e garantir existência de um diretório temporário local ao módulo.
    - Verificar existência de arquivos dentro do diretório temporário.
    - Carregar e salvar dados no formato JSON com tratamento básico de erros.
    - Limpar arquivos temporários do diretório quando necessário.
Posição na arquitetura:
    Componente utilitário de infraestrutura/local I/O utilizado por camadas de
    aplicação ou serviços que precisam persistir temporariamente dados no
    filesystem local. Não é responsável por persistência durável de longo prazo
    nem por sincronização entre nós.
Dependências críticas:
    - pathlib.Path: manipulação de caminhos e operações no filesystem.
    - json: serialização e desserialização de dados JSON.
    - logging: relatório e registro de eventos e erros.
    - Permissões do sistema de arquivos para criar, ler, escrever e remover arquivos no diretório calculado (Path(__file__).parent / "temp").
Considerações de segurança:
    - Dados sensíveis não devem ser salvos em texto simples neste diretório,
      pois não há criptografia ou controle de acesso adicional.
    - Garantir permissões corretas no diretório temporário para evitar acesso indevido por outros processos/usuários.
Exemplo de uso básico:
    logger = getLogger("app")
    fm = FileManager(logger)
    # Salvar dados
    fm.save_json("exemplo.json", {"chave": "valor"})
    # Verificar existência
    if fm.check_file_exists("exemplo.json"):
        dados = fm.load_json("exemplo.json")
    # Limpar arquivos temporários
    fm.clear_temp_files()
"""

import json
import logging
from pathlib import Path
from typing import Any

class FileManager:
    """
    Execução de operações de I/O de arquivos.
    """
    
    def __init__(self):
        # Inicializa o gerenciador de arquivos com um logger e um caminho para arquivos temporários
        self.logger = logging.getLogger(__name__)
        self.path = f"{Path(__file__).parent}/temp"
        # Cria o diretório temporário se não existir
        Path(self.path).mkdir(exist_ok=True)

    def check_file_exists(self, filename: str) -> bool:
        """
        Verifica se um arquivo existe no caminho especificado
        """
        file_path = Path(f"{self.path}/{filename}")
        exists = file_path.is_file()
        if exists:
            self.logger.info(f"Arquivo {file_path} existe.")
        else:
            self.logger.warning(f"Arquivo {file_path} não encontrado.")
        return exists

    def load_json(self, filename: str) -> dict[str, Any]:
        """
        Carrega dados JSON de um arquivo
        """
        try:
            # Abre e lê o arquivo JSON
            with open(f"{self.path}/{filename}", 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Falha ao carregar JSON de {self.path}/{filename}: {e}")
            raise

    def save_json(self, file_name: str, data: Any) -> None:
        """
        Salva dados em um arquivo JSON
        Parâmetros:
            data (Any): Os dados a serem salvos em formato JSON
        """
        try:
            # Abre o arquivo para escrita e salva os dados em formato JSON
            with open(f"{self.path}/{file_name}", 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"Falha ao salvar JSON em {self.path}/{file_name}: {e}")
            raise

    def clear_temp_files(self) -> None:
        """
        Limpa arquivos temporários no diretório especificado
        """
        try:
            temp_dir = Path(self.path)
            if temp_dir.exists() and temp_dir.is_dir():
                for temp_file in temp_dir.iterdir():
                    if temp_file.is_file():
                        temp_file.unlink()
                self.logger.info(f"Arquivos temporários em {self.path} foram limpos.")
            else:
                self.logger.warning(f"O diretório {self.path} não existe ou não é um diretório.")
        except Exception as e:
            self.logger.error(f"Falha ao limpar arquivos temporários em {self.path}: {e}")
            raise

    def clear_temp_engine_files(self) -> None:
        """
        Limpa arquivos temporários no diretório especificado
        """
        try:
            temp_dir = Path(self.path)
            if temp_dir.exists() and temp_dir.is_dir():
                for temp_file in temp_dir.iterdir():
                    if temp_file.is_file():
                        if (("all_doctype_data_" in temp_file.name) or 
                            ("contract_data_" in temp_file.name) or 
                            ("engine_result_" in temp_file.name) or
                            ("enriched_data_" in temp_file.name)):
                            temp_file.unlink()
                self.logger.info(f"Arquivos temporários em {self.path} foram limpos.")
            else:
                self.logger.warning(f"O diretório {self.path} não existe ou não é um diretório.")
        except Exception as e:
            self.logger.error(f"Falha ao limpar arquivos temporários em {self.path}: {e}")
            raise        