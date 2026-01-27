"""
Engine Data Builder — Construtor e serializador de estruturas de dados do motor
Propósito:
    Fornece ferramentas para construir, analisar e serializar uma representação
    hierárquica de dados (doctypes, campos, fórmulas) usada pelo motor de cálculo.

Responsabilidades principais:
    - Traversal do árvore de doctypes e montagem de objetos de domínio (EngineDataHead/Item/Field).
    - Extração e análise de caminhos referenciados por fórmulas para geração de saída compacta.
    - Geração de mapeamentos de referência (códigos curtos) e substituição de paths nas estruturas.
    
Posição na arquitetura:
    Camada de transformação/serialização entre a representação de metadados (doctype tree + fórmulas)
    e a camada de persistência/integração do motor. Atua como adaptador que converte dados do
    sistema fonte em payloads estruturados que o engine consome.

Dependências críticas:
    - Estrutura de entrada: doctype_tree (lista de nós com 'path', 'type', 'fieldname', 'children', etc.).
    - Conjunto de fórmulas no formato esperado (grupos com chave "tableformulas" contendo "formula", "groupfielddoctype", ...).
    - Dados por doctype (all_doctype_data) indexados por nome de doctype.
    - Componente PathManager/PathReplacer para gerar e aplicar referências de caminho.

Considerações de segurança:
    - Validação: o módulo assume entradas bem formadas; validar/limpar dados externos (especialmente strings de fórmulas)
      antes de chamar o builder para evitar injeção de padrões regex ou substituições inesperadas.
    - Contenção de recursos: entradas muito grandes (árvores profundas ou muitas fórmulas) podem causar uso significativo de CPU/memória.

Exemplo de uso básico:
    # carregar metadados e dados
    doctype_tree = FileManager.load_json("doctype_tree.json")
    formulas = FileManager.load_json("formulas.json")
    all_doctype_data = FileManager.load_json("all_doctype_data.json")
    # construir estrutura em modo compacto (analisando apenas caminhos usados pelas fórmulas)
    builder = EngineDataBuilder(
        doctype_tree=doctype_tree,
        all_doctype_data=all_doctype_data,
        child_name="childs",
        compact_mode=True
    output = builder.build()
    FileManager.save_json(output, "engine_payload.json")

"""

import re
import logging
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

@dataclass
class FieldData:
    """
    Representa um campo com seu caminho, tipo e valor
    """
    path: str
    type: str
    value: Any

@dataclass
class EngineDataItem:
    """
    Representa um item de dados do motor
    """
    id: str
    creation: str
    fields: List[FieldData] = field(default_factory=list)
    childs: List['EngineDataHead'] = field(default_factory=list)

    def to_dict(self, child_name: str = "childs") -> Dict[str, Any]:
        """
        Converte para dicionário com nome de filho personalizado
        Parâmetros:
            child_name (str): Nome da chave para filhos (padrão: "childs")
        Retorno:
            Dict[str, Any]: Representação em dicionário do item
        """
        try:
            return {
                "id": self.id,
                "creation": self.creation,
                "fields": [{"path": f.path, "type": f.type, "value": f.value} for f in self.fields],
                child_name: [child.to_dict(child_name) for child in self.childs]
            }
        except Exception as e:
            logger.exception("Erro inesperado ao converter item para dicionário: %s", e)
            return {"id": "", "creation": "", "fields": [], child_name: []}
    
    def is_empty(self) -> bool:
        """
        Verifica se o item está vazio (sem dados significativos)
        Retorno:
            bool: True se o item estiver vazio, False caso contrário
        """
        try:
            if self.id and self.id.strip():
                return False

            if not self.fields:
                return True

            for f in self.fields:
                if f.value not in [None, "", 0, False, "1999-01-01", "1999-01-01 00:00:00", "00:00:00"]:
                    return False

            return True
        except Exception as e:
            logger.exception("Erro inesperado ao verificar se item está vazio: %s", e)
            return True
    
    def has_children(self) -> bool:
        """
        Verifica se o item tem filhos
        Retorno:
            bool: True se o item tiver filhos, False caso contrário
        """
        try:
            return len(self.childs) > 0
        except Exception as e:
            logger.exception("Erro inesperado ao verificar se item tem filhos: %s", e)
            return False

