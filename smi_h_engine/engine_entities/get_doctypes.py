"""
Processamento de DocTypes
Propósito:
    Fornecer utilitários para recuperar, processar e persistir metadados e instâncias de DocTypes do
    Frappe Framework (via API Arteris/SmiApi), construindo uma representação hierárquica das entidades
    e seus relacionamentos pai-filho. Suporta também a serialização local dessas estruturas e dados.
Responsabilidades principais:
    - Recuperar listas de DocTypes (principais e filhos) e seus campos via SmiApi (integração com Frappe).
    - Filtrar e normalizar campos, extrair mapeamentos pai-filho e construir uma árvore hierárquica de entidades.
    - Recuperar dados reais (registros) de DocTypes, aplicar filtros e salvar resultados em JSON local.
    - Gerenciar operações de I/O para persistência (criação/limpeza de diretórios, normalização de nomes de arquivos).
Posição na arquitetura:
    - Camada de integração/ETL entre a API Arteris (SmiApi) — que expõe metadados e dados do Frappe Framework —
      e consumidores internos que precisam de uma visão estruturada dos DocTypes (por exemplo, geradores de
      relatórios, migração de dados, ou sincronizadores).
    - Atua como adaptador que traduz conceitos do Frappe (DocType, DocField, relações Table) para uma representação
      serializável e navegável (árvore hierárquica) usada por outras partes do sistema.
Dependências críticas:
    - Frappe Framework (modelo conceitual: DocType, DocField, chaves e endpoints de consulta) — acessado via SmiApi.
    - SmiApi: cliente que implementa as chamadas HTTP para obter doctypes, docfields, chaves e dados.
    - HierarchicalTreeBuilder: construtor da representação hierárquica a partir da estrutura e dos dados.
    - Módulos utilitários locais: EngineDataBuilder, e funcionalidades de sistema de arquivos.
    - Python stdlib: os, json, shutil, unicodedata, re, I/O e logging.
Considerações de segurança:
    - Controle e proteção de credenciais: as credenciais usadas por SmiApi não devem ser commitadas no repositório;
      usar variáveis de ambiente ou cofre de segredos.
    - Permissões de arquivos: diretórios e arquivos JSON gerados podem conter dados sensíveis; garantir permissões
      adequadas ao gravar (restrictive file modes) e rotacionar logs/dumps conforme necessário.
    - Tratamento de erros e resiliência: a comunicação com a API deve tratar timeouts, limitação de taxa (rate limit)
      e falhas parciais sem expor dados sensíveis em logs.
    - Normalização e limpeza de nomes de arquivos: evita path traversal e caracteres inválidos ao salvar dados localmente.
Exemplo de uso básico:
    from get_doctypes import DoctypeProcessor
    dp = DoctypeProcessor()
    # Recupera apenas a estrutura hierárquica de DocTypes
    hierarchy = dp.get_hierarchical_structure()
    # Recupera dados relacionados a um id principal (ex: contrato) e gera arquivo JSON
    result = dp.get_data(main_id="CONTRACT-0001", parameters=[{"parameter":"#MEASUREMENT#","value":"MEAS-01"}])
    # result contém chaves: "data", "structure", "hierarchical"
Observações:
    - Este módulo pressupõe a existência de endpoints compatíveis expostos pelo SmiApi que mapeiam os conceitos do
      Frappe Framework (DocType, DocField, filtros por campo, recuperação por chave).
    - A implementação separa responsabilidades em componentes testáveis (ArterisApiClient, DataManager, Extractors,
      DoctypeRetriever, DoctypeDataRetriever) para facilitar manutenção e evolução.
"""

import json
import re
import unicodedata
import logging
from .hierarchical_tree import HierarchicalTreeBuilder
from .api_smi import SmiApi
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from .file_manager import FileManager

logger = logging.getLogger(__name__)

