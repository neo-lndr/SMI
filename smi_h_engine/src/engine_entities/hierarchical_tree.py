"""
Hierarchical tree builder para o motor de cálculos.
Constrói uma representação hierárquica (entidades e campos) a partir dos dados de doctypes,
fornecendo a estrutura necessária para ordenar e executar cálculos, alem de ser utilizado
pela interface de construção de fórmulas.

Responsabilidades principais:
 - Converter doctypes e campos em entidades hierárquicas (nós, filhos, tipos e paths).
 - Aplicar mapeamentos obrigatórios e opcionais entre entidades.
 - Normalizar nomes/paths e mapear tipos de campo para o modelo hierárquico.
 - Persistir/fornecer a estrutura pronta para consumo pelos módulos do motor de cálculo.

Posição na arquitetura:
 - Camada de preparação de metadados, imediatamente acima do motor de execução de cálculos;
    fornece a estrutura que o orquestrador de cálculos utiliza para determinar dependências e ordem.

Dependências críticas:
 - Fornecedores de configuração: objeto `mappings` (mapeamentos especificados) e `translations`.
 - Fonte dos doctypes: estrutura JSON passada para build_tree (ex.: FileManager.load_json).
 - Módulos padrão: json, unicodedata, re, logging; tipagens para segurança em tempo de desenvolvimento.

Considerações de segurança:
 - Não executar código derivado de metadados (evitar eval/exec). Limitar leitura/escrita a caminhos
    de arquivo controlados e tratar dados sensíveis (PII) com cuidado ao serializar.

Exemplo básico de uso:
     translations = Translations(...)    # objeto que implementa get_translations()
     mappings = Mappings(...)            # objeto que implementa get_specific_mapping()
     all_doctypes = FileManager.load_json("doctypes.json")
     builder = HierarchicalTreeBuilder(translations, mappings)
     tree = builder.build_tree(all_doctypes)
     FileManager.save_json(tree, "hierarchical_tree.json")
"""

import re
import unicodedata
import logging
from typing import Dict, List, Set, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

@dataclass
class Entity:
    """
    Classe que representa uma entidade na estrutura hierárquica.
    """
    # Atributos principais
    # Chave
    key: str
    # Descrição
    description: str
    # Nome do campo (para entidades de doctype)
    fieldname: str
    # Nome do campo de dados (para entidades de doctype)
    fieldname_data: str = ""
    # Tipo (string, numeric, date, boolean, doctype, key)
    type: str = "doctype"
    # Caminho hierárquico
    path: str = ""
    # Permite drag and drop na UI
    dragandrop: bool = False
    # Filhos (outras entidades)
    children: List['Entity'] = field(default_factory=list)
    # Ícone representativo
    icon: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Converte a entidade para uma representação em dicionário
        """
        try:
            field = {
                "key": self.key,
                "description": self.description,
                "fieldname": self.fieldname,
                "fieldname_data": self.fieldname_data,
                "type": self.type,
                "path": self.path,
                "dragandrop": self.dragandrop,
                "icon": self.icon,
                "children": [child.to_dict() for child in self.children],
            }
            return field
        except Exception as e:
            logger.exception("Erro inesperado convertendo entidade para dicionário: %s", e)
            return {}
 
    def add_child(self, child: 'Entity') -> None:
        """
        Adiciona uma entidade filha
        Parâmetros:
            child (Entity): A entidade filha a ser adicionada
        """
        try:
            self.children.append(child)
        except Exception as e:
            logger.exception("Erro inesperado adicionando entidade filha: %s", e)
    
    def has_child_with_key(self, key: str) -> bool:
        """
        Verifica se a entidade tem um filho com a chave dada
        Parâmetros:
            key (str): A chave a ser verificada
        Retorno:
            bool: True se um filho com a chave existir, False caso contrário
        """
        try:
            return any(child.key == key for child in self.children)
        except Exception as e:
            logger.exception("Erro inesperado verificando filho com chave: %s", e)
            return False
    
    def find_child_by_key(self, key: str) -> Optional['Entity']:
        """
        Encontra um filho pela sua chave
        Parâmetros:
            key (str): A chave do filho a ser encontrado
        Retorno:
            Entity or None: A entidade filha se encontrada, ou None caso contrário
        """
        try:
            for child in self.children:
                if child.key == key:
                    return child
            return None
        except Exception as e:
            logger.exception("Erro inesperado procurando filho por chave: %s", e)
            return None
    
    def remove_child_by_key(self, key: str) -> None:
        """
        Remove um filho pela sua chave
        Parâmetros:
            key (str): A chave do filho a ser removido
        """
        try:
            self.children = [child for child in self.children if child.key != key]
        except Exception as e:
            logger.exception("Erro inesperado removendo filho por chave: %s", e)

class StringNormalizer:
    """
    Responsável pela normalização de strings para caminhos e chaves
    """
    
    @staticmethod
    def normalize(s: str) -> str:
        """
        Normaliza a string para uso em caminhos
        Parâmetros:
            s (str): A string a ser normalizada
        Retorno:
            str: A string normalizada
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
    
    @staticmethod
    def create_key(name: str) -> str:
        """
        Cria uma chave a partir de um nome
        Parâmetros:
            name (str): O nome a partir do qual criar a chave
        Retorno:
            str: A chave criada
        """
        try:
            return name.replace(" ", "_")
        except Exception as e:
            logger.exception("Erro inesperado criando chave: %s", e)
            return ""