@dataclass
class FormulaData:
    """
    Representa uma configuração de fórmula
    """
    path: str
    value: str
    update: Dict[str, str]

    def to_dict(self) -> Dict[str, Any]:
        """
        Converte para dicionário
        Retorno:
            Dict[str, Any]: Representação em dicionário da fórmula
        """
        try:
            return {
                "path": self.path,
                "value": self.value,
                "update": self.update
            }
        except Exception as e:
            logger.exception("Erro inesperado ao converter fórmula para dicionário: %s", e)
            return {"path": "", "value": "", "update": {}}

@dataclass
class EngineDataHead:
    """
    Representa o cabeçalho da estrutura de dados do motor
    """
    path: str
    formulas: List[FormulaData] = field(default_factory=list)
    data: List[EngineDataItem] = field(default_factory=list)

    def to_dict(self, child_name: str = "childs", compact: bool = False, ultra_compact: bool = False) -> Dict[str, Any]:
        """
        Converte para dicionário com nome de filho personalizado
        Parâmetros:
            child_name (str): Nome da chave para filhos (padrão: "childs")
            compact (bool): Se True, filtra itens vazios sem filhos
            ultra_compact (bool): Se True, filtra itens vazios sem filhos e sem valores de campo significativos
        Retorno:
            Dict[str, Any]: Representação em dicionário da cabeça
        """
        try:
            if compact or ultra_compact:
                filtered_data = []
                for item in self.data:
                    try:
                        if ultra_compact:
                            has_field_values = any(
                                field.value not in [None, "", 0, False, "1999-01-01", "1999-01-01 00:00:00", "00:00:00"]
                                for field in item.fields
                            )
                            if has_field_values or item.has_children():
                                filtered_data.append(item.to_dict(child_name))
                        else:
                            if not item.is_empty() or item.has_children():
                                filtered_data.append(item.to_dict(child_name))
                    except Exception as e:
                        logger.exception("Erro ao processar item durante filtragem: %s", e)
                        continue
            else:
                filtered_data = [item.to_dict(child_name) for item in self.data]

            return {
                "path": self.path,
                "formulas": [f.to_dict() for f in self.formulas],
                "data": filtered_data
            }
        except Exception as e:
            logger.exception("Erro inesperado ao converter cabeça para dicionário: %s", e)
            return {"path": "", "formulas": [], "data": []}

class DefaultValueProvider:
    """
    Provê valores padrão para tipos de campos comuns
    """
    
    DEFAULT_VALUES = {
        "int": 0,
        "numeric": 0,
        "float": 0,
        "number": 0,
        "string": "",
        "boolean": False,
        "date": "1999-01-01",
        "datetime": "1999-01-01 00:00:00",
        "time": "00:00:00",
        "text": ""
    }
    
    DEFAULT_CREATION_DATE = "1999-01-01 00:00:00"
    
    @classmethod
    def get_default(cls, field_type: str) -> Any:
        """
        Obtém o valor padrão para o tipo de campo especificado
        Parâmetros:
            field_type (str): Tipo do campo (e.g., "int", "string", "date", etc.)
        Retorno:
            Any: Valor padrão correspondente ao tipo, ou string vazia se desconhecido
        """
        try:
            return cls.DEFAULT_VALUES.get(field_type, "")
        except Exception as e:
            logger.exception("Erro inesperado ao obter valor padrão para tipo %s: %s", field_type, e)
            return ""