@dataclass
class Field:
    """
    Representa um campo em um DocType
    """
    fieldname: str
    label: Optional[str] = None
    fieldtype: Optional[str] = None
    options: Optional[str] = None
    hidden: Optional[bool] = None
    parent: Optional[str] = None
    creation: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Field':
        """
        Cria um Field a partir de um dicionário

        Parâmetros:
            data (Dict[str, Any]): dados do campo

        Retorno:
            Field: instância do campo
        """
        try:
            data["options"] = data.get("options", "")
            return cls(
                fieldname=data.get("fieldname", ""),
                label=data.get("label"),
                fieldtype=data.get("fieldtype"),
                options=data.get("options"),
                hidden=data.get("hidden"),
                parent=data.get("parent"),
                creation=data.get("creation")
            )
        except Exception as e:
            logger.exception("Erro inesperado criando Field: %s", e)
            return cls(fieldname="")

    def to_dict(self) -> Dict[str, Any]:
        """
        Converte para dicionário, excluindo valores None

        Retorno:
            Dict[str, Any]: dicionário representando o campo
        """
        try:
            return {k: v for k, v in self.__dict__.items() if v is not None}
        except Exception as e:
            logger.exception("Erro inesperado convertendo Field para dict: %s", e)
            return {}

@dataclass
class ParentMapping:
    """
    Representa uma relação pai-filho entre DocTypes
    """
    child: str
    parent: str
    type: str

class StringNormalizer:
    """
    Realiza a normalização de strings
    """
    
    @staticmethod
    def normalize(s: str) -> str:
        """
        Normaliza a string para uso em arquivo/caminho

        Retorno:
            str: string normalizada
        """
        try:
            if not s:
                return ""

            s = unicodedata.normalize('NFKD', s).encode('ASCII', 'ignore').decode('ASCII')
            s = re.sub(r'[^a-zA-Z0-9_]', '_', s)
            s = re.sub(r'_{2,}', '_', s)
            s = s.strip('_')
            return s.lower()
        except Exception as e:
            logger.exception("Erro inesperado normalizando string: %s", e)
            return ""

class FieldFilter:
    """
    Filtra campos com base em regras de negócio
    """
    
    EXCLUDED_FIELDTYPES = {"Section Break", "Column Break", "Tab Break", ""}
    EXCLUDED_FIELDNAMES = {"lft", "rgt", "old_parent"}
    
    @classmethod
    def should_include(cls, field_data: Dict[str, Any]) -> bool:
        """
        Verifica se o campo deve ser incluído

        Parâmetros:
            field_data (Dict[str, Any]): dados do campo

        Retorno:
            bool: True se deve incluir, False caso contrário
        """
        try:
            if field_data.get("fieldtype") in cls.EXCLUDED_FIELDTYPES:
                return False

            fieldname = field_data.get("fieldname", "")
            if fieldname in cls.EXCLUDED_FIELDNAMES or fieldname.startswith("parent_"):
                return False

            return True
        except Exception as e:
            logger.exception("Erro inesperado verificando inclusão do campo: %s", e)
            return False