class FieldTypeMapper:
    """
    Mapeia tipos de campo para tipos do modelo hierárquico
    """
    # Mapeamento de tipos
    TYPE_MAPPING = {
        "Data": "string",
        "Date": "date",
        "Datetime": "datetime",
        "Int": "numeric",
        "Float": "numeric",
        "Currency": "numeric",
        "Check": "boolean",
        "Select": "string",
        "Long Text": "string",
        "Small Text": "string",
        "Text": "string",
        "Text Editor": "string",
        "Table": "doctype"
    }
    
    @classmethod
    def map_type(cls, fieldtype: str) -> str:
        """
        Mapeia o tipo de campo para o tipo do modelo hierárquico
        Parâmetros:
            fieldtype (str): O tipo de campo a ser mapeado
        Retorno:
            str: O tipo mapeado
        """
        try:
            return cls.TYPE_MAPPING.get(fieldtype, "string")
        except Exception as e:
            logger.exception("Erro inesperado mapeando tipo de campo: %s", e)
            return "string"

class MappingManager:
    """
    Gerencia relacionamentos pai-filho e mapeamentos
    """

    def __init__(self, specified_mappings: List[Dict[str, str]]):
        """
        Inicializa o gerenciador de mapeamentos com os mapeamentos especificados
        """
        self.specified_mappings = specified_mappings
        self.mandatory_children: Dict[str, List[str]] = {}
        self.mandatory_parents: Dict[str, List[str]] = {}
        self.child_to_parent_map: Dict[str, str] = {}
        self._build_lookup_tables()
    
    def _build_lookup_tables(self) -> None:
        """
        Constrói tabelas de consulta para acesso eficiente
        """
        try:
            for mapping in self.specified_mappings:
                child = mapping["child"]
                parent = mapping["parent"]

                if child not in self.mandatory_parents:
                    self.mandatory_parents[child] = []

                self.mandatory_parents[child].append(parent)

                if parent not in self.mandatory_children:
                    self.mandatory_children[parent] = []

                self.mandatory_children[parent].append(child)
                self.child_to_parent_map[child] = parent
        except Exception as e:
            logger.exception("Erro inesperado construindo tabelas de consulta: %s", e)
    
    def has_mandatory_parent(self, child: str) -> bool:
        """
        Verifica se um filho tem pais obrigatórios
        Parâmetros:
            child (str): O nome do filho a ser verificado
        Retorno:
            bool: True se o filho tiver pais obrigatórios, False caso contrário
        """
        try:
            return child in self.mandatory_parents
        except Exception as e:
            logger.exception("Erro inesperado verificando pais obrigatórios: %s", e)
            return False
    
    def get_mandatory_parents(self, child: str) -> List[str]:
        """
        Obtém os pais obrigatórios de um filho
        Parâmetros:
            child (str): O nome do filho cujos pais obrigatórios serão obtidos
        Retorno:
            List[str]: Uma lista de nomes de pais obrigatórios
        """
        try:
            return self.mandatory_parents.get(child, [])
        except Exception as e:
            logger.exception("Erro inesperado obtendo pais obrigatórios: %s", e)
            return []
    
    def get_mandatory_children(self, parent: str) -> List[str]:
        """
        Obtém os filhos obrigatórios de um pai
        Parâmetros:
            parent (str): O nome do pai cujos filhos obrigatórios serão obtidos
        Retorno:
            List[str]: Uma lista de nomes de filhos obrigatórios
        """
        try:
            return self.mandatory_children.get(parent, [])
        except Exception as e:
            logger.exception("Erro inesperado obtendo filhos obrigatórios: %s", e)
            return []
    
    def is_valid_optional_child(self, parent: str, child: str) -> bool:
        """
        Verifica se um filho pode ser adicionado opcionalmente a um pai
        Parâmetros:
            parent (str): O nome do pai
            child (str): O nome do filho
        Retorno:
            bool: True se o filho puder ser adicionado opcionalmente ao pai, False caso contrário
        """
        try:
            if self.has_mandatory_parent(child) and parent not in self.mandatory_parents[child]:
                return False

            if child in self.get_mandatory_children(parent):
                return False

            return True
        except Exception as e:
            logger.exception("Erro inesperado validando filho opcional: %s", e)
            return False
    
    def get_proper_parent(self, child: str) -> Optional[str]:
        """
        Obtém o pai adequado para um filho com base nos mapeamentos
        Parâmetros:
            child (str): O nome do filho cujo pai adequado será obtido
        Retorno:
            Optional[str]: O nome do pai adequado, ou None se não houver mapeamento
        """
        try:
            return self.child_to_parent_map.get(child)
        except Exception as e:
            logger.exception("Erro inesperado obtendo pai adequado: %s", e)
            return None
    
    def get_children_to_remove_from_root(self) -> Set[str]:
        """
        Obtém o conjunto de filhos que não devem estar no nível raiz
        Retorno:
            Set[str]: Um conjunto de nomes de filhos que não devem estar no nível raiz
        """
        try:
            normalizer = StringNormalizer()
            return {normalizer.create_key(mapping["child"])
                    for mapping in self.specified_mappings}
        except Exception as e:
            logger.exception("Erro inesperado obtendo filhos para remover da raiz: %s", e)
            return set()

