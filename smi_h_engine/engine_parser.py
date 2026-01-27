"""
Parser de Fórmulas e Extrator de Agregações
Propósito:
    Analisa expressões matemáticas com funções de agregação, extraindo chamadas de agregação,
    variáveis (formato eNNNNNv) e filtros para suportar a construção de dependências e execução.
    Fornece utilitários para percorrer estruturas hierárquicas e coletar/ordenar fórmulas.
    Responsabilidades principais
Responsabilidades principais:
    - Identificar e extrair chamadas de funções de agregação e seus argumentos/filters.
    - Detectar e listar variáveis usadas nas agregações e na expressão global.
    - Tratar de estruturas aninhadas (parênteses balanceados) e separar argumentos/top-level commas.
    - Percorrer estruturas de dados hierárquicas para coletar, deduplicar e preparar fórmulas para ordenação/executação.
Posição na arquitetura:
    Componente de pré-processamento/compilação de fórmulas: fica entre a camada de ingestão (onde as fórmulas são definidas/armazenadas)
    e a camada de execução/avaliação. Gera metadados (lista de agregações, variáveis e caminhos DAG) usados pelo motor de cálculo.
Dependências críticas:
    - config.get_config: fornece listas permitidas de funções de agregação e funções custom (safe_aggr_functions, safe_custom_functions).
    - re (regex): usado intensivamente para identificar variáveis, funções e para parsing.
    - Estruturas de dados de entrada: espera dicts/lists com campos "path", "formulas" e "data" para extração recursiva.
Considerações de segurança:
    - Não executar (eval/exec) strings de fórmula; o módulo apenas analisa texto e extrai metadados.
    - Validar e manter listas "safe_aggr_functions" e "safe_custom_functions" no config para evitar reconhecimento/execução de funções não autorizadas.
    - Filtragem de operadores corrige '=' para '==', mas entrada do usuário deve ser validada para evitar manipulações inesperadas.
Exemplo de uso básico:
    from engine_parser import FormulaParser
    parser = FormulaParser()
    formula = "sum(e00001v, e00002v > 0) + avg_node(e00003v)"
    result = parser.parse_formula(formula)
    # result terá chaves: "aggr" (lista de agregações), "vars" (variáveis não agregadas)
    print(result["aggr"])
    [
        {
            "base": "sum(e00001v, e00002v > 0)",
            "eval": "sum(e00001v)",
            "vars": ["e00001v"],
            "global": True,
            "filter": "e00002v == 0 or e00002v > 0",  # exemplo de saída após correção (dependendo do input)
            "filter_vars": ["e00002v"]
        },
        ...
    ]
Notas:
    - O comportamento exato depende das listas carregadas via config (quais funções são reconhecidas como agregação e custom).
    - Para avaliação segura das expressões resultantes, integrar com um executor controlado que só permita operações/pipelines previstas.
"""

import re
import logging
from config.config import get_config
from typing import Dict, List, Any, Optional, Tuple