class ArterisApiClient:
    """
    Wrapper para operações da API Arteris
    """
    
    def __init__(self):
        try:
            self.arteris_api = SmiApi()
            self.logger = logging.getLogger(__name__)
        except Exception as e:
            logger.exception("Erro inesperado inicializando ArterisApiClient: %s", e)
            raise
    
    def get_main_doctypes(self) -> Optional[List[Dict]]:
        """
        Obtém os doctypes principais da API

        Retorno:
            Optional[List[Dict]]: lista de doctypes ou None em caso de falha
        """
        try:
            _get_arteris_doctypes = self.arteris_api.get_arteris_doctypes(child=False)
            if _get_arteris_doctypes is None:
                logger.error("A resposta da API para doctypes principais é None")
                return None
            return _get_arteris_doctypes # type: ignore
        except Exception as e:
            logger.exception("Erro inesperado obtendo doctypes principais: %s", e)
            return None
    
    def get_child_doctypes(self) -> Optional[List[Dict]]:
        """
        Obtém os doctypes filhos da API

        Retorno:
            Optional[List[Dict]]: lista de doctypes ou None em caso de falha
        """
        try:
            _get_arteris_doctypes = self.arteris_api.get_arteris_doctypes(child=True)
            if _get_arteris_doctypes is None or not isinstance(_get_arteris_doctypes, list):
                logger.error("A resposta da API para doctypes filhos é None ou não é uma lista válida")
                return None
            return _get_arteris_doctypes # type: ignore
        except Exception as e:
            logger.exception("Erro inesperado obtendo doctypes filhos: %s", e)
            return None
    
    def get_docfields(self, doctype_name: str) -> Optional[Dict]:
        """
        Obtém os campos para um doctype

        Parâmetros:
            doctype_name (str): nome do doctype

        Retorno:
            Optional[Dict]: dicionário com os campos do doctype ou None em caso de falha
        """
        try:
            _get_docfields_for_doctype = self.arteris_api.get_docfields_for_doctype(doctype_name)
            if _get_docfields_for_doctype is None:
                logger.error("A resposta da API para docfields de %s é None", doctype_name)
                return None
            return _get_docfields_for_doctype # type: ignore
        except Exception as e:
            logger.exception("Erro inesperado obtendo campos para %s: %s", doctype_name, e)
            return None
    
    def get_names(self, doctype_name: str, filters: Optional[str] = None) -> List[str]:
        """
        Obtém chaves para um doctype

        Parâmetros:
            doctype_name (str): nome do doctype
            filters (Optional[str]): filtros opcionais no formato JSON

        Retorno:
            List[str]: lista de chaves ou vazia em caso de falha
        """
        try:
            _filters = {}
            if filters is not None:
                _filters = json.loads(filters)
            _get_keys = self.arteris_api.get_keys(doctype_name=doctype_name, filters=_filters, return_field="name")
            if _get_keys is None or not isinstance(_get_keys, list):
                logger.error("A resposta da API para chaves de %s é None ou não é lista", doctype_name)
                return []
            return _get_keys
        except json.JSONDecodeError as e:
            logger.error("Erro decodificando JSON nos filtros para %s: %s", doctype_name, e)
            return []
        except Exception as e:
            logger.exception("Erro inesperado obtendo chaves para %s: %s", doctype_name, e)
            return []

    def get_field(self, doctype_name: str, return_field: str, filters: Dict) -> List[str]:
        """
        Obtém valores de um campo para um doctype

        Parâmetros:
            doctype_name (str): nome do doctype
            return_field (str): campo a ser retornado como chave
            filters (Dict): filtros opcionais no formato dicionário

        Retorno:
            List[str]: lista de chaves ou vazia em caso de falha
        """
        try:
            _get_keys = self.arteris_api.get_keys(doctype_name=doctype_name, return_field=return_field, filters=filters)
            if _get_keys is None:
                logger.error("A resposta da API para campo %s de %s é None", return_field, doctype_name)
                return []
            return _get_keys
        except Exception as e:
            logger.exception("Erro inesperado obtendo campo %s para %s: %s", return_field, doctype_name, e)
            return []

    def get_data_by_key(self, doctype_name: str, key: str) -> Optional[Dict]:
        """
        Obtém dados para uma chave específica

        Parâmetros:
            doctype_name (str): nome do doctype
            key (str): chave do registro

        Retorno:
            Optional[Dict]: dicionário com os dados ou None em caso de falha
        """
        try:
            return self.arteris_api.get_data_from_key(doctype_name, key)
        except Exception as e:
            logger.exception("Erro inesperado obtendo dados para %s:%s: %s", doctype_name, key, e)
            return None

    def get_contracts(self) -> Optional[List[Dict]]:
        """
        Obtém dados do doctype Contract

        Retorno:
            Optional[List[Dict]]: lista de contratos ou None em caso de falha
        """
        try:
            _get_contracts = self.arteris_api.get_contracts()
            if _get_contracts is None:
                logger.error("A resposta da API para contratos é None")
                return None
            return _get_contracts # type: ignore
        except Exception as e:
            logger.exception("Erro inesperado obtendo contratos: %s", e)
            return None            

class DoctypeFieldExtractor:
    """
    Extrai e processa os campos de doctype
    """
    
    def __init__(self, field_filter: FieldFilter):
        try:
            self.field_filter = field_filter
        except Exception as e:
            logger.exception("Erro inesperado inicializando DoctypeFieldExtractor: %s", e)
            raise
    
    def extract_fields(self, docfields: Dict) -> List[Field]:
        """
        Extrai os campos da resposta docfields

        Parâmetros:
            docfields (Dict): dicionário com os campos do doctype

        Retorno:
            List[Field]: lista de campos extraídos
        """
        try:
            fields = []

            for field_data in docfields.get("fields", []):
                try:
                    if self.field_filter.should_include(field_data):
                        field = Field.from_dict(field_data)
                        fields.append(field)
                except Exception as e:
                    logger.error("Erro processando campo individual: %s", e)
                    continue

            return fields
        except Exception as e:
            logger.exception("Erro inesperado extraindo campos: %s", e)
            return []