class EntityFactory:
    """
    Factory para criar diferentes tipos de entidades
    """
    
    def __init__(self, normalizer: StringNormalizer,
                 type_mapper: FieldTypeMapper,
                 translations: Optional[Dict[str, str]] = None):
        self.normalizer = normalizer
        self.type_mapper = type_mapper
        self.translations = translations or {}
    
    def create_doctype_entity(self,
                              doctype_name: str,
                              fieldname_data: str = "") -> Entity:
        """
        Cria uma entidade doctype
        Parâmetros:
            doctype_name (str): O nome do doctype
            fieldname_data (str): O nome do campo de dados associado (opcional)
        Retorno:
            Entity: A entidade doctype criada
        """
        try:
            doctype_key = self.normalizer.create_key(doctype_name)
            translated_name = self.translations.get(doctype_key, doctype_name)

            entity = Entity(
                key=doctype_key,
                description=translated_name,
                fieldname=doctype_name,
                fieldname_data=fieldname_data,
                type="doctype",
                path=self.normalizer.normalize(translated_name),
                dragandrop=False,
                icon="text"
            )

            entity.add_child(self.create_key_field())
            return entity
        except Exception as e:
            logger.exception("Erro inesperado criando entidade doctype: %s", e)
            return None # type: ignore
    
    def create_key_field(self) -> Entity:
        """
        Cria o campo chave padrão (Identificador - name para doctypes)
        Retorno:
            Entity: A entidade do campo chave criada
        """
        try:
            return Entity(
                key="chave",
                description="Chave do registro",
                fieldname="name",
                type="key",
                path=self.normalizer.normalize("Chave do registro"),
                dragandrop=True,
                icon="key"
            )
        except Exception as e:
            logger.exception("Erro inesperado criando campo chave: %s", e)
            return None # type: ignore
    
    def create_field_entity(self, field_data: Dict[str, Any]) -> Entity:
        """
        Cria uma entidade de campo a partir dos dados do campo
        Parâmetros:
            field_data (Dict[str, Any]): Dicionário contendo os dados do campo
        Retorno:
            Entity: A entidade do campo criada
        """
        try:
            field_type = self.type_mapper.map_type(field_data.get("fieldtype", ""))
            field_label = field_data.get("label", "")
            field_key = self.normalizer.create_key(field_label)
            field_icon = self.apply_icon(field_data.get("fieldtype", ""))

            return Entity(
                key=field_key,
                description=field_label,
                fieldname=field_data.get("fieldname", ""),
                fieldname_data=field_data.get("fieldname_data", ""),
                type=field_type,
                path=self.normalizer.normalize(field_label),
                dragandrop=True,
                icon=field_icon
            )
        except Exception as e:
            logger.exception("Erro inesperado criando entidade de campo: %s", e)
            return None # type: ignore
    

    def apply_icon(self, type: str) -> str:
        """
        Aplica o ícone apropriado com base no tipo de campo
        Parâmetros:
            type (str): O tipo de campo
        Retorno:
            str: O nome do ícone correspondente
        """
        try:
            icon_map = {
                "Link": "key",
                "Float": "number",
                "Currency": "money",
                "Int": "integer",
                "Data": "text",
                "Select": "text",
                "Date": "calendar",
                "Datetime": "calendar",
            }
            icon = icon_map.get(type)

            if not icon:
                icon = "text"

            return icon
        except Exception as e:
            logger.exception("Erro inesperado aplicando ícone: %s", e)
            return "text"