class PathManager:
    """
    Gerencia referências e substituições de caminhos
    """
    
    def __init__(self):
        # Inicializa a lista de caminhos e o conjunto para rastrear unicidade
        self.paths: List[str] = []
        self._path_set: set = set()
    
    def add_path(self, path: str) -> None:
        """
        Adiciona um caminho à coleção se ainda não estiver presente
        Parâmetros:
            path (str): O caminho a ser adicionado
        """
        try:
            if path and path not in self._path_set:
                self.paths.append(path)
                self._path_set.add(path)
        except Exception as e:
            logger.exception("Erro inesperado ao adicionar caminho %s: %s", path, e)
    
    def generate_references(self) -> Dict[str, List[Dict[str, str]]]:
        """
        Gera mapeamento de referência para todos os caminhos
        Retorno:
            Dict[str, List[Dict[str, str]]]: Dicionário com mapeamento de referências
        """
        try:
            references = {}
            for index, path in enumerate(self.paths):
                references[f"e{index:05d}v"] = path

            return {"referencia": [references]}
        except Exception as e:
            logger.exception("Erro inesperado ao gerar referências: %s", e)
            return {"referencia": [{}]}
    
    def replace_paths_with_references(self, data: Any, references: Dict) -> Any:
        """
        Substitui todos os caminhos pelos seus códigos de referência
        Parâmetros:
            data (Any): A estrutura de dados onde os caminhos serão substituídos
            references (Dict): O dicionário de referências gerado por generate_references()
        Retorno:
            Any: A estrutura de dados com os caminhos substituídos pelos códigos de referência
        """
        try:
            ref_dict = references["referencia"][0]
            sorted_refs = dict(sorted(ref_dict.items(), key=lambda x: len(x[1]), reverse=True))
            replacer = PathReplacer(sorted_refs)
            return replacer.replace(data)
        except Exception as e:
            logger.exception("Erro inesperado ao substituir caminhos por referências: %s", e)
            return data

class PathReplacer:
    """
    Trata a lógica de substituição de caminhos
    """
    
    def __init__(self, reference_dict: Dict[str, str]):
        # Inicializa com o dicionário de referência
        self.reference_dict = reference_dict
    
    def replace(self, obj: Any) -> Any:
        """
        Substitui recursivamente os caminhos no objeto
        Parâmetros:
            obj (Any): O objeto (lista, dicionário, string, etc.) onde os caminhos serão substituídos
        Retorno:
            Any: O objeto com os caminhos substituídos pelos códigos de referência
        """
        try:
            if isinstance(obj, list):
                return [self.replace(item) for item in obj]
            elif isinstance(obj, dict):
                if "value" in obj and "path" in obj and "update" in obj:
                    obj["value"] = self._replace_in_formula(obj["value"])

                if "path" in obj:
                    obj["path"] = self._replace_direct_path(obj["path"])

                for key in ["data", "childs", "fields", "formulas"]:
                    if key in obj:
                        obj[key] = self.replace(obj[key])

            return obj
        except Exception as e:
            logger.exception("Erro inesperado ao substituir caminhos no objeto: %s", e)
            return obj
    
    def _replace_direct_path(self, path: str) -> str:
        """
        Substitui correspondências exatas de caminho
        Parâmetros:
            path (str): O caminho a ser substituído
        Retorno:
            str: O código de referência correspondente ou o caminho original se não encontrado
        """
        try:
            for code, original_path in self.reference_dict.items():
                if path == original_path:
                    return code
            return path
        except Exception as e:
            logger.exception("Erro inesperado ao substituir caminho direto %s: %s", path, e)
            return path
    
    def _replace_in_formula(self, formula: str) -> str:
        """
        Substitui caminhos dentro de strings de fórmula
        Parâmetros:
            formula (str): A fórmula onde os caminhos serão substituídos
        Retorno:
            str: A fórmula com os caminhos substituídos pelos códigos de referência
        """
        try:
            if not isinstance(formula, str):
                return formula

            result = formula
            for code, original_path in self.reference_dict.items():
                pattern = r'(^|\W)(' + re.escape(original_path) + r')(\W|$)'

                def replace_match(match):
                    return match.group(1) + code + match.group(3)

                result = re.sub(pattern, replace_match, result)

            return result
        except Exception as e:
            logger.exception("Erro inesperado ao substituir caminhos na fórmula: %s", e)
            return formula

