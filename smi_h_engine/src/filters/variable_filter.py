"""
Extrator de Variáveis de Filtro (FilterVariableExtractor)
Propósito:
    Fornecer utilitários para identificar e localizar variáveis no formato e00000v
    que aparecem à direita de operadores de comparação em expressões textuais.
    Facilita a análise e transformação de filtros antes de validação ou execução.
Responsabilidades principais:
    - Detectar ocorrências de variáveis do padrão [eE]\\d{5}[vV] quando aparecem após operadores de comparação.
    - Retornar informações detalhadas de cada ocorrência (texto da variável, posição inicial e final).
    - Fornecer listas de nomes únicos de variáveis e mapas de variáveis por expressão.
    - Produzir versões "destacadas" das expressões com marcadores envolvendo as variáveis encontradas.
Posição na arquitetura:
    Componente de análise/normalização de entrada, tipicamente usado na camada de pré-processamento
    de filtros ou expressões antes da validação, tradução para consultas ou execução. Pode ser integrado
    a pipelines de parsing, validação de regras de negócio ou ferramentas de refatoração de filtros.
Dependências críticas:
    - Bibliotecas padrão do Python: re (expressões regulares), typing (anotações).
    - Não requer bibliotecas externas; assume entrada como strings válidas.
Considerações de segurança:
    - Entrada muito longa ou especialmente construída pode causar sobrecarga na avaliação via regex (ReDoS);
      em cenários expostos a usuários não confiáveis, aplicar limites de tamanho ou tempo de execução.
    - O padrão atual é sensível ao formato esperado; alterações no formato de variáveis devem ser tratadas cuidadosamente.
Exemplo de uso básico:
    from variable_filter import FilterVariableExtractor
    extractor = FilterVariableExtractor()
    expr = "field1 == e00001v and field2 != E12345V or amount >= e00002v"
    # Extrai ocorrências com posições
    occurrences = extractor.extract_variables(expr)
    # Ex.: [{'variable': 'e00001v', 'start_pos': 11, 'end_pos': 18}, ...]
    unique = extractor.extract_unique_variables(expr)
    # Ex.: ['e00001v', 'E12345V', 'e00002v']
    highlighted = extractor.highlight_variables(expr, prefix='__', suffix='__')
    # Ex.: "field1 == __e00001v__ and field2 != __E12345V__ or amount >= __e00002v__"
"""

import logging
import re
from typing import List, Dict, Tuple, Any

logger = logging.getLogger(__name__)

class FilterVariableExtractor:
    """
    Classe para extrair variáveis no formato e00000v que aparecem 
    à direita de operadores de comparação em expressões.
    """
    
    def __init__(self, variable_pattern: str = r'[eE]\d{5}[vV]'):
        """
        Inicializa o FilterVariableExtractor com um padrão específico de variável.

        Parâmetros:
            variable_pattern: Padrão de expressão regular para variáveis a extrair.
                              O padrão padrão é 'e' seguido por 5 dígitos seguido por 'v' (insensível a maiúsculas/minúsculas).
        """
        try:
            self.variable_pattern = variable_pattern
            # Padrão para combinar operadores de comparação seguidos pelo padrão da variável
            self.comparison_pattern = r'(?:[=!<>]=?|<|>)\s*(' + variable_pattern + r')'
        except Exception as e:
            logger.exception("Erro inesperado na inicialização do FilterVariableExtractor: %s", e)
            raise

    def extract_variables(self, expression: str) -> List[Dict[str, Any]]:
        """
        Extrai variáveis à direita de operadores de comparação de uma expressão.

        Parâmetros:
            expression: A expressão em formato string para análise.

        Retorno:
            Uma lista de dicionários contendo informações da variável:
            - variable: O texto da variável encontrada
            - start_pos: Posição inicial na expressão
            - end_pos: Posição final na expressão
        """
        try:
            results = []

            for match in re.finditer(self.comparison_pattern, expression):

                # O grupo 1 contém a variável capturada
                variable = match.group(1)

                # Obtém as posições inicial e final da variável (não do operador)
                start_pos = match.start(1)
                end_pos = match.end(1)

                results.append({
                    'variable': variable,
                    'start_pos': start_pos,
                    'end_pos': end_pos,
                })

            return results
        except Exception as e:
            logger.exception("Erro inesperado ao extrair variáveis: %s", e)
            return []
    
    def extract_unique_variables(self, expression: str) -> List[str]:
        """
        Extrai nomes de variáveis únicos à direita dos operadores de comparação.

        Parâmetros:
            expression: A expressão em formato string para análise.

        Retorno:
            Uma lista de nomes de variáveis únicos.
        """
        try:
            matches = self.extract_variables(expression)
            unique_vars = list(set(match['variable'] for match in matches))
            return unique_vars
        except Exception as e:
            logger.exception("Erro inesperado ao extrair variáveis únicas: %s", e)
            return []
    
    def process_multiple_expressions(self, expressions: List[str]) -> Dict[int, List[Dict[str, Any]]]:
        """
        Processa múltiplas expressões e extrai variáveis de cada uma.

        Parâmetros:
            expressions: Uma lista de expressões em formato string para análise.

        Retorno:
            Um dicionário mapeando os índices das expressões para listas de informações das variáveis.
        """
        try:
            results = {}

            for i, expression in enumerate(expressions):
                results[i] = self.extract_variables(expression)

            return results
        except Exception as e:
            logger.exception("Erro inesperado ao processar múltiplas expressões: %s", e)
            return {}
    
    def find_variable_positions(self, text: str, variable: str) -> List[Tuple[int, int]]:
        """
        Encontra todas as posições de uma variável específica no texto.

        Parâmetros:
            text: O texto em que realizar a busca.
            variable: A variável que se deseja buscar.

        Retorno:
            Uma lista de tuplas contendo (posição_inicial, posição_final).
        """
        try:
            positions = []
            pattern = r'(?:[=!<>]=?|<|>)\s*(' + re.escape(variable) + r')'

            for match in re.finditer(pattern, text):
                positions.append((match.start(1), match.end(1)))

            return positions
        except Exception as e:
            logger.exception("Erro inesperado ao buscar posições da variável: %s", e)
            return []

    def highlight_variables(self, expression: str,
                            prefix: str = '__', suffix: str = '__') -> str:
        """
        Cria uma versão destacada da expressão com as variáveis encontradas marcadas.

        Parâmetros:
            expression: A expressão a ser destacada.
            prefix: A string a ser inserida antes de cada variável.
            suffix: A string a ser inserida depois de cada variável.

        Retorno:
            Uma string com as variáveis destacadas.
        """
        try:
            # Extrai variáveis com suas posições
            variables = self.extract_variables(expression)

            # Ordena por posição inicial em ordem decrescente para evitar deslocar as posições
            variables.sort(key=lambda x: x['start_pos'], reverse=True)

            # Cria uma lista mutável de caracteres
            chars = list(expression)

            # Insere os marcadores
            for var_info in variables:
                chars.insert(var_info['end_pos'], suffix)
                chars.insert(var_info['start_pos'], prefix)

            # Junta os caracteres de volta em uma string
            return ''.join(chars)
        except Exception as e:
            logger.exception("Erro inesperado ao destacar variáveis: %s", e)
            return expression