class PathManager:
    """
    Gerencia atualizações de caminho na estrutura hierárquica
    """
    
    def __init__(self, normalizer: StringNormalizer):
        """
        Inicializa o gerenciador de caminhos com o normalizador
        """
        self.normalizer = normalizer
    
    def update_all_paths(self, entities: List[Entity]) -> None:
        """
        Atualiza todos os caminhos na hierarquia
        Parâmetros:
            entities (List[Entity]): A lista de entidades raiz cuja hierarquia terá os caminhos atualizados
        """
        try:
            for entity in entities:
                entity.path = self.normalizer.normalize(entity.description)
                self._update_child_paths(entity, entity.path)
        except Exception as e:
            logger.exception("Erro inesperado atualizando todos os caminhos: %s", e)
    
    def _update_child_paths(self, parent: Entity, parent_path: str) -> None:
        """
        Atualiza recursivamente os caminhos dos filhos
        Parâmetros:
            parent (Entity): A entidade pai cujos filhos terão os caminhos atualizados
            parent_path (str): O caminho do pai
        """
        try:
            for child in parent.children:
                child_path = self.normalizer.normalize(child.description)
                child.path = f"{parent_path}.{child_path}"
                self._update_child_paths(child, child.path)
        except Exception as e:
            logger.exception("Erro inesperado atualizando caminhos dos filhos: %s", e)

class EntityTreeNavigator:
    """
    Navega e pesquisa entidades na árvore
    """

    @staticmethod
    def find_entity_by_key(entities: List[Entity], key: str) -> Optional[Entity]:
        """
        Localiza uma entidade pela sua chave na árvore
        Parâmetros:
            entities (List[Entity]): A lista de entidades raiz onde a pesquisa será realizada
            key (str): A chave da entidade a ser localizada
        Retorno:
            Optional[Entity]: A entidade encontrada, ou None se não encontrada
        """
        try:
            for entity in entities:
                if entity.key == key:
                    return entity

                result = EntityTreeNavigator._find_in_children(entity, key)
                if result:
                    return result
            return None
        except Exception as e:
            logger.exception("Erro inesperado procurando entidade por chave: %s", e)
            return None
    
    @staticmethod
    def _find_in_children(parent: Entity, key: str) -> Optional[Entity]:
        """
        Pesquisa recursivamente nos filhos
        Parâmetros:
            parent (Entity): A entidade pai cujos filhos serão pesquisados
            key (str): A chave da entidade a ser localizada
        Retorno:
            Optional[Entity]: A entidade encontrada, ou None se não encontrada
        """
        try:
            for child in parent.children:
                if child.key == key:
                    return child
                result = EntityTreeNavigator._find_in_children(child, key)
                if result:
                    return result
            return None
        except Exception as e:
            logger.exception("Erro inesperado procurando nos filhos: %s", e)
            return None
    
    @staticmethod
    def remove_entity_from_tree(entities: List[Entity], key: str) -> None:
        """
        Remove a entidade correspondente a chave
        Parâmetros:
            entities (List[Entity]): A lista de entidades raiz onde a remoção será realizada
            key (str): A chave da entidade a ser removida
        """
        try:
            for entity in entities:
                entity.remove_child_by_key(key)
                EntityTreeNavigator._remove_from_children(entity, key)
        except Exception as e:
            logger.exception("Erro inesperado removendo entidade da árvore: %s", e)
    
    @staticmethod
    def _remove_from_children(parent: Entity, key: str) -> None:
        """
        Remove entidade filho com a chave dada recursivamente
        Parâmetros:
            parent (Entity): A entidade pai cujos filhos serão verificados para remoção
            key (str): A chave da entidade a ser removida
        """
        try:
            for child in parent.children:
                child.remove_child_by_key(key)
                EntityTreeNavigator._remove_from_children(child, key)
        except Exception as e:
            logger.exception("Erro inesperado removendo dos filhos: %s", e)