class FormulaProcessor:
    """
    Processa e extrai fórmulas para doctypes específicos
    """
    
    def __init__(self, formulas: List[Dict], field_path_finder):
        # Inicializa com a lista de fórmulas e o localizador de caminhos de campo
        self.formulas = formulas
        self.field_path_finder = field_path_finder
    
    def get_doctype_formulas(self, doctype_name: str) -> List[FormulaData]:
        """
        Obtem todas as fórmulas para um doctype específico
        Parâmetros:
            doctype_name (str): Nome do doctype para o qual as fórmulas são extraídas
        Retorno:
            List[FormulaData]: Lista de objetos FormulaData para o doctype
        """
        try:
            doctype_formulas = []
            table_formulas = self.formulas[0].get("tableformulas", [])

            for formula in table_formulas:
                try:
                    if formula.get("groupfielddoctype") == doctype_name:
                        path = self.field_path_finder(
                            formula["groupfielddoctype"],
                            formula["groupfieldfieldname"]
                        )
                        if path:
                            formula_data = FormulaData(
                                path=path,
                                value=formula["formula"],
                                update={
                                    "doctype": formula["groupfielddoctype"],
                                    "fieldname": formula["groupfieldfieldname"]
                                }
                            )
                            doctype_formulas.append(formula_data)
                except Exception as e:
                    logger.exception("Erro ao processar fórmula individual: %s", e)
                    continue

            return doctype_formulas
        except Exception as e:
            logger.exception("Erro inesperado ao obter fórmulas do doctype %s: %s", doctype_name, e)
            return []

class FieldPathFinder:
    """
    Encontra caminhos de campo na árvore de doctype
    """
    
    def __init__(self, doctype_tree: List[Dict]):
        # Inicializa com a árvore de doctype
        self.doctype_tree = doctype_tree
    
    def find(self, doctype_name: str, field_name: str) -> Optional[str]:
        """
        Localiza o caminho para um campo específico em um doctype
        Parâmetros:
            doctype_name (str): Nome do doctype
            field_name (str): Nome do campo
        Retorno:
            Optional[str]: O caminho do campo se encontrado, None caso contrário
        """
        try:
            return self._search_recursive(self.doctype_tree, doctype_name, field_name)
        except Exception as e:
            logger.exception("Erro inesperado ao buscar campo %s no doctype %s: %s", field_name, doctype_name, e)
            return None
    
    def _search_recursive(self, nodes: List[Dict], doctype_name: str,
                         field_name: str, current_path: Optional[str] = None) -> Optional[str]:
        """
        Busca recursivamente o caminho do campo
        Parâmetros:
            nodes (List[Dict]): Lista de nós atuais na árvore
            doctype_name (str): Nome do doctype a procurar
            field_name (str): Nome do campo a procurar
            current_path (Optional[str]): Caminho atual na recursão
        Retorno:
            Optional[str]: O caminho do campo se encontrado, None caso contrário
        """
        try:
            for node in nodes:
                try:
                    if node.get("type") == "doctype" and node.get("fieldname") == doctype_name:
                        for child in node.get("children", []):
                            if child.get("fieldname") == field_name:
                                return child.get("path")

                    result = self._search_recursive(
                        node.get("children", []),
                        doctype_name,
                        field_name,
                        current_path
                    )

                    if result:
                        return result
                except Exception as e:
                    logger.exception("Erro ao processar nó durante busca recursiva: %s", e)
                    continue

            return None
        except Exception as e:
            logger.exception("Erro inesperado na busca recursiva: %s", e)
            return None