class FormulaParser:
    """
    Classe para análise de fórmulas e extração de suas funções de agregação.

    Esta classe implementa um parser eficiente usando expressões regulares e análise de tokens
    para identificar funções de agregação, extrair variáveis e lidar com estruturas aninhadas
    em fórmulas matemáticas.

    O parser suporta:
    - Detecção de funções de agregação a partir de uma lista configurável
    - Extração de variáveis de fórmulas
    - Análise de expressões de filtro dentro de funções de agregação
    - Análise de parênteses balanceados para expressões aninhadas
    """
    
    def __init__(self, debug: bool = False):
        """
        Inicializa o parser com funções de agregação permitidas a partir da configuração.

        Carrega a lista de funções de agregação permitidas a partir da configuração da aplicação
        e compila padrões de expressões regulares para uma análise eficiente de fórmulas.
        """
        try:
            self.debug = debug
            self.logger = logging.getLogger(__name__)

            # Carrega as funções permitidas
            config_obj = get_config()
            self.safe_aggr_functions = config_obj.safe_aggr_functions
            # self.safe_aggr_functions.update(config_obj.numpy_functions)
            # self.safe_aggr_functions.update(config_obj.default_functions)
            self.safe_custom_functions = config_obj.safe_custom_functions

            # Regex para identificar variáveis no formato e12345v
            self.var_pattern = re.compile(r'e\d{5}v')

            # Cria padrões regex eficientes para identificar funções de agregação
            self._compile_patterns()
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.exception("Erro inesperado na inicialização do parser: %s", e)
            raise
    
    def _compile_patterns(self) -> None:
        """
        Compila padrões regex para identificar funções de agregação e seus argumentos.

        Cria padrões de expressão regular para:
        1. Detectar funções de agregação com seus argumentos e filtros
        2. Identificar funções personalizadas usadas em expressões de filtro

        Esses padrões são usados ao longo do processo de análise para uma análise eficiente das fórmulas.
        """
        try:
            # Regex para criar padrão para funções de agregação
            aggr_funcs = '|'.join(self.safe_aggr_functions)
            pattern = rf'({aggr_funcs})\s*\((.*?)(?:,\s*(.*?))?\)'
            self.aggr_pattern = re.compile(pattern, re.DOTALL)

            # Regex para encontrar funções personalizadas em filtros
            custom_funcs = '|'.join(self.safe_custom_functions)
            custom_pattern = rf'({custom_funcs})\s*\((.*?)\)'
            self.custom_func_pattern = re.compile(custom_pattern, re.DOTALL)
        except Exception as e:
            self.logger.exception("Erro inesperado na compilação dos padrões regex: %s", e)
            raise
    
    def extract_variables(self, expression: str) -> List[str]:
        """
        Extrai variáveis (por exemplo, e00001v) de uma expressão.

        Identifica todas as variáveis na expressão que correspondem ao padrão 'e' seguido exatamente
        por 5 dígitos e depois 'v', e retorna uma lista de variáveis únicas encontradas.

        Parâmetros:
            expression: A expressão a ser analisada

        Retorno:
            Lista de variáveis únicas encontradas, preservando sua ordem original
        """
        try:
            # Se a expressão estiver vazia, retorna lista vazia
            if not expression:
                return []

            # Localiza todas as variáveis na expressão
            variables = self.var_pattern.findall(expression)

            # Remove duplicatas preservando a ordem
            unique_vars = []
            for var in variables:
                if var not in unique_vars:
                    unique_vars.append(var)

            return unique_vars
        except Exception as e:
            self.logger.exception("Erro inesperado na extração de variáveis: %s", e)
            return []
    
    def _fix_comparison_operators(self, str_expr) -> str:
        """
        Substitui '=' por '==' em expressões para garantir comparações corretas.

        Garante que apenas comparações sejam ajustadas, evitando múltiplos '==' em sequência.
        Isso é necessário porque os usuários às vezes usam um único sinal de igual para comparações
        em vez do duplo igual exigido.

        Parâmetros:
            str_expr: A expressão a ser corrigida

        Retorno:
            A expressão com os operadores de comparação corrigidos
        """
        try:
            # Se a expressão estiver vazia, retorna como está
            if not str_expr:
                return str_expr

            # Substitui '=' por '==' apenas quando não faz parte de '==' ou '===' e evita duplicação
            result = re.sub(r'(?<![=!<>])=(?![=])', '==', str_expr).replace('== ==', '==')

            return result
        except Exception as e:
            self.logger.exception("Erro inesperado na correção dos operadores de comparação: %s", e)
            return str_expr

    def _parse_aggregate_call(self, match) -> Dict:
        """
        Analisa uma chamada de função de agregação e extrai seus componentes.

        Analisa uma correspondência de regex de uma função de agregação, extraindo:
        - Nome da função
        - Expressão do argumento principal
        - Expressão de filtro (se presente)
        - Variáveis no argumento e no filtro

        Parâmetros:
            match: Objeto de correspondência de regex contendo os grupos capturados

        Retorno:
            Dicionário com informações sobre a função de agregação
        """
        try:
            # Extrai os grupos capturados
            func_name = match.group(1)
            arg_expr = match.group(2).strip() if match.group(2) else ""
            filter_expr = match.group(3).strip() if match.group(3) else ""
            filter_expr = self._fix_comparison_operators(filter_expr)

            # Extrai variáveis do argumento principal
            arg_vars = self.extract_variables(arg_expr)

            # Extrai variáveis do filtro
            filter_vars = self.extract_variables(filter_expr)

            # Constrói a função completa como uma string
            full_func = f"{func_name}({arg_expr}"
            if filter_expr:
                full_func += f", {filter_expr}"
            full_func += ")"

            return {
                "formula": full_func,
                "vars": arg_vars,
                "filter": filter_expr,
                "filter_vars": filter_vars
            }
        except Exception as e:
            self.logger.exception("Erro inesperado na análise da chamada de agregação: %s", e)
            return {
                "formula": "",
                "vars": [],
                "filter": "",
                "filter_vars": []
            }
    
    def balance_parentheses(self, expression: str, start_idx: int) -> Tuple[int, str]:
        """
        Localiza o índice da correspondente parêntese de fechamento e extrai a subexpressão.

        Usa uma abordagem baseada em pilha para corresponder parênteses de abertura e fechamento, garantindo
        que parênteses aninhados sejam tratados corretamente.

        Parâmetros:
            expression: A expressão completa
            start_idx: Índice do parêntese de abertura

        Retorno:
            Tupla com o índice do parêntese de fechamento e a subexpressão extraída
        """
        try:
            # Se o índice inicial for inválido ou não for um '(', retorna -1 e string vazia
            if start_idx >= len(expression) or expression[start_idx] != '(':
                if self.debug:
                    self.logger.debug(f"Indice de inicio inválido {start_idx} para balanceamento de parênteses")
                return -1, ""

            # Usa uma pilha para rastrear parênteses
            stack = []
            for i in range(start_idx, len(expression)):
                if expression[i] == '(':
                    stack.append('(')
                elif expression[i] == ')':
                    if stack:
                        # Remove o último parêntese aberto da pilha
                        stack.pop()
                        if not stack:  # Parênteses balanceados
                            subexpr = expression[start_idx+1:i]
                            return i, subexpr

            return -1, ""  # Paraênteses não balanceados
        except Exception as e:
            self.logger.exception("Erro inesperado no balanceamento de parênteses: %s", e)
            return -1, ""
    
    def find_top_level_commas(self, expr: str) -> List[int]:
        """
        Encontra posições de vírgulas no nível superior (não dentro de parênteses).
        Identifica vírgulas que não estão dentro de parênteses, retornando suas posições.
        Isso é essencial para separar os argumentos principais das expressões de filtro em
        funções de agregação.

        Parâmetros:
            expr: A expressão a ser analisada

        Retorno:
            Lista de índices das vírgulas de nível superior
        """
        try:
            comma_positions = []
            paren_level = 0

            for i, char in enumerate(expr):
                # Segue o nível de parênteses
                if char == '(':
                    paren_level += 1
                elif char == ')':
                    paren_level -= 1
                elif char == ',' and paren_level == 0:
                    comma_positions.append(i)

            return comma_positions
        except Exception as e:
            self.logger.exception("Erro inesperado na busca por vírgulas de nível superior: %s", e)
            return []
    
    def parse_aggregate_functions(self, formula: str) -> List[Dict]:
        """
        Extrai funções de agregação e suas variáveis associadas de uma fórmula.

        Implementa uma abordagem baseada em tokens e análise de parênteses
        para lidar corretamente com filtros e funções aninhadas.

        Parâmetros:
            formula: A fórmula a ser analisada

        Retorno:
            Lista de dicionários com informações sobre as funções de agregação encontradas
        """
        try:
            if not formula:
                if self.debug:
                    self.logger.debug("Fómula vazia fornecida, retornando lista vazia")
                return []

            # Armazena as funções de agregação encontradas
            aggregations = []

            # Posição atual na fórmula
            pos = 0
            formula_len = len(formula)

            while pos < formula_len:
                # Busca por nomes de funções de agregação
                found_func = None
                for func_name in self.safe_aggr_functions:
                    if formula[pos:].startswith(func_name) and pos + len(func_name) < formula_len:
                        # Verifica se é seguido por um parêntese de abertura
                        next_pos = pos + len(func_name)

                        # Ignora espaços em branco
                        while next_pos < formula_len and formula[next_pos].isspace():
                            next_pos += 1

                        if next_pos < formula_len and formula[next_pos] == '(':
                            found_func = func_name
                            pos = next_pos
                            break

                if found_func:
                    # Encontrada uma função de agregação, agora precisamos extrair seus argumentos
                    # Encontra o parêntese de fechamento correspondente
                    closing_paren_pos, content = self.balance_parentheses(formula, pos)

                    if closing_paren_pos != -1:

                        # Localiza vírgulas de nível superior para separar argumentos de filtros
                        comma_positions = self.find_top_level_commas(content)

                        if comma_positions:
                            # Este é um caso de vírgula de nível superior, separe o argumento do filtro
                            arg_expr = content[:comma_positions[0]].strip()
                            filter_expr = content[comma_positions[0]+1:].strip()
                        else:
                            # Sem vírgula, todo o conteúdo é o argumento
                            arg_expr = content.strip()
                            filter_expr = ""

                        # Extrai variáveis do argumento e do filtro
                        arg_vars = self.extract_variables(arg_expr)
                        filter_vars = self.extract_variables(filter_expr)

                        full_func = f"{found_func}({content})"

                        # Constrói o objeto de agregação
                        # Inclui a função de agregação sem o filtro interno
                        if found_func in ["first", "last", "firstc", "lastc"]:
                            # Caso especial para funções first/last
                            base_func = f"{arg_expr}"
                        else:
                            base_func = f"{found_func.replace('_node','')}({arg_expr})"

                        # Corrige operadores de comparação no filtro
                        filter_expr = self._fix_comparison_operators(filter_expr)

                        aggr_obj = {
                            "base": full_func,  # A função de agregação sem o filtro
                            "eval": base_func,
                            "vars": arg_vars,
                            "global": ("_node" not in base_func),
                            "filter": filter_expr,
                            "filter_vars": filter_vars
                        }

                        # Adiciona a agregação encontrada à lista
                        aggregations.append(aggr_obj)

                        pos = closing_paren_pos + 1

                    else:
                        # Parênteses não balanceados, move para o próximo caractere
                        if self.debug:
                            self.logger.debug(f"Parênteses não balanceados na posição {pos}, pulando caractere")
                        pos += 1
                else:
                    # Sem função de agregação encontrada, move para o próximo caractere
                    pos += 1

            if self.debug:
                self.logger.debug(f"Análise completa da fórmula: {formula}")

            return aggregations
        except Exception as e:
            self.logger.exception("Erro inesperado na análise de funções de agregação: %s", e)
            return []
    
    def extract_non_aggregated_variables(self, formula: str, aggr_vars: List[str], filter_vars: List[str]) -> List[str]:
        """
        Extrai variáveis que não são parte de funções de agregação.

        Identifica variáveis na fórmula que não estão contabilizadas em
        funções de agregação ou filtros, que provavelmente são usadas diretamente em cálculos.

        Parâmetros:
            formula: A fórmula completa
            aggr_vars: Variáveis já identificadas em funções de agregação
            filter_vars: Variáveis usadas em condições de filtro

        Retorno:
            Lista de variáveis que não estão em funções de agregação ou filtros
        """
        try:
            # Localiza todas as variáveis na fórmula
            all_vars = self.extract_variables(formula)
            # Ordena as variáveis para consistência
            all_vars = set(sorted(all_vars, key=lambda x: (int(x[1:6]), x)))

            # Remove variables já presentes em funções de agregação ou filtros
            aggr_set = set(aggr_vars)
            filter_set = set(filter_vars)

            # Variáveis que não estão em funções de agregação ou filtros
            other_vars = all_vars - aggr_set - filter_set

            return list(other_vars)
        except Exception as e:
            self.logger.exception("Erro inesperado na extração de variáveis não agregadas: %s", e)
            return []
    
    def analyze_formula(self, formula_str: str) -> Dict:
        """
        Analisa a fórmula completa e extrai todas as funções de agregação e variáveis.

        Realiza uma análise abrangente da fórmula, identificando:
        - Todas as funções de agregação e seus componentes
        - Variáveis usadas em funções de agregação e seus filtros
        - Variáveis usadas diretamente na fórmula (não em agregações)
        - Cria um grafo de dependência (DAG) para avaliação da fórmula

        Parâmetros:
            formula_str: A fórmula a ser analisada

        Retorno:
            Dicionário com funções de agregação, suas variáveis e outras variáveis
        """
        try:
            if self.debug:
                self.logger.debug(f"Analisando fórmula: {formula_str}...")

            # Inicializa listas para armazenar resultados
            aggr_functions = []
            all_aggr_vars = []
            all_filter_vars = []
            # TODO remover dag_paths
            dag_paths = []

            # Extrai funções de agregação
            aggregations = self.parse_aggregate_functions(formula_str)

            # Processa as funções de agregação encontradas
            for idx, aggr in enumerate(aggregations):
                aggr_functions.append(aggr)
                all_aggr_vars.extend(aggr["vars"])
                all_filter_vars.extend(aggr["filter_vars"])

                # Adiciona variáveis aos caminhos do DAG
                # TODO remover dag_paths
                dag_paths.extend(aggr["vars"])
                dag_paths.extend(aggr["filter_vars"])

            # Remove duplicatas das listas de variáveis
            unique_aggr_vars = []
            for var in all_aggr_vars:
                if var not in unique_aggr_vars:
                    unique_aggr_vars.append(var)

            # Remove duplicatas das listas de variáveis de filtro
            unique_filter_vars = []
            for var in all_filter_vars:
                if var not in unique_filter_vars:
                    unique_filter_vars.append(var)

            # Extrai variáveis que não são agregadas
            if self.debug:
                self.logger.debug("Extraindo variáveis que não são agregadas")
            other_vars = self.extract_non_aggregated_variables(
                formula_str, unique_aggr_vars, unique_filter_vars
            )

            # Adiciona outras variáveis aos caminhos do DAG
            dag_paths.extend(other_vars)

            # Remove duplicatas dos caminhos do DAG enquanto preserva a ordem
            unique_dag_paths = []
            for path in dag_paths:
                if path not in unique_dag_paths:
                    unique_dag_paths.append(path)

            
            aggr_functions.sort(key=lambda x: x["base"])
            unique_dag_paths.sort(key=lambda x: (int(x[1:6]), x))
            other_vars.sort(key=lambda x: (int(x[1:6]), x))
            
            # Constrói o resultado final
            result = {
                "aggr": aggr_functions,
                "vars": other_vars,
                "dag_paths": unique_dag_paths
            }

            if self.debug:
                self.logger.debug(f"Análise completa da fórmula: {formula_str}")

            return result
        except Exception as e:
            self.logger.exception("Erro inesperado na análise da fórmula: %s", e)
            return {
                "aggr": [],
                "vars": [],
                "dag_paths": []
            }

    def parse_formula(self, formula: str) -> Dict:
        """
        Analisa uma fórmula e extrai suas funções de agregação, variáveis e caminhos do DAG.

        Este é o ponto de entrada principal para a análise de fórmulas, criando uma instância do FormulaParser
        e usando-a para analisar a fórmula.

        Parâmetros:
            formula: A fórmula a ser analisada

        Retorno:
            Dicionário com funções de agregação, suas variáveis e caminhos do DAG
        """
        try:
            if self.debug:
                self.logger.debug(f"Analisando fórmula: {formula[:50]}...")
            parser = FormulaParser()
            result = parser.analyze_formula(formula)
            if self.debug:
                self.logger.debug(f"Análise completa da fórmula: {formula[:50]}")
            return result
        except Exception as e:
            self.logger.exception("Erro inesperado na análise da fórmula: %s", e)
            return {
                "aggr": [],
                "vars": [],
                "dag_paths": []
            }

    def extract_formulas(self, data: Any, results_dict: Optional[Dict[str, Dict]] = None) -> List[Dict]:
        """
        Extrai recursivamente fórmulas da estrutura de dados em árvore.

        Esta função percorre a estrutura de dados, identificando entidades com fórmulas
        e coletando-as em um dicionário de resultados indexado pelo caminho da entidade para evitar duplicatas.

        A função lida com estruturas de dados hierárquicas, explorando recursivamente aninhados
        objetos e arrays para encontrar todas as definições de fórmulas.

        Parâmetros:
            data: O objeto de dados a ser processado (pode ser um dict ou list)
            results_dict: O dicionário para armazenar resultados por caminho (para evitar duplicatas)

        Retorno:
            Lista de entidades com suas fórmulas e IDs
        """
        try:
            # Inicializa o dicionário de resultados se não for fornecido
            if results_dict is None:
                results_dict = {}

            # Processa a lista de dados chamando recursivamente extract_formulas em cada item
            if isinstance(data, list):
                for idx, item in enumerate(data):
                    self.extract_formulas(item, results_dict)
                return list(results_dict.values())

            # Processa o objeto de dados (dicionário)
            if isinstance(data, dict):
                # Verifica se esta é uma entidade com fórmulas
                if "path" in data and "formulas" in data and "data" in data:
                    path = data["path"]
                    formulas = data.get("formulas", [])

                    # Somente processa se tiver fórmulas
                    if formulas:
                        if self.debug:
                            self.logger.debug(f"Encontrada entidade com path '{path}' contendo {len(formulas)} fórmulas")

                        # Extrai IDs dos dados
                        ids = []
                        for item in data.get("data", []):
                            if "id" in item and item["id"]:  # Apenas adiciona IDs não nulos
                                ids.append({"id": item["id"]})

                        # Cria ou atualiza a entrada no dicionário de resultados
                        if path in results_dict:
                            # Se a entidade já existe, mescla as fórmulas e IDs
                            if self.debug:
                                self.logger.debug(f"Mesclando entidade duplicada '{path}'")
                            existing = results_dict[path]

                            # Adiciona novas fórmulas se ainda não existirem
                            existing_formula_paths = {f["path"] for f in existing["formulas"]}
                            formulas_added = 0

                            for formula in formulas:
                                # Adiciona apenas se o caminho da fórmula não existir
                                if formula["path"] not in existing_formula_paths:
                                    existing["formulas"].append(formula)
                                    existing_formula_paths.add(formula["path"])
                                    formulas_added += 1

                            # Adiciona novos IDs se ainda não existirem
                            existing_ids = {id_obj["id"] for id_obj in existing["ids"]}
                            ids_added = 0

                            for id_obj in ids:
                                if id_obj["id"] not in existing_ids:
                                    existing["ids"].append(id_obj)
                                    existing_ids.add(id_obj["id"])
                                    ids_added += 1
                        else:
                            # Adiciona a entidade com suas fórmulas e IDs aos resultados
                            results_dict[path] = {
                                "path": path,
                                "formulas": formulas,
                                "ids": ids
                            }

                    # Continua o processamento recursivo do campo de dados
                    self.extract_formulas(data.get("data", []), results_dict)

                # Processa outros campos que podem conter dados aninhados
                for key, value in data.items():
                    if isinstance(value, (dict, list)) and key != "formulas":
                        self.extract_formulas(value, results_dict)

            return list(results_dict.values())
        except Exception as e:
            self.logger.exception("Erro inesperado na extração de fórmulas: %s", e)
            return []

    def parse_formulas(self, data: Any) -> List[Dict]:
        """
        Extrai, analisa e ordena fórmulas da estrutura de dados.

        Esta função fornece um pipeline completo para o processamento de fórmulas:
        1. Extrai fórmulas da estrutura de dados hierárquica
        2. Analisa cada fórmula para identificar seus componentes (variáveis, agregações, filtros)
        3. Ordena as fórmulas com base em suas dependências para avaliação adequada

        Parâmetros:
            data: O objeto de dados a ser processado (pode ser um dict ou list)

        Retorno:
            Lista de entidades com suas fórmulas e IDs, ordenadas para execução
        """
        if self.debug:
            self.logger.debug("Extraindo fórmulas da estrutura de dados")
        results = self.extract_formulas(data)
        if self.debug:
            self.logger.debug(f"Extraídas {len(results)} grupos de fórmulas")

        # Analisa cada fórmula para extrair funções de agregação e variáveis
        formula_count = 0
        for r in results:
            group_path = r.get("path", "unknown")
            formulas = r.get("formulas", [])
            if self.debug:
                self.logger.debug(f"Processando grupo '{group_path}' com {len(formulas)} fórmulas")
            
            for f in formulas:
                formula_path = f.get("path", "unknown")
                formula_value = f.get("value", "")

                # Tenta analisar a fórmula
                try:
                    f["parsed"] = self.parse_formula(formula_value)
                    formula_count += 1
                except Exception as e:
                    self.logger.exception("Erro inesperado ao analisar fórmula '%s': %s", formula_path, e)

        if self.debug:
            self.logger.info(f"Fórmulas analisadas com sucesso: {formula_count}")
    
        return results