class DoctypeProcessor:
    """
    Processa os doctypes e constrói entidades
    """
    
    def __init__(self, entity_factory: EntityFactory,
                 mapping_manager: MappingManager,
                 doctypes_data: Dict[str, Any]):
            self.entity_factory = entity_factory
            self.mapping_manager = mapping_manager
            self.doctypes_data = doctypes_data
            self.processed_doctypes: Set[str] = set()
    
    def process_doctype(self,
                        doctype_name: str,
                        fieldname_data: str = "") -> Optional[Entity]:
        """
        Processa um único doctype e retorna sua entidade
        Parâmetros:
            doctype_name (str): O nome do doctype a ser processado
            fieldname_data (str): O nome do campo de dados associado (opcional)
        Retorno:
            Optional[Entity]: A entidade do doctype processado, ou None se o doctype não existir
        """
        try:
            if doctype_name in self.processed_doctypes:
                return None

            if "all_doctypes" in self.doctypes_data:
                all_ = self.doctypes_data.get("all_doctypes", {})
            else:
                all_ = self.doctypes_data

            if doctype_name not in all_:
                return None

            self.processed_doctypes.add(doctype_name)
            entity = self.entity_factory.create_doctype_entity(doctype_name, fieldname_data)

            if entity:
                self._add_regular_fields(entity, doctype_name)
                self._add_mandatory_children(entity, doctype_name)
                self._add_optional_relationships(entity, doctype_name)

            return entity
        except Exception as e:
            logger.exception("Erro inesperado processando doctype: %s", e)
            return None
    
    def _add_regular_fields(self, entity: Entity, doctype_name: str) -> None:
        """
        Adiciona campos regulares (não-relacionamento) à entidade
        Parâmetros:
            entity (Entity): A entidade à qual os campos serão adicionados
            doctype_name (str): O nome do doctype cujos campos serão adicionados
        """
        try:
            if "all_doctypes" in self.doctypes_data:
                all_ = self.doctypes_data.get("all_doctypes", {})
            else:
                all_ = self.doctypes_data

            fields = all_.get(doctype_name, [])

            for f in fields:
                if f.get("fieldtype") == "Table":
                    continue

                field_entity = self.entity_factory.create_field_entity(f)
                if field_entity:
                    entity.add_child(field_entity)
        except Exception as e:
            logger.exception("Erro inesperado adicionando campos regulares: %s", e)
    
    def _add_mandatory_children(self, entity: Entity, doctype_name: str) -> None:
        """
        Adiciona filhos obrigatórios à entidade
        Parâmetros:
            entity (Entity): A entidade à qual os filhos obrigatórios serão adicionados
            doctype_name (str): O nome do doctype cujos filhos obrigatórios serão adicionados
        """
        try:
            mandatory_children = self.mapping_manager.get_mandatory_children(doctype_name)

            for child_name in mandatory_children:
                if entity.has_child_with_key(self.entity_factory.normalizer.create_key(child_name)):
                    continue

                child_entity = self.process_doctype(child_name)
                if child_entity:
                    entity.add_child(child_entity)
        except Exception as e:
            logger.exception("Erro inesperado adicionando filhos obrigatórios: %s", e)
    
    def _add_optional_relationships(self, entity: Entity, doctype_name: str) -> None:
        """
        Adiciona relacionamentos opcionais com base nas opções de campo
        Parâmetros:
            entity (Entity): A entidade à qual os relacionamentos opcionais serão adicionados
            doctype_name (str): O nome do doctype cujos relacionamentos opcionais serão adicionados
        """
        try:
            if "all_doctypes" in self.doctypes_data:
                all_ = self.doctypes_data.get("all_doctypes", {})
            else:
                all_ = self.doctypes_data

            fields = all_.get(doctype_name, [])

            for f in fields:
                if f.get("fieldtype") != "Table" or not f.get("options"):
                    continue

                related_doctype = f["options"]

                if not self.mapping_manager.is_valid_optional_child(doctype_name, related_doctype):
                    continue

                related_key = self.entity_factory.normalizer.create_key(related_doctype)
                if entity.has_child_with_key(related_key):
                    continue

                child_entity = self.process_doctype(related_doctype, f.get("fieldname", ""))
                if child_entity:
                    entity.add_child(child_entity)
        except Exception as e:
            logger.exception("Erro inesperado adicionando relacionamentos opcionais: %s", e)