class DoctypeIndexManager:
    """
    Gerencia os índices de processamento de doctype
    """
    
    def __init__(self):
        # Inicializa o dicionário de índices
        self.indices: Dict[str, int] = {}
    
    def get_index(self, path: str, reset: bool = False) -> int:
        """
        Obtém o índice atual para o caminho
        Parâmetros:
            path (str): O caminho do doctype
            reset (bool): Se True, reseta o índice para 0
        Retorno:
            int: O índice atual para o caminho
        """
        try:
            if reset or path not in self.indices:
                self.indices[path] = 0
            return self.indices[path]
        except Exception as e:
            logger.exception("Erro inesperado ao obter índice para caminho %s: %s", path, e)
            return 0
    
    def increment_index(self, path: str) -> None:
        """
        Incrementa o índice para o caminho
        Parâmetros:
            path (str): O caminho do doctype
        """
        try:
            self.indices[path] = self.indices.get(path, 0) + 1
        except Exception as e:
            logger.exception("Erro inesperado ao incrementar índice para caminho %s: %s", path, e)

class PathAnalyzer:
    """
    Analisa caminhos de fórmula para determinar campos necessários
    """

    def __init__(self, unique_paths: List[str]):
        # Inicializa com uma lista de caminhos únicos
        self.unique_paths = unique_paths
        self.required_fields = self._analyze_paths()
    
    def _analyze_paths(self) -> Dict[str, Set[str]]:
        """
        Analisa caminhos e retorna campos necessários por doctype
        Retorno:
            Dict[str, Set[str]]: Dicionário mapeando caminhos de doctype para conjuntos de campos necessários
        """
        try:
            required = {}

            for path in self.unique_paths:
                try:
                    parts = path.split('.')

                    for i in range(len(parts)):
                        if i == len(parts) - 1:
                            parent_path = '.'.join(parts[:i]) if i > 0 else parts[0]
                            if parent_path not in required:
                                required[parent_path] = set()
                            required[parent_path].add(parts[i])
                        else:
                            current_path = '.'.join(parts[:i+1])
                            if current_path not in required:
                                required[current_path] = set()
                except Exception as e:
                    logger.exception("Erro ao analisar caminho individual %s: %s", path, e)
                    continue

            return required
        except Exception as e:
            logger.exception("Erro inesperado ao analisar caminhos: %s", e)
            return {}
    
    def get_required_fields(self, doctype_path: str) -> Set[str]:
        """
        Obtem campos necessários para um caminho de doctype específico
        Parâmetros:
            doctype_path (str): O caminho do doctype
        Retorno:
            Set[str]: Conjunto de campos necessários para o doctype
        """
        try:
            return self.required_fields.get(doctype_path, set())
        except Exception as e:
            logger.exception("Erro inesperado ao obter campos necessários para %s: %s", doctype_path, e)
            return set()
    
    def is_path_required(self, path: str) -> bool:
        """
        Verifica se um caminho ou qualquer um de seus filhos é necessário
        Parâmetros:
            path (str): O caminho a ser verificado
        Retorno:
            bool: True se o caminho ou qualquer filho for necessário, False caso contrário
        """
        try:
            if path in self.required_fields:
                return True

            for required_path in self.required_fields:
                if required_path.startswith(path + "."):
                    return True

            if "." in path:
                parts = path.rsplit(".", 1)
                parent_path = parts[0]
                field_name = parts[1]

                if parent_path in self.required_fields:
                    required_fields_for_parent = self.required_fields[parent_path]
                    if field_name in required_fields_for_parent:
                        return True

            return False
        except Exception as e:
            logger.exception("Erro inesperado ao verificar se caminho é necessário %s: %s", path, e)
            return False