class ParentMappingExtractor:
    """
    Extrai relações pai-filho entre doctypes
    """
    
    def extract_mappings(self, doctypes_with_fields: Dict[str, List[Dict]]) -> List[ParentMapping]:
        """
        Extrai mapeamentos de pai-filho a partir dos campos do doctype

        Parâmetros:
            doctypes_with_fields (Dict[str, List[Dict]]): dicionário com doctypes e seus campos

        Retorno:
            List[ParentMapping]: lista de mapeamentos pai-filho extraídos
        """
        try:
            mappings = []

            for doctype_name, fields in doctypes_with_fields.items():
                if not fields:
                    continue

                for field in fields:
                    try:
                        if (field.get("fieldtype") == "Table" and
                            field.get("fieldname") and
                            field.get("options")):

                            mapping = ParentMapping(
                                child=field["options"],
                                parent=doctype_name,
                                type=field["fieldtype"]
                            )
                            mappings.append(mapping)
                    except Exception as e:
                        logger.error("Erro processando mapeamento para %s: %s", doctype_name, e)
                        continue

            return mappings
        except Exception as e:
            logger.exception("Erro inesperado extraindo mapeamentos: %s", e)
            return []

class DoctypeDataRetriever:
    """
    Recupera os dados de um determinado doctype
    """
    
    def __init__(self, api_client: ArterisApiClient):
        try:
            self.api_client = api_client
        except Exception as e:
            logger.exception("Erro inesperado inicializando DoctypeDataRetriever: %s", e)
            raise

    def get_doctype_keys_api(self, doctype_name: str, return_field: str, filters: Dict) -> Optional[List[str]]:
        """
        Obtém chaves para um doctype usando a API

        Parâmetros:
            doctype_name (str): nome do doctype
            return_field (str): campo a ser retornado como chave
            filters (Dict): filtros opcionais no formato dicionário

        Retorno:
            Optional[List[str]]: lista com as chaves ou None em caso de falha
        """
        try:
            keys = self.api_client.get_field(doctype_name, return_field, filters)
            if not keys:
                return None
            return keys
        except Exception as e:
            logger.exception("Erro inesperado obtendo chaves via API para %s: %s", doctype_name, e)
            return None
    
    def get_doctype_data(self, doctype_name: str, filters: Optional[str] = None) -> Tuple[List[Dict], List[str]]:
        """
        Obtém dados e chaves para um doctype

        Parâmetros:
            doctype_name (str): nome do doctype
            filters (Optional[str]): filtros opcionais no formato JSON

        Retorno:
            Tuple[List[Dict], List[str]]: tupla com lista de dados e lista de chaves
        """
        try:
            keys = self.api_client.get_names(doctype_name, filters)
            data = []

            if keys:
                for key in keys:
                    try:
                        doc_data = self.api_client.get_data_by_key(doctype_name, key)
                        if doc_data:
                            data.append(doc_data)
                    except Exception as e:
                        logger.error("Erro obtendo dados para chave %s de %s: %s", key, doctype_name, e)
                        continue

            return data, keys
        except Exception as e:
            logger.exception("Erro inesperado obtendo dados do doctype %s: %s", doctype_name, e)
            return [], []


    def get_contracts(self) -> Optional[List[Dict]]:
        """
        Obtém dados do doctype Contract

        Retorno:
            Optional[List[Dict]]: lista de contratos ou None em caso de falha
        """
        try:
            return self.api_client.get_contracts()
        except Exception as e:
            logger.exception("Erro inesperado obtendo contratos: %s", e)
            return None