class MappingEnforcer:
    """
    Força a aplicação de mapeamentos especificados na estrutura da árvore
    """
    
    def __init__(self, mapping_manager: MappingManager,
                 navigator: EntityTreeNavigator,
                 normalizer: StringNormalizer):
        self.mapping_manager = mapping_manager
        self.navigator = navigator
        self.normalizer = normalizer
    
    def enforce_mappings(self, entities: List[Entity]) -> None:
        """
        Garante a aplicação de todos os mapeamentos especificados na árvore
        Parâmetros:
            entities (List[Entity]): A lista de entidades raiz onde os mapeamentos serão aplicados
        """
        try:
            self._remove_misplaced_children(entities)
            self._add_children_to_correct_parents(entities)

            for entity in entities:
                self._enforce_mappings_recursive(entity)
        except Exception as e:
            logger.exception("Erro inesperado aplicando mapeamentos: %s", e)
    
    def _remove_misplaced_children(self, entities: List[Entity]) -> None:
        """
        Remove filhos que estão sob pais errados
        Parâmetros:
            entities (List[Entity]): A lista de entidades raiz onde os filhos serão verificados e removidos se necessário
        """
        try:
            for mapping in self.mapping_manager.specified_mappings:
                child_key = self.normalizer.create_key(mapping["child"])
                parent_key = self.normalizer.create_key(mapping["parent"])

                for entity in entities:
                    if entity.key != parent_key:
                        entity.remove_child_by_key(child_key)
                        self.navigator._remove_from_children(entity, child_key)
        except Exception as e:
            logger.exception("Erro inesperado removendo filhos deslocados: %s", e)
    
    def _add_children_to_correct_parents(self, entities: List[Entity]) -> None:
        """
        Adiciona filhos aos seus pais corretos de acordo com os mapeamentos
        Parâmetros:
            entities (List[Entity]): A lista de entidades raiz onde os filhos serão adicionados aos pais corretos
        """
        try:
            for mapping in self.mapping_manager.specified_mappings:
                child_key = self.normalizer.create_key(mapping["child"])
                parent_key = self.normalizer.create_key(mapping["parent"])
                parent = self.navigator.find_entity_by_key(entities, parent_key)
                child = self.navigator.find_entity_by_key(entities, child_key)
                if parent and child and not parent.has_child_with_key(child_key):
                    parent.add_child(child)
        except Exception as e:
            logger.exception("Erro inesperado adicionando filhos aos pais corretos: %s", e)
    
    def _enforce_mappings_recursive(self, entity: Entity) -> None:
        """
        Recursivamente aplica mapeamentos em todos os níveis
        Parâmetros:
            entity (Entity): A entidade cuja hierarquia será verificada e ajustada conforme os mapeamentos
        """
        try:
            for child in entity.children[:]:
                grandchildren_to_move = []

                for grandchild in child.children[:]:
                    proper_parent_name = self.mapping_manager.get_proper_parent(grandchild.fieldname)

                    if proper_parent_name and child.fieldname != proper_parent_name:
                        for sibling in entity.children:
                            if sibling.fieldname == proper_parent_name:
                                grandchildren_to_move.append((grandchild, sibling))
                                break

                for grandchild, proper_parent in grandchildren_to_move:
                    if not proper_parent.has_child_with_key(grandchild.key):
                        proper_parent.add_child(grandchild)
                    child.remove_child_by_key(grandchild.key)

            for child in entity.children:
                self._enforce_mappings_recursive(child)
        except Exception as e:
            logger.exception("Erro inesperado aplicando mapeamentos recursivamente: %s", e)