class DataTraverser:
    """
    Percorre e processa os dados do doctype
    """
    
    def __init__(
            self, 
            all_doctype_data: List[Dict], 
            path_manager: PathManager,
            formula_processor: FormulaProcessor, 
            child_name: str = "childs",
            path_analyzer: Optional['PathAnalyzer'] = None):
        # Inicializa com dados, gerenciador de caminhos, processador de fórmulas e analisador de caminhos
        self.all_doctype_data = all_doctype_data
        self.path_manager = path_manager
        self.formula_processor = formula_processor
        self.child_name = child_name
        self.index_manager = DoctypeIndexManager()
        self.default_provider = DefaultValueProvider()
        self.path_analyzer = path_analyzer
    
    def get_doctype_data(self, doctype_name: str) -> List[Dict]:
        """
        Obtém dados para um doctype específico
        Parâmetros:
            doctype_name (str): Nome do doctype
        Retorno:
            List[Dict]: Lista de dados para o doctype, ou lista vazia se não encontrado
        """
        try:
            for data_dict in self.all_doctype_data:
                if doctype_name in data_dict:
                    return data_dict[doctype_name]
            return []
        except Exception as e:
            logger.exception("Erro inesperado ao obter dados do doctype %s: %s", doctype_name, e)
            return []
    
    def traverse_doctype(self, node: Dict, parent_head: Optional[EngineDataHead] = None,
                        doctype_data: Optional[List[Dict]] = None,
                        reset_index: bool = False,
                        parent_item: Optional[EngineDataItem] = None) -> Optional[EngineDataHead]:
        """
        Percorre e processa um nó de doctype
        Parâmetros:
            node (Dict): O nó do doctype a ser processado
            parent_head (Optional[EngineDataHead]): A cabeça pai para anexar novos dados (se None, retorna nova cabeça)
            doctype_data (Optional[List[Dict]]): Dados específicos do doctype (se None, obtém automaticamente)
            reset_index (bool): Se True, reseta o índice de processamento para este doctype
            parent_item (Optional[EngineDataItem]): O item pai para anexar novos dados (se None, usa a cabeça pai)
        Retorno:
            Optional[EngineDataHead]: A nova cabeça criada (se parent_head for None), caso contrário None
        """
        try:
            self.path_manager.add_path(node["path"])

            if doctype_data is None:
                doctype_data = self.get_doctype_data(node["fieldname"])

            formulas = self.formula_processor.get_doctype_formulas(node["fieldname"])

            new_head = EngineDataHead(
                path=node["path"],
                formulas=formulas,
                data=[]
            )

            if parent_item is not None:
                parent_item.childs.append(new_head)
            elif parent_head and parent_head.data:
                parent_head.data[-1].childs.append(new_head)

            self._process_doctype_data(
                node["children"],
                new_head,
                doctype_data,
                node["path"],
                reset_index
            )

            return new_head if parent_head is None else None
        except Exception as e:
            logger.exception("Erro inesperado ao percorrer doctype %s: %s", node.get("fieldname", "desconhecido"), e)
            return None
    
    def _process_doctype_data(self, nodes: List[Dict], head: EngineDataHead,
                             doctype_data: List[Dict], path: str, reset_index: bool):
        """
        Processa os dados para um doctype
        Parâmetros:
            nodes (List[Dict]): Lista de nós filhos do doctype
            head (EngineDataHead): A cabeça onde os dados serão anexados
            doctype_data (List[Dict]): Dados específicos do doctype
            path (str): O caminho do doctype
            reset_index (bool): Se True, reseta o índice de processamento para este doctype
        """
        try:
            index = self.index_manager.get_index(path, reset_index)

            if doctype_data and index < len(doctype_data):
                for data_item in doctype_data[index:]:
                    try:
                        self.index_manager.increment_index(path)
                        engine_item = self._create_engine_item(nodes, data_item, head, path)
                        if engine_item:
                            if not engine_item.is_empty() or engine_item.has_children():
                                head.data.append(engine_item)
                    except Exception as e:
                        logger.exception("Erro ao processar item de dados: %s", e)
                        continue
            else:
                try:
                    engine_item = self._create_empty_engine_item(nodes, head, path)
                    if engine_item:
                        if not engine_item.is_empty() or engine_item.has_children():
                            head.data.append(engine_item)
                except Exception as e:
                    logger.exception("Erro ao criar item vazio: %s", e)
        except Exception as e:
            logger.exception("Erro inesperado ao processar dados do doctype %s: %s", path, e)
    
    def _create_engine_item(self, nodes: List[Dict], data: Dict,
                           head: EngineDataHead, current_path: str = "") -> Optional[EngineDataItem]:
        """
        Criar um item de dados do motor a partir dos dados do doctype
        Parâmetros:
            nodes (List[Dict]): Lista de nós filhos do doctype
            data (Dict): Dados específicos do doctype
            head (EngineDataHead): A cabeça onde o item será anexado
            current_path (str): O caminho atual do doctype
        Retorno:
            Optional[EngineDataItem]: O item criado, ou None se não puder ser criado
        """
        try:
            engine_item = EngineDataItem(
                id=data.get("name", ""),
                creation=data.get("creation", self.default_provider.DEFAULT_CREATION_DATE)
            )

            for node in nodes:
                try:
                    if not self.path_analyzer or self.path_analyzer.is_path_required(node["path"]):
                        self.path_manager.add_path(node["path"])

                    if node["type"] == "doctype":
                        if self.path_analyzer and not self.path_analyzer.is_path_required(node["path"]):
                            continue

                        if node.get("fieldname_data"):
                            nested_data = data.get(node["fieldname_data"], [])
                        else:
                            nested_data = self.get_doctype_data(node["fieldname"])

                        if engine_item:
                            self.traverse_doctype(node, head, nested_data, True, engine_item)
                    else:
                        if engine_item is not None:
                            field_name = node.get("fieldname", "")
                            field_path = node.get("path", "")

                            if (not self.path_analyzer or
                                self.path_analyzer.is_path_required(field_path)):

                                value = data.get(field_name, None)
                                field_data = FieldData(
                                    path=node["path"],
                                    type=node["type"],
                                    value=value
                                )
                                engine_item.fields.append(field_data)
                except Exception as e:
                    logger.exception("Erro ao processar nó durante criação de item: %s", e)
                    continue

            return engine_item
        except Exception as e:
            logger.exception("Erro inesperado ao criar item do motor: %s", e)
            return None
    
    def _create_empty_engine_item(self, nodes: List[Dict],
                                 head: EngineDataHead, current_path: str = "") -> Optional[EngineDataItem]:
        """
        Cria um item de mecanismo vazio com valores padrão
        Parâmetros:
            nodes (List[Dict]): Lista de nós filhos do doctype
            head (EngineDataHead): A cabeça onde o item será anexado
            current_path (str): O caminho atual do doctype
        Retorno:
            Optional[EngineDataItem]: O item criado, ou None se não puder ser criado
        """
        try:
            engine_item = EngineDataItem(
                id="",
                creation=self.default_provider.DEFAULT_CREATION_DATE
            )

            for node in nodes:
                try:
                    if not self.path_analyzer or self.path_analyzer.is_path_required(node["path"]):
                        self.path_manager.add_path(node["path"])

                    if node["type"] == "doctype":
                        if self.path_analyzer and not self.path_analyzer.is_path_required(node["path"]):
                            continue

                        if engine_item:
                            self.traverse_doctype(node, head, [], True, engine_item)
                    else:
                        if engine_item is not None:
                            field_path = node.get("path", "")

                            if (not self.path_analyzer or
                                self.path_analyzer.is_path_required(field_path)):

                                default_value = self.default_provider.get_default(node["type"])
                                field_data = FieldData(
                                    path=node["path"],
                                    type=node["type"],
                                    value=default_value
                                )
                                engine_item.fields.append(field_data)
                except Exception as e:
                    logger.exception("Erro ao processar nó durante criação de item vazio: %s", e)
                    continue

            return engine_item
        except Exception as e:
            logger.exception("Erro inesperado ao criar item vazio do motor: %s", e)
            return None