class Mappings:
    """
    Classe de mapeamentos específicos
    """
    
    def get_specific_mapping(self) -> List[Dict]:
        """
        Retorna um mapeamento específico para a estrutura da entidade.
        Substitui a logica padrão do Frappe, necessaria para construir a árvore hierárquica corretamente.
        Retorno:
            List[Dict]: lista de mapeamentos específicos
        """

        # Força com que determinados filhos sejam sempre associados a um pai específico
        specific_mappings = [
            {"child": "Contract Adjustment", "parent": "Contract"},
            {"child": "Contract Item", "parent": "Contract"},
            {"child": "Contract Measurement", "parent": "Contract", "filters": [{"medicaovigente": "sim"}]},
            {"child": "Contract Measurement Record", "parent": "Contract", "filters": [{"medicaovigente": "sim"}]},
        ]

        return specific_mappings


    def get_ignore_mapping(self) -> List[str]:
        """
        Retorna um mapeamento de itens a serem ignorados na estrutura da entidade.
        Retorno:
            List[str]: lista de itens a serem ignorados
        """

        # Doctypes que devem ser ignorados
        ignore_mappings = [
            "Formula",
            "Formula Template",
            "Formula Group",
            "Formula Fields",
            "Formula Template",
            "Formula Group Field",
            "Formula Group Template",
            "Asset Config Kartado",
            "Contract Item Config Kartado",
            "Integration Record Keys",
            "Item Config Kartado",
            "Integration Inconsistency",
            "Integration Record",
            "Depth Period Setting",
            "TestPut",
            "TestPutChild",
            "Work Role Config Kartado",
            "Contract Measurement Productivity",
            "Contract Measurement Productivity Total",
            "Kartado Config",
            "Osiris Config",
            "SMI Config",
            "Contract Signature",
            "Contract Item Workload Cfg",
            "Contract S",
            "Retention Type"
        ]

        return ignore_mappings

    def get_main_data(self) -> List[Dict]:
        """
        Metodo para retornar os doctypes que são exclusivos por medição, e define os filtros aplicados 
        para a carga dos dados, transformando doctypes pais em filhos, eliminando a deficiência do Frappe
        em tratar mais de um nível de filhos.

        Retorno:
            List[Dict]: lista de mapeamentos específicos
        """

        # Usando a medicao como parâmetro
        main_doctypes = [
            {
                "doctype": "Contract", # Nome do doctype
                "key": "name", # Campo usado como chave
                "data": True, # Indica se deve coletar dados
                "childs": [ # Doctypes filhos
                    {   
                        "doctype": "Contract Adjustment", 
                        "data": True,
                        "key": "contrato" # Chave de relacionamento com o pai
                    },
                    {   
                        "doctype": "Contract Item", 
                        "data": True,
                        "key": "contrato"
                    },
                    {   
                        "doctype": "Contract Measurement", 
                        "data": True,
                        "key": "contrato",
                        "filters": [{"field": "name", "value": "#MEASUREMENT#"}] # Filtro personalizado
                    },
                    {
                        "doctype": "Contract Measurement Record", 
                        "data": True,
                        "key": "contrato",
                        "filters": [{"field": "boletimmedicao", "value": "#MEASUREMENT#"}]
                    }
                ]
            },
            {
                "doctype": "Contract Item",
                "data": False,
                "key": "contrato",
                "childs": [
                    {
                        "doctype": "Contract Item Order", 
                        "data": False,
                        "key": "parent",
                        "customapi": True, # Indica necessidade de usar a busca customizada
                        "customapi_field": "pedidosap", # Campo a ser retornado
                        "childs": [
                            {
                                "doctype": "SAP Order",
                                "key": "name",
                                "data": True
                            }                            
                        ]
                    }                    
                ]                
            }
        ]

        return main_doctypes    

class Translations:
    """
    Fornece traduções para nomes de DocTypes
    """

    def get_translations(self) -> Dict[str, str]:
        """
        Retorna um dicionário de traduções para nomes de DocTypes

        Retorno:
            Dict[str, str]: dicionário de traduções
        """

        # Traduções padronizadas
        return {
            "Asset": "Ativos",
            "Category": "Categorias",
            "City": "Cidades",
            "Contract": "Contratos",
            "Contract_Item": "Itens",
            "Contract_Measurement": "Bol. de medição",
            "Contract_Measurement_Record": "Registros de BM.",
            "Contract_Adjustment": "Reajustes",
            "Contract_Item_Highway": "Rodovias",
            "Contract_Item_Order": "Ped. SAP",
            "Contract_Item_Asset": "Ativos",
            "Contract_Item_Work_Role": "Funções",
            "Contract_Item_City": "Cidades",
            "Contract_Measurement_Asset": "Ativos",
            "Contract_Measurement_Work_Role": "Funções",
            "Contract_Measurement_Record_Material": "Materiais",
            "Contract_Measurement_Record_Asset": "Ativos",
            "Contract_Measurement_Record_Work_Role": "Funções",
            "Contract_Adjustment_Data": "Dados do reajuste",
            "Contracted_Company": "Empresa contratada",
            "Highway": "Rodovias",
            "Highway_City": "Cidades",
            "Holiday": "Feriados",
            "Item_Classification": "Classificação de itens",
            "Material": "Materiais",
            "Person": "Pessoa",
            "Contract_Measurement_City": "Cidades",
            "Contract_Measurement_FTD": "Fat. direto",
            "Contract_Measurement_SAP_Order": "Ped. SAP",
            "Work_Role": "Funções",
            "Contract_Measurement_Record_Log": "Relatórios",
            "Contract_Measurement_Record_Resource": "Recursos",
            "Contract_Measurement_Item": "Itens",
            "Contract_Measurement_Record_Time": "Apontamentos de horas",
            "Contract_Item_Type": "Tipos de itens",
            "Item": "Modelos de itens",
            "Unit": "Unidades",
            "Subsidiary": "Concessionárias",
            "SAP_Order_Highway": "Rodovias",
            "SAP_Order_Period": "Linhas",
            "Item Group": "Grupos de itens",
            "Item_Sub_Group": "Subgrupos de itens",
            "Contract_Measurement_Performance": "Performance",
            "Contract_Performance": "Performance"
        }    