class HierarchicalTreeBuilder:
    """
    Classe principal para construção de estruturas de árvore hierárquica
    """
    
    def __init__(self, translations, mappings):
        self.normalizer = StringNormalizer()
        self.type_mapper = FieldTypeMapper()
        self.path_manager = PathManager(self.normalizer)
        self.navigator = EntityTreeNavigator()
        self.translations = translations
        self.mappings = mappings
        
    def build_tree(self, all_doctypes: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Constrói a estrutura da árvore hierárquica a partir dos doctypes fornecidos
        * Converte doctypes e campos em entidades hierárquicas
        * Aplica mapeamentos obrigatórios e opcionais
        * Normaliza nomes/paths e mapeia tipos de campo
        * Atualiza todos os paths na estrutura
        * Retorna a estrutura pronta para consumo
        * Remove filhos do nível raiz que devem ser apenas filhos
        * Cada dicionário contém chave, descrição, fieldname, tipo, path, dragandrop, ícone e filhos
        """
        try:
            specified_mappings = self.mappings.get_specific_mapping()
            translations = self.translations.get_translations()

            mapping_manager = MappingManager(specified_mappings)
            entity_factory = EntityFactory(self.normalizer, self.type_mapper, translations)
            doctype_processor = DoctypeProcessor(entity_factory, mapping_manager, all_doctypes)
            mapping_enforcer = MappingEnforcer(mapping_manager, self.navigator, self.normalizer)

            entities = self._build_initial_tree(all_doctypes, mapping_manager, doctype_processor)
            mapping_enforcer.enforce_mappings(entities)
            entities = self._remove_children_from_root(entities, mapping_manager)
            self.path_manager.update_all_paths(entities)

            return [entity.to_dict() for entity in entities if entity]
        except Exception as e:
            logger.exception("Erro inesperado construindo árvore hierárquica: %s", e)
            return []
    
    def _build_initial_tree(self, all_doctypes: Dict[str, Any],
                           mapping_manager: MappingManager,
                           doctype_processor: DoctypeProcessor) -> List[Entity]:
        """
        Constrói a estrutura da árvore inicial
        Parâmetros:
            all_doctypes (Dict[str, Any]): Dicionário contendo todos os doctypes e seus campos
            mapping_manager (MappingManager): O gerenciador de mapeamentos
            doctype_processor (DoctypeProcessor): O processador de doctypes
        Retorno:
            List[Entity]: A lista de entidades raiz construídas
        """
        try:
            entities = []

            if "all_doctypes" in all_doctypes:
                all_ = all_doctypes.get("all_doctypes", {})
            else:
                all_ = all_doctypes

            for doctype_name in all_.keys():
                if not mapping_manager.has_mandatory_parent(doctype_name):
                    entity = doctype_processor.process_doctype(doctype_name)
                    if entity:
                        entities.append(entity)

            for doctype_name in all_.keys():
                if doctype_name not in doctype_processor.processed_doctypes:
                    entity = doctype_processor.process_doctype(doctype_name)
                    if entity:
                        entities.append(entity)

            return entities
        except Exception as e:
            logger.exception("Erro inesperado construindo árvore inicial: %s", e)
            return []
    
    def _remove_children_from_root(self, entities: List[Entity],
                                  mapping_manager: MappingManager) -> List[Entity]:
        """
        Remove entidades do nível raiz que devem ser apenas filhos
        Parâmetros:
            entities (List[Entity]): A lista de entidades raiz
            mapping_manager (MappingManager): O gerenciador de mapeamentos
        Retorno:
            List[Entity]: A lista de entidades raiz após a remoção dos filhos deslocados
        """
        try:
            children_to_remove = mapping_manager.get_children_to_remove_from_root()
            return [entity for entity in entities if entity.key not in children_to_remove]
        except Exception as e:
            logger.exception("Erro inesperado removendo filhos da raiz: %s", e)
            return entities