class EngineDataBuilder:
    """
    Classe principal para construção da estrutura de dados do motor
    """
    
    # def __init__(
    #         self, 
    #         doctype_tree: List[Dict], 
    #         formulas: List[Dict],
    #         all_doctype_data: List[Dict], 
    #         child_name: str = "childs",
    #         compact_mode: bool = False):

    def __init__(
            self, 
            doctype_tree: List[Dict], 
            formulas: List[Dict],
            all_doctype_data: List[Dict], 
            child_name: str = "childs"):    
        
        # Inicializa com árvore de doctype, fórmulas, dados e opções 
        self.doctype_tree = doctype_tree
        self.formulas = formulas
        self.all_doctype_data = all_doctype_data
        self.child_name = child_name
        #self.compact_mode = compact_mode

        # Inicializa componentes
        self.path_manager = PathManager()
        self.field_finder = FieldPathFinder(doctype_tree)
        self.formula_processor = FormulaProcessor(formulas, self.field_finder.find)

        # Extrai caminhos únicos das fórmulas
        #self.unique_formulas = self.extract_formulas_paths() if compact_mode else []
        self.unique_formulas = self.extract_formulas_paths()

        # Cria analisador de caminho se estiver no modo compacto
        # path_analyzer = PathAnalyzer(self.unique_formulas) if compact_mode else None
        path_analyzer = PathAnalyzer(self.unique_formulas)
        
        self.traverser = DataTraverser(
            all_doctype_data, 
            self.path_manager, 
            self.formula_processor,
            child_name,
            path_analyzer
        )
    
    def build(self) -> Dict[str, Any]:
        """
        Constrói a estrutura de dados completa do motor
        Retorno:
            Dict[str, Any]: A estrutura de dados do motor pronta para uso
        """
        try:
            result = []

            for root in self.doctype_tree:
                try:
                    # if self.compact_mode and self.traverser.path_analyzer:
                    if self.traverser.path_analyzer:
                        if not self.traverser.path_analyzer.is_path_required(root.get("path", "")):
                            continue

                    head = self.traverser.traverse_doctype(root)
                    if head:
                        result.append(head)
                except Exception as e:
                    logger.exception("Erro ao processar nó raiz: %s", e)
                    continue

            references = self.path_manager.generate_references()

            result_dicts = [head.to_dict(self.child_name, compact=True) for head in result]

            sorted_refs = {
                "referencia": [
                    dict(sorted(references["referencia"][0].items(),
                               key=lambda x: len(x[1]), reverse=True))
                ]
            }
            result_with_refs = self.path_manager.replace_paths_with_references(
                result_dicts,
                sorted_refs
            )

            return {
                "referencia": references["referencia"],
                "data": result_with_refs
            }
        except Exception as e:
            logger.exception("Erro inesperado ao construir estrutura de dados: %s", e)
            return {"referencia": [[]], "data": []}
    
    def extract_formulas_paths(self) -> List[str]:
        """
        Extrai caminhos únicos das fórmulas
        Retorno:
            List[str]: Lista de caminhos únicos encontrados nas fórmulas
        """
        try:
            path_pattern = r'[a-zA-Z][a-zA-Z0-9_]*\.[a-zA-Z0-9_.]*[a-zA-Z0-9_]+'

            formulas = "\n".join([
                item["formula"]
                for group in self.formulas
                for item in group.get("tableformulas", [])
                if "formula" in item
            ])

            paths = re.findall(path_pattern, formulas)

            unique_paths = []
            for path in paths:
                if path not in unique_paths:
                    unique_paths.append(path)

            for group in self.formulas:
                try:
                    for item in group.get("tableformulas", []):
                        try:
                            if "groupfielddoctype" in item and "groupfieldfieldname" in item:
                                path = self.field_finder.find(
                                    item["groupfielddoctype"],
                                    item["groupfieldfieldname"]
                                )
                                if path and path not in unique_paths:
                                    unique_paths.append(path)
                        except Exception as e:
                            logger.exception("Erro ao processar item de fórmula: %s", e)
                            continue
                except Exception as e:
                    logger.exception("Erro ao processar grupo de fórmulas: %s", e)
                    continue

            return unique_paths
        except Exception as e:
            logger.exception("Erro inesperado ao extrair caminhos das fórmulas: %s", e)
            return []