class DoctypeRetriever:
    """
    Recupera doctypes e seus campos
    """
    
    def __init__(self, api_client: ArterisApiClient, field_extractor: DoctypeFieldExtractor, mappings: Mappings):
        try:
            self.api_client = api_client
            self.field_extractor = field_extractor
            self.mappings = mappings
        except Exception as e:
            logger.exception("Erro inesperado inicializando DoctypeRetriever: %s", e)
            raise
    
    def get_doctypes_with_fields(self, doctype_list: List[Dict]) -> Dict[str, List[Dict]]:
        """
        Obtém os doctypes com seus campos

        Parâmetros:
            doctype_list (List[Dict]): lista de doctypes

        Retorno:
            Dict[str, List[Dict]]: dicionário com doctypes e seus campos
        """
        try:
            doctypes_with_fields = {}

            for doc in doctype_list:
                try:
                    doctype_name = doc.get("name")
                    if not doctype_name:
                        continue

                    docfields = self.api_client.get_docfields(doctype_name)
                    if docfields:
                        fields = self.field_extractor.extract_fields(docfields)
                        doctypes_with_fields[doctype_name] = [f.to_dict() for f in fields]
                except Exception as e:
                    logger.error("Erro processando doctype %s: %s", doc.get("name", "Unknown"), e)
                    continue

            return doctypes_with_fields
        except Exception as e:
            logger.exception("Erro inesperado obtendo doctypes com campos: %s", e)
            return {}
    
    def get_all_doctypes(self) -> Dict[str, Any]:
        """
        Obtém todos os doctypes (principais e filhos) com seus campos

        Retorno:
            Dict[str, Any]: dicionário com doctypes principais, filhos e todos combinados
        """
        try:
            main_list = self.api_client.get_main_doctypes()
            main_doctypes = self.get_doctypes_with_fields(main_list) if main_list else {}

            child_list = self.api_client.get_child_doctypes()
            child_doctypes = self.get_doctypes_with_fields(child_list) if child_list else {}

            all_doctypes = {**main_doctypes, **child_doctypes}

            ignore_list = self.mappings.get_ignore_mapping()
            for ignored in ignore_list:
                all_doctypes.pop(ignored, None)

            return {
                "main_doctypes": main_doctypes,
                "child_doctypes": child_doctypes,
                "all_doctypes": all_doctypes
            }
        except Exception as e:
            logger.exception("Erro inesperado obtendo todos os doctypes: %s", e)
            return {
                "main_doctypes": {},
                "child_doctypes": {},
                "all_doctypes": {}
            }

