"""
Configurações globais do motor de cálculo.

Propósito:
    Define e expõe as configurações padrão e atualizáveis usadas pelo motor de cálculo para validação
    e execução segura de expressões, centralizando políticas de permissão e bloqueio.

Responsabilidades principais:
    - Centralizar listas de funções seguras e nós AST bloqueados.
    - Expor API simples para leitura (get_config) e atualização (update_config).
    - Fornecer valores padrão validados pelo Pydantic.
    - Permitir controle centralizado das políticas de execução.

Posição na arquitetura:
    Módulo de infraestrutura / núcleo consumido por componentes de parsing, validação e execução
    de expressões no motor.

Dependências críticas:
    - pydantic (validação e modelagem)
    - typing (anotações de tipos)
    - Consumidores: parser, executor, e camadas que aplicam políticas de segurança.

Considerações de segurança:
    - Não executar código arbitrário; usar listas brancas de funções e bloquear nós AST perigosos.

Exemplo de uso básico:

    cfg = get_config()
    logger.info(f"Funções de agregação configuradas: {cfg.safe_aggr_functions}")

    # Atualiza (substitui) a lista de funções customizadas permitidas
    update_config({"safe_custom_functions": {"contains", "starts_with"}})
"""

import logging
from typing import Dict, Any, Set, Callable, ClassVar
from pydantic import BaseModel, ValidationError
import numpy as np

logger = logging.getLogger(__name__)

class EngineConfig(BaseModel):
    """
    Configurações do motor de cálculo.
    Define listas de funções seguras e nós AST bloqueados para validação e execução segura.
    """

    safe_aggr_functions: Set[str] = {
        "sum", "avg", "count", "max", "min", "abs", "len", 
        "first", "last","firstc", "lastc",
        "sum_node", "avg_node", "count_node", "max_node", "min_node" 
    }

    # Allowed safe functions
    safe_custom_functions: Set[str] = {
        "contains"
    }    

    # Inicia com um conjunto mínimo de builtins seguros
    numpy_functions: ClassVar[Dict[str, Callable]] = {
        # Funções matemáticas básicas
        'sum': np.sum,            # Soma de elementos
        'mean': np.mean,          # Média aritmética
        'average': np.average,    # Média ponderada
        'median': np.median,      # Mediana
        'std': np.std,            # Desvio padrão
        'var': np.var,            # Variância
        'min': np.min,            # Valor mínimo
        'max': np.max,            # Valor máximo
        'argmin': np.argmin,      # Índice do valor mínimo
        'argmax': np.argmax,      # Índice do valor máximo
        
        # Operações estatísticas
        'percentile': np.percentile,  # Percentil
        'quantile': np.quantile,      # Quantil
        'cov': np.cov,                # Covariância
        'corrcoef': np.corrcoef,      # Coeficiente de correlação
        
        # Operações de agregação
        'prod': np.prod,          # Produto dos elementos
        'cumsum': np.cumsum,      # Soma acumulativa
        'cumprod': np.cumprod,    # Produto acumulativo
        
        # Funções trigonométricas
        'sin': np.sin,            # Seno
        'cos': np.cos,            # Cosseno
        'tan': np.tan,            # Tangente
        'arcsin': np.arcsin,      # Arco seno
        'arccos': np.arccos,      # Arco cosseno
        'arctan': np.arctan,      # Arco tangente
        
        # Funções exponenciais e logarítmicas
        'exp': np.exp,            # Exponencial
        'log': np.log,            # Logaritmo natural
        'log10': np.log10,        # Logaritmo base 10
        'log2': np.log2,          # Logaritmo base 2
        'sqrt': np.sqrt,          # Raiz quadrada
        
        # Funções de arredondamento
        'round': np.round,        # Arredondamento
        'floor': np.floor,        # Arredondamento para baixo
        'ceil': np.ceil,          # Arredondamento para cima
        'trunc': np.trunc,        # Truncamento
        
        # Funções lógicas
        'all': np.all,            # Verifica se todos são verdadeiros
        'any': np.any,            # Verifica se algum é verdadeiro
        
        # Manipulação de arrays
        'concatenate': np.concatenate,  # Concatenar arrays
        'stack': np.stack,              # Empilhar arrays
        'vstack': np.vstack,            # Empilhar verticalmente
        'hstack': np.hstack,            # Empilhar horizontalmente
        'reshape': np.reshape,          # Remodelar arrays
        'transpose': np.transpose,      # Transpor arrays
        
        # Operações condicionais
        'where': np.where,        # Operador condicional
        'select': np.select,      # Seleção condicional
        
        # Outras funções úteis
        'unique': np.unique,      # Valores únicos
        'diff': np.diff,          # Diferenças entre elementos adjacentes
        'gradient': np.gradient,  # Gradiente
        'clip': np.clip,          # Recortar valores
        'absolute': np.absolute,  # Valor absoluto (alias: np.abs)
        'abs': np.abs,            # Valor absoluto

        'flt': np.round           # Arredondamento para ponto flutuante
    }

    # Funções que permaneceriam inalteradas:
    default_functions: ClassVar[Dict[str, Any]] = {
        'bin': bin,          # Representação binária
        'bool': bool,        # Conversão para booleano
        'bytearray': bytearray,  # Criar bytearray
        'bytes': bytes,      # Criar bytes
        'chr': chr,          # Converter inteiro para caractere Unicode
        'complex': complex,  # Criar número complexo
        'dict': dict,        # Criar dicionário
        'divmod': divmod,    # Divisão e módulo
        'enumerate': enumerate,  # Enumerar sequência
        'filter': filter,    # Filtrar sequência
        'float': float,      # Conversão para ponto flutuante
        'format': format,    # Formatação de string
        'frozenset': frozenset,  # Criar frozenset
        'hash': hash,        # Calcular hash
        'hex': hex,          # Representação hexadecimal
        'id': id,            # Identificador único
        'int': int,          # Conversão para inteiro
        'isinstance': isinstance,  # Verificar tipo
        'issubclass': issubclass,  # Verificar herança
        'len': len,          # Tamanho da sequência
        'list': list,        # Criar lista
        'map': map,          # Mapear função
        'oct': oct,          # Representação octal
        'ord': ord,          # Converter caractere para inteiro
        'pow': pow,          # Potenciação (embora np.power seja uma alternativa)
        'range': range,      # Gerar sequência
        'reversed': reversed,  # Inverter sequência
        'set': set,          # Criar conjunto
        'slice': slice,      # Criar objeto slice
        'sorted': sorted,    # Ordenar
        'str': str,          # Conversão para string
        'tuple': tuple,      # Criar tupla
        'type': type,        # Obter tipo
        'zip': zip,          # Combinar sequências
        'True': True,        # Constante booleana
        'False': False,      # Constante booleana
        'None': None,        # Constante nula
    }
    
    # Funções AST bloqueadas
    blocked_ast: Set[str] = {
        'Import', 'ImportFrom', 'Exec', 'Eval', 
        'Attribute', 'Call', 'ClassDef', 'FunctionDef',
        'Delete', 'Assert', 'Raise', 'Try', 'TryExcept',
        'TryFinally', 'With', 'AsyncFunctionDef', 'AsyncWith',
        'Global', 'Nonlocal'
    }