class DoctypeProcessor:
    """
    Processador principal para operações de doctype
    """
    
    def __init__(self):
        try:
            self.normalizer = StringNormalizer()
            self.api_client = ArterisApiClient()
            self.field_filter = FieldFilter()
            self.field_extractor = DoctypeFieldExtractor(self.field_filter)
            self.mapping_extractor = ParentMappingExtractor()
            self.data_retriever = DoctypeDataRetriever(self.api_client)
            self.translations = Translations()
            self.mappings = Mappings()
            self.doctype_retriever = DoctypeRetriever(self.api_client, self.field_extractor, self.mappings)
            self.hierarchical_tree = HierarchicalTreeBuilder(self.translations, self.mappings)
            self.file_manager = FileManager()
        except Exception as e:
            logger.exception("Erro inesperado inicializando DoctypeProcessor: %s", e)
            raise
    
    def get_keys(self, doctype_name: str, filters: Optional[str] = None) -> List[str]:
        """
        Obtém chaves para um doctype específico

        Parâmetros:
            doctype_name (str): nome do doctype
            filters (Optional[str]): filtros opcionais no formato JSON

        Retorno:
            List[str]: lista de chaves
        """
        try:
            return self.api_client.get_names(doctype_name, filters)
        except Exception as e:
            logger.exception("Erro inesperado obtendo chaves para %s: %s", doctype_name, e)
            return []

    def process_doctypes(self) -> Dict[str, Any]:
        """
        Processa todos os doctypes e retorna dados estruturados

        Retorno:
            Dict[str, Any]: dicionário com doctypes e mapeamentos pai-filho
        """
        try:
            doctype_data = self.doctype_retriever.get_all_doctypes()

            parent_mappings = self.mapping_extractor.extract_mappings(
                doctype_data["all_doctypes"]
            )

            doctype_data["parents_mapping"] = [
                {"child": m.child, "parent": m.parent, "type": m.type}
                for m in parent_mappings
            ]

            return doctype_data
        except Exception as e:
            logger.exception("Erro inesperado processando doctypes: %s", e)
            return {
                "main_doctypes": {},
                "child_doctypes": {},
                "all_doctypes": {},
                "parents_mapping": []
            }
        
    def get_hierarchical_structure(self) -> List[Dict]:
        """
        Recupera e salva todos os dados dos doctypes

        Retorno:
            List[Dict]: estrutura hierárquica dos doctypes
        """
        try:
            all_doctypes = self.process_doctypes()
            hierarchical = self.hierarchical_tree.build_tree(all_doctypes)
            return hierarchical
        except Exception as e:
            logger.exception("Erro inesperado obtendo estrutura hierárquica: %s", e)
            return []

    def get_default_data_update_structure(self, all_doctype_structure: Dict[str, Any], doctypes: List[Dict]):
        try:
            for dt in doctypes:
                try:
                    if "childs" in dt:
                        self.get_default_data_update_structure(all_doctype_structure, dt["childs"])

                    if dt.get("data"):
                        main_map = all_doctype_structure.get("main_doctypes")
                        if isinstance(main_map, dict):
                            main_map.pop(dt["doctype"], None)
                except Exception as e:
                    logger.error("Erro processando doctype %s na atualização da estrutura: %s", dt.get("doctype", "Unknown"), e)
                    continue
        except Exception as e:
            logger.exception("Erro inesperado atualizando estrutura de dados padrão: %s", e)

    def get_default_data(self, using_cached_data=False) -> Dict[str, Any]:
        """
        Recupera os dados padrão para todos os doctypes

        Parâmetros:
            using_cached_data (bool): indica se deve usar dados em cache

        Retorno:
            Dict[str, Any]: dicionário com dados dos doctypes
        """
        try:
            if (not using_cached_data or
                not self.file_manager.check_file_exists("all_doctypes_data.json") or
                not self.file_manager.check_file_exists("all_doctypes_structure.json")):

                all_doctype_structure = self.process_doctypes()
                main_doctypes = self.mappings.get_main_data()
                self.get_default_data_update_structure(all_doctype_structure, main_doctypes)

                ignore_list = self.mappings.get_ignore_mapping()
                for ignored in ignore_list:
                    all_doctype_structure["main_doctypes"].pop(ignored, None)

                all_doctype_data = []

                for doctype_name in all_doctype_structure["main_doctypes"]:

                    print(f"Obtendo dados para doctype: {doctype_name}")

                    try:
                        data, _ = self.data_retriever.get_doctype_data(doctype_name)
                        all_doctype_data.append({doctype_name: data})
                    except Exception as e:
                        logger.error("Erro obtendo dados para doctype %s: %s", doctype_name, e)
                        continue

                self.file_manager.save_json(file_name="all_doctypes_data.json", data=all_doctype_data)
                self.file_manager.save_json(file_name="all_doctypes_structure.json", data=all_doctype_structure)

            else:
                all_doctype_data = self.file_manager.load_json("all_doctypes_data.json")
                all_doctype_structure = self.file_manager.load_json("all_doctypes_structure.json")

            return {
                "data": all_doctype_data,
                "structure": all_doctype_structure["all_doctypes"]
            }
        except Exception as e:
            logger.exception("Erro inesperado obtendo dados padrão: %s", e)
            return {
                "data": [],
                "structure": {}
            }

    def get_data_main_doctypes(self,
                               all_doctype_data: List[Dict],
                               doctypes: List[Dict],
                               main_keys: List[str],
                               parameters: List[Dict[str, str]]) -> None:
        """
        Recupera os dados dos doctypes principais e seus filhos recursivamente
        Parâmetros:
            all_doctype_data (List[Dict]): lista para armazenar os dados dos doctypes
            doctypes (List[Dict]): lista de doctypes a serem processados
            main_keys (List[str]): chaves principais para filtrar os dados
            parameters (List[Dict[str, str]]): parâmetros adicionais para filtros
        """
        try:
            for dt in doctypes:
                try:
                    dt_data = []
                    dt_keys = []

                    for k in main_keys:
                        try:
                            get_data = None

                            if "customapi" in dt and dt["customapi"]:
                                filters = {}
                                filters[dt["key"]] = k
                                if "filters" in dt:
                                    for filter in dt["filters"]:
                                        filters[filter["field"]] = filter["value"]
                                keys = self.data_retriever.get_doctype_keys_api(dt["doctype"], dt["customapi_field"], filters)
                            else:
                                filters = f'["{dt["key"]}","=","{k}"]'
                                if "filters" in dt:
                                    for filter in dt["filters"]:
                                        value = filter["value"]
                                        for p in parameters:
                                            if value == p["parameter"]:
                                                value = p["value"]
                                        filters += f',["{filter["field"]}","=","{value}"]'
                                filters = f'[{filters}]'
                                get_data, keys = self.data_retriever.get_doctype_data(dt["doctype"], filters)

                            if keys:
                                dt_keys.extend([k for k in keys if k not in dt_keys])

                            if dt["data"] and get_data:
                                dt_data.extend(get_data)
                        except Exception as e:
                            logger.error("Erro processando chave %s para doctype %s: %s", k, dt.get("doctype", "Unknown"), e)
                            continue

                    if dt_data:
                        all_doctype_data.append({dt["doctype"]: dt_data.copy()})

                    if "childs" in dt:
                        self.get_data_main_doctypes(
                            all_doctype_data,
                            dt["childs"],
                            dt_keys,
                            parameters
                        )
                except Exception as e:
                    logger.error("Erro processando doctype %s: %s", dt.get("doctype", "Unknown"), e)
                    continue
        except Exception as e:
            logger.exception("Erro inesperado obtendo dados dos doctypes principais: %s", e)   
    
    def get_data(self, main_id: str, parameters: List[Dict[str, str]] = []) -> Dict[str, Any]:
        """
        Recupera e salva todos os dados dos doctypes
        Parâmetros:
            main_id (str): id principal para filtrar os dados
            parameters (List[Dict[str, str]]): parâmetros adicionais para filtros
        Retorno:
            Dict[str, Any]: dicionário com dados, estrutura e hierarquia
        """
        try:

            print(f"Obtendo dados para id principal: {main_id}")

            result = self.get_default_data(using_cached_data=True)
            all_doctype_structure = result["structure"]
            all_doctype_data = result["data"]

            main_doctypes = self.mappings.get_main_data()

            print(f"Doctypes principais a processar: {[dt['doctype'] for dt in main_doctypes]}")

            self.get_data_main_doctypes(all_doctype_data, main_doctypes, [main_id], parameters)

            self.file_manager.save_json(file_name=f"all_doctype_data_{main_id}.json", data=all_doctype_data)

            print("Construindo estrutura hierárquica...")

            hierarchical = self.hierarchical_tree.build_tree(all_doctype_structure)

            self.file_manager.save_json(file_name=f"all_doctype_hierarchical_{main_id}.json", data=hierarchical)

            return {
                "data": all_doctype_data,
                "structure": all_doctype_structure,
                "hierarchical": hierarchical
            }
        except Exception as e:
            print(f"Erro inesperado obtendo dados para {main_id}: {e}")
            logger.exception("Erro inesperado obtendo dados para %s: %s", main_id, e)
            return {
                "data": [],
                "structure": {},
                "hierarchical": []
            }

    def get_formula_data(self, using_cached_data=False) -> List[Dict[str, Any]]:
        """
        Recupera dados do grupo Formula
        Parâmetros:
            using_cached_data (bool): indica se deve usar dados em cache
        Retorno:
            List[Dict]: lista de dados do grupo Formula
        """
        try:
            if not using_cached_data or not self.file_manager.check_file_exists("formula_group.json"):
                data, _ = self.data_retriever.get_doctype_data("Formula Group")
                self.file_manager.save_json(file_name="formula_group.json", data=data)

            _get_formula_data = self.file_manager.load_json("formula_group.json")
            return _get_formula_data # type: ignore
        except Exception as e:
            logger.exception("Erro inesperado obtendo dados de fórmulas: %s", e)
            return []