# Configuração global padrão
try:
    default_config = EngineConfig()
    logger.info("Configuração padrão inicializada com sucesso")
except Exception as e:
    logger.exception("Erro crítico ao inicializar configuração padrão: %s", e)
    default_config = EngineConfig()

def get_config() -> EngineConfig:
    """
    Retorna a configuração global.
    """
    try:
        return default_config
    except Exception as e:
        logger.exception("Erro inesperado ao obter configuração: %s", e)
        return EngineConfig()

def update_config(config_updates: Dict[str, Any]) -> None:
    """
    Atualiza a configuração global com os valores fornecidos de forma segura.

    Parâmetros:
        config_updates (Dict[str, Any]): Dicionário com as atualizações de configuração
    """
    try:
        if not isinstance(config_updates, dict):
            logger.error("Parâmetro config_updates deve ser um dicionário")
            return

        if not config_updates:
            logger.warning("Dicionário de atualizações está vazio")
            return

        # Validação de entrada mais rigorosa para correção da vulnerabilidade crítica
        for key, value in config_updates.items():
            if not isinstance(key, str):
                logger.error("Chave de configuração deve ser string: %s", key)
                return

            if len(key) > 100:
                logger.error("Nome de chave muito longo: %s", key[:50])
                return

        # Validar que todas as chaves existem no modelo
        valid_fields = set(EngineConfig.model_fields.keys())
        invalid_keys = set(config_updates.keys()) - valid_fields

        if invalid_keys:
            logger.error("Chaves inválidas na configuração: %s", invalid_keys)
            return

        # Criar uma nova instância para validar os updates
        current_data = default_config.dict()
        current_data.update(config_updates)

        try:
            EngineConfig(**current_data)

            # Se a validação passou, aplicar as mudanças
            for key, value in config_updates.items():
                if hasattr(default_config, key):
                    setattr(default_config, key, value)
                    logger.info("Configuração atualizada: %s = %s", key, value)

        except ValidationError as e:
            logger.error("Erro de validação na configuração: %s", e)
            return

    except Exception as e:
        logger.exception("Erro inesperado ao atualizar configuração: %s", e)
        return