"""
Filtro de Expressões para Dados em Árvore

Propósito:
    Fornecer uma API para avaliar expressões condicionais contra dados hierárquicos em formato de árvore,
    permitindo consultas com operadores relacionais, lógicos e funções especiais (contains, first, last, firstc, lastc).

Responsabilidades principais:
    - Parsear expressões de filtro e convertê-las em uma AST segura.
    - Avaliar expressões sobre registros hierárquicos, navegando por subnós quando necessário.
    - Extrair valores (first/last/por data) para caminhos especificados nos resultados filtrados.
    - Suportar filtragem limitada a um nó (por record_id) e retorno de caminhos específicos.

Posição na arquitetura:
    Componente de lógica de domínio responsável pela filtragem/consulta de modelos em árvore. Atua entre a camada de
    persistência (ou carregamento de dados) e a camada de apresentação/serviço que consome conjuntos filtrados.

Dependências críticas:
    - ply (ply.lex e ply.yacc) — para análise léxica e sintática das expressões.
    - jmespath — utilitário opcional para navegação em JSON (presente no módulo).
    - log.logger (logger interno do projeto) — para registro de eventos e erros.
    - Bibliotecas padrão: re, hashlib, json, typing, os, sys.

Considerações de segurança:
    - Nunca usar exec/eval sobre expressões de usuários; o parser atual converte para AST e avalia de forma controlada.
    - Validar tamanhos e complexidade das expressões recebidas para evitar DoS por parsing pesado.
    - Sanitizar mensagens de log que contenham conteúdo fornecido pelo usuário para evitar vazamento de dados sensíveis.
    - Limitar recursos durante avaliações recursivas para evitar estouro de pilha ou loops inadvertidos em dados malformados.

Exemplo de uso básico:
    from filters.filters_paths import tree_data_filter

    tree = {
        "data": [
            {"id": "1", "fields": [{"path": "e00001v", "value": 1}], "data": []},
            {"id": "2", "fields": [{"path": "e00001v", "value": 2}], "data": []}
        ]
    }

    f = tree_data_filter()
    result = f.filter_tree_data(tree_data=tree, return_paths=["e00001v"], filter_expr="e00001v == 1")
    # result -> [{"path": "e00001v", "values": [1]}]  (exemplo de retorno esperado)
"""

import ply.lex as lex  # Analisador léxico para tokenização de expressões
import ply.yacc as yacc  # Analisador sintático para análise de expressões
import logging
from typing import Dict, Any, Optional, List, Union, Callable

class tree_data_filter:
    """
    Classe que implementa um analisador e avaliador de expressões de filtro para dados hierárquicos.
    
    Suporta as operações:
    - Comparações: ==, !=, >=, <=, >, <
    - Lógica: and, or
    - Funções: contains(), first(), last(), firstc(), lastc()

    Esta classe usa ply (Python Lex-Yacc) para validar os filtros
    e converter em uma sintaxe abstrata (AST) que representa como uma árvore de sintaxe abstrata que pode
    ser avaliada em dados estruturados.
    """

    # Definição de tokens usados na análise léxica
    tokens = (
        'IDENTIFIER', 'NUMBER', 'STRING', 'BOOLEAN',
        'EQUALS', 'NOTEQUALS', 'GREATEREQUAL', 'LESSEQUAL', 'GREATER', 'LESS',
        'AND', 'OR', 'LPAREN', 'RPAREN', 'COMMA',
        'CONTAINS', 'FIRST', 'LAST', 'FIRSTC', 'LASTC',
    )

    # Regras para tokens simples (operadores e símbolos)
    t_EQUALS = r'=='
    t_NOTEQUALS = r'!='
    t_GREATEREQUAL = r'>='
    t_LESSEQUAL = r'<='
    t_GREATER = r'>'
    t_LESS = r'<'
    t_LPAREN = r'\('
    t_RPAREN = r'\)'
    t_COMMA = r','
    
    # Caracteres a serem ignorados pelo analisador léxico
    t_ignore = ' \t'

    # Precedência de operadores (da mais baixa para a mais alta)
    precedence = (
        ('left', 'OR'),              # OR tem a menor precedência
        ('left', 'AND'),             # AND tem precedência intermediária
        ('left', 'EQUALS', 'NOTEQUALS', 'GREATEREQUAL', 'LESSEQUAL', 'GREATER', 'LESS'),  # Comparações têm alta precedência
    )

    # Definição para identificadores (nomes de campo, palavras-chave)
    def t_IDENTIFIER(self, t):
        r'[a-zA-Z][a-zA-Z0-9_]*'
        # Verifica se o identificador é uma palavra-chave especial
        if t.value == 'and':
            t.type = 'AND'
        elif t.value == 'or':
            t.type = 'OR'
        elif t.value == 'True' or t.value == 'False':
            t.type = 'BOOLEAN'
        elif t.value == 'contains':
            t.type = 'CONTAINS'
        elif t.value == 'first':
            t.type = 'FIRST'
        elif t.value == 'last':
            t.type = 'LAST'
        elif t.value == 'firstc':
            t.type = 'FIRSTC'
        elif t.value == 'lastc':
            t.type = 'LASTC'
        return t

    # Definição de números inteiros
    def t_NUMBER(self, t):
        r'\d+'
        t.value = int(t.value)  # Converte o valor para inteiro
        return t

    # Definição para strings (delimitadas por aspas simples)
    def t_STRING(self, t):
        r"'[^']*'"
        # Remove as aspas do início e do fim para obter o valor real da string
        t.value = t.value[1:-1]
        return t

    # Tratamento de erros léxicos (caracteres não reconhecidos)
    def t_error(self, t):
        error_msg = f"Caracter ilegal '{t.value[0]}' na posição {t.lexpos}"
        self.logger.error(error_msg)
        if self.debug:
            self.logger.debug("Pulando caractere ilegal e continuando a análise léxica")
        t.lexer.skip(1)  # Ignora o caractere não reconhecido

    # ----- REGRAS DE PRODUÇÃO PARA ANÁLISE SINTÁTICA -----
    # Expressão com operador binário (==, !=, >=, <=, >, <, and, or)
    def p_expression_binop(self, p):
        '''expression : expression EQUALS expression
                      | expression NOTEQUALS expression
                      | expression GREATEREQUAL expression
                      | expression LESSEQUAL expression
                      | expression GREATER expression
                      | expression LESS expression
                      | expression AND expression
                      | expression OR expression'''
        # Cria um nó AST para o operador binário: (tipo, operador, operando_esquerdo, operando_direito)
        p[0] = ('binop', p[2], p[1], p[3])

    # Expressão agrupada entre parênteses
    def p_expression_group(self, p):
        'expression : LPAREN expression RPAREN'
        # Cria um nó AST para expressão agrupada: (tipo, expressão)
        p[0] = ('group', p[2])

    # Função contains(x, y) - verifica se x contém y
    def p_expression_contains(self, p):
        'expression : CONTAINS LPAREN expression COMMA expression RPAREN'
        # Cria um nó AST para a função contains: (tipo, contêiner, item)
        p[0] = ('contains', p[3], p[5])

    # Função first(x) - retorna o primeiro valor para o caminho x
    def p_expression_first(self, p):
        'expression : FIRST LPAREN expression RPAREN'
        # Cria um nó AST para a função first: (tipo, caminho)
        p[0] = ('first', p[3])

    # Função last(x) - retorna o último valor para o caminho x
    def p_expression_last(self, p):
        'expression : LAST LPAREN expression RPAREN'
        # Cria um nó AST para a função last: (tipo, caminho)
        p[0] = ('last', p[3])

    # Função firstc(x) - retorna o primeiro valor para o caminho x pela data de criação mais recente
    def p_expression_firstc(self, p):
        'expression : FIRSTC LPAREN expression RPAREN'
        # Cria um nó AST para a função firstc: (tipo, caminho)
        p[0] = ('firstc', p[3])

    # Função lastc(x) - retorna o primeiro valor para o caminho x pela data de criação mais antiga
    def p_expression_lastc(self, p):
        'expression : LASTC LPAREN expression RPAREN'
        # Cria um nó AST para a função lastc: (tipo, caminho)
        p[0] = ('lastc', p[3])

    # Identificador (nome do campo)
    def p_expression_identifier(self, p):
        'expression : IDENTIFIER'
        # Cria um nó AST para identificador: (tipo, nome)
        p[0] = ('identifier', p[1])

    # Número inteiro
    def p_expression_number(self, p):
        'expression : NUMBER'
        # Cria um nó AST para número: (tipo, valor)
        p[0] = ('number', p[1])

    # Texto (texto entre aspas)
    def p_expression_string(self, p):
        'expression : STRING'
        # Cria um nó AST para string: (tipo, valor)
        p[0] = ('string', p[1])

    # Valor booleano (True/False)
    def p_expression_boolean(self, p):
        'expression : BOOLEAN'
        # Cria um nó AST para booleano: (tipo, valor)
        p[0] = ('boolean', p[1])

    # Lidando com erros sintáticos
    def p_error(self, p):
        if p:
            error_msg = f"Erro de sintaxe em '{p.value}' (tipo de token: {p.type}, posição: {p.lexpos})"
            self.logger.error(error_msg)
            if self.debug:
                self.logger.debug(f"Estado do parser no erro: {self.parser.state}")
        else:
            error_msg = "Erro de sintaxe no final da expressão (fim inesperado da entrada)"
            self.logger.error(error_msg)
            if self.debug:
                self.logger.debug("Nenhuma informação de token disponível para este erro de sintaxe")

    def __init__(self, debug: bool = False):
        try:
            self.logger = logging.getLogger(__name__)
            self.debug = debug
            # Inicializa o analisador léxico e o analisador sintático
            self.lexer = lex.lex(module=self)
            self.parser = yacc.yacc(module=self)
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.exception("Erro inesperado durante inicialização: %s", e)
            raise

    def _extract_tree_structure(self, tree_data: Dict) -> Any:
        """
        Extrai uma representação de estrutura leve dos dados da árvore para geração de chave de cache.
        
        Parâmetros:
            tree_data: Estrutura de dados da árvore completa

        Retorno:
            Representação simplificada da estrutura da árvore
        """

        def extract_node_structure(node):
            # Extrai a estrutura de um nó, ignorando valores específicos
            if isinstance(node, dict):
                structure = {}
                if 'id' in node:
                    structure['id'] = node['id']
                if 'fields' in node and node['fields']:
                    structure['fields'] = [field.get('path') for field in node['fields'] if field.get('path')]
                if 'data' in node and node['data']:
                    structure['data'] = [extract_node_structure(child) for child in node['data']]
                return structure
            elif isinstance(node, list):
                return [extract_node_structure(item) for item in node]
            return node
        
        # Extrai a estrutura da árvore inteira
        tree_structure = extract_node_structure(tree_data)

        return tree_structure
        
    def parse(self, expression: str):
        """
        Avalia a expressão condicional e retorna a árvore de sintaxe (AST).

        Parâmetros:
            expression: String contendo a expressão de filtro a ser analisada

        Retorno:
            Sintaxe abstrata da árvore representando a expressão
        """
        try:
            ast = self.parser.parse(expression)
            return ast
        except Exception as e:
            self.logger.exception("Erro inesperado durante parsing da expressão: %s", e)
            return None
    
    def convert_to_python_function(self, expression: str) -> Callable:
        """
        Converte uma expressão condicional em uma função Python que pode ser
        usada para filtrar registros.

        Parâmetros:
            expression: Expressão condicional (ex: "e00001v == 1")

        Retorno:
            Uma função Python que aceita um registro e retorna True/False

        Exceções:
            ValueError: Se a expressão não puder ser analisada
        """
        try:
            ast = self.parse(expression)
            if ast is None:
                error_msg = f"Não foi possível fazer o parse da expressão: {expression}"
                self.logger.error(error_msg)
                raise ValueError(error_msg)

            def filter_function(record, tree_data):
                try:
                    result = self._evaluate_ast(ast, record, tree_data)
                    return result
                except Exception as e:
                    self.logger.exception("Erro inesperado durante avaliação do filtro: %s", e)
                    return False

            return filter_function
        except ValueError:
            raise
        except Exception as e:
            self.logger.exception("Erro inesperado durante conversão para função Python: %s", e)
            raise ValueError(f"Erro durante conversão da expressão: {e}")
    
    def _evaluate_ast(self, ast_node, record, tree_data):
        """
        Avalia uma AST de uma expressão condicional para um registro específico.
        Utiliza recursividade para verificar os subníveis da hierarquia.

        Parâmetros:
            ast_node: Nó da AST a ser avaliado
            record: Registro a ser filtrado
            tree_data: Dados completos da árvore para funções especiais

        Retorno:
            Resultado da avaliação (True/False)
        """
        if record is None:
            return False
            
        node_type = ast_node[0]  # Get the AST node type

        if node_type == 'binop':
            op = ast_node[1]  # Operador (==, !=, >=, <=, >, <, and, or)
            
            # Tratamento especial para operadores lógicos para suportar a hierarquia
            if op == 'and':
                # Primeiro, verifica se a condição esquerda está satisfeita no nível atual
                left_result = self._evaluate_condition(ast_node[2], record, tree_data)
                if not left_result:
                    return False
                
                # Se o lado esquerdo for satisfeito, verifica o lado direito no nível atual
                right_result = self._evaluate_condition(ast_node[3], record, tree_data)
                if not right_result:
                    return False

                return True
            
            elif op == 'or':
                # Avalia o lado esquerdo no nível atual primeiro
                left_result = self._evaluate_condition(ast_node[2], record, tree_data)
                
                # Se o lado esquerdo for verdadeiro, não é necessário avaliar o lado direito
                if left_result:
                    return True
                
                # Se o lado esquerdo for falso, o resultado depende do lado direito no nível atual
                right_result = self._evaluate_condition(ast_node[3], record, tree_data)
                if right_result:
                    return True
                    
                return False
            
            # Para operadores de comparação no nível atual
            left = self._evaluate_condition(ast_node[2], record, tree_data)
            right = self._evaluate_condition(ast_node[3], record, tree_data)
            
            # Tratamento seguro para operadores de comparação
            try:
                operator_result = False
                if op == '==':
                    operator_result = left == right
                elif op == '!=':
                    operator_result = left != right
                elif op == '>=':
                    operator_result = left >= right
                elif op == '<=':
                    operator_result = left <= right
                elif op == '>':
                    operator_result = left > right
                elif op == '<':
                    operator_result = left < right
                return operator_result
            except Exception as e:
                self.logger.exception("Erro inesperado durante comparação: %s", e)
                return False
                
        # Para nós que não são binop, apenas avalia a condição no nível atual
        return self._evaluate_condition(ast_node, record, tree_data)
    
    def _evaluate_condition(self, ast_node, record, tree_data):
        """
        Avalia uma condição em um registro específico.
        
        Parâmetros:
            ast_node: Nó AST a ser avaliado
            record: Registro a ser filtrado
            tree_data: Dados completos da árvore para funções especiais
            
        Returno:
            Resultado da avaliação (True/False, ou valor do nó para identificadores, números, etc.)
        """
        node_type = ast_node[0]
        
        if node_type == 'binop':
            op = ast_node[1]
            
            # Para operadores lógicos simples (sem hierarquia)
            if op == 'and':
                # Avaliação com atalho para AND
                left_result = self._evaluate_condition(ast_node[2], record, tree_data)
                if not left_result:
                    return False
                return self._evaluate_condition(ast_node[3], record, tree_data)
                
            elif op == 'or':
                # Avaliação com atalho para OR
                left_result = self._evaluate_condition(ast_node[2], record, tree_data)
                if left_result:
                    return True
                return self._evaluate_condition(ast_node[3], record, tree_data)
                
            # Para operadores de comparação
            left = self._evaluate_condition(ast_node[2], record, tree_data)
            right = self._evaluate_condition(ast_node[3], record, tree_data)
            
            # Tratamento seguro para operadores de comparação
            try:
                if op == '==':
                    return left == right
                elif op == '!=':
                    return left != right
                elif op == '>=':
                    return left >= right
                elif op == '<=':
                    return left <= right
                elif op == '>':
                    return left > right
                elif op == '<':
                    return left < right
            except Exception as e:
                self.logger.exception("Erro inesperado durante comparação em _evaluate_condition: %s", e)
                return False
            
        elif node_type == 'group':
            # Avalia a expressão dentro dos parênteses
            return self._evaluate_condition(ast_node[1], record, tree_data)
            
        elif node_type == 'contains':
            # Função contains(x, y) - verifica se y está contido em x
            container = self._evaluate_condition(ast_node[1], record, tree_data)
            item = self._evaluate_condition(ast_node[2], record, tree_data)
            # Verifica se o contêiner é válido
            if container is None:
                return False
                # Converte para string para verificar a inclusão
            return str(item) in str(container)
            
        elif node_type == 'first':
            # Função first(x) - retorna o primeiro valor para o caminho x
            path = self._get_path_from_ast(ast_node[1])
            # Obtém o primeiro valor para o caminho nos dados da árvore
            if path and tree_data and 'data' in tree_data:
                result = self._find_first_value_for_path(path, tree_data['data'])
                # No contexto do filtro, considera verdadeiro se o valor no registro atual corresponder ao primeiro valor
                if 'fields' in record and record['fields'] is not None:
                    for field in record['fields']:
                        if field.get('path') == path and field.get('value') == result:
                            return True
                return False  # Este registro não corresponde ao primeiro valor
            return False
            
        elif node_type == 'last':
            # Função last(x) - retorna o último valor para o caminho x
            path = self._get_path_from_ast(ast_node[1])
            # Obtém o último valor para o caminho nos dados da árvore
            if path and tree_data and 'data' in tree_data:
                result = self._find_last_value_for_path(path, tree_data['data'])
                # No contexto do filtro, considera verdadeiro se o valor no registro atual corresponder ao último valor
                if 'fields' in record and record['fields'] is not None:
                    for field in record['fields']:
                        if field.get('path') == path and field.get('value') == result:
                            return True
                return False  # Este registro não corresponde ao último valor
            return False
            
        elif node_type == 'firstc':
            # Função firstc(x) - retorna o primeiro valor pelo critério de data de criação mais recente
            path = self._get_path_from_ast(ast_node[1])
            # Obtém o primeiro valor cujo campo "creation" para o caminho seja o mais recente
            if path and tree_data and 'data' in tree_data:
                result = self._find_firstc_value_for_path(path, tree_data['data'])
                # No contexto do filtro, considera verdadeiro se o valor no registro atual corresponder ao resultado
                if 'fields' in record and record['fields'] is not None:
                    for field in record['fields']:
                        if field.get('path') == path and field.get('value') == result:
                            return True
                return False  # Este registro não corresponde ao resultado
            
        elif node_type == 'lastc':
            # Função lastc(x) - retorna o primeiro valor pelo critério de data de criação mais antiga
            path = self._get_path_from_ast(ast_node[1])
            # Obtém o primeiro valor cujo campo "creation" para o caminho seja o mais antigo
            if path and tree_data and 'data' in tree_data:
                result = self._find_lastc_value_for_path(path, tree_data['data'])
                # No contexto do filtro, considera verdadeiro se o valor no registro atual corresponder ao resultado
                if 'fields' in record and record['fields'] is not None:
                    for field in record['fields']:
                        if field.get('path') == path and field.get('value') == result:
                            return True
                return False  # Este registro não corresponde ao resultado
            return False
            
        elif node_type == 'identifier':
            # Procura o valor do campo no registro atual
            if 'fields' in record and record['fields'] is not None:
                for field in record['fields']:
                    if field.get('path') == ast_node[1]:
                        return field.get('value')

            # Se não encontrado no nível atual, procura em subnós
            if 'data' in record and record['data'] is not None:
                for subnode in record['data']:
                    # Procura em nós que representam propriedades específicas
                    if isinstance(subnode, dict) and 'path' in subnode and subnode['path'] == ast_node[1] and 'data' in subnode and subnode['data']:
                        for data_item in subnode['data']:
                            if 'fields' in data_item and data_item['fields']:
                                return data_item['fields'][0].get('value')

                    # Procura em campos de subnós genéricos
                    elif isinstance(subnode, dict) and 'fields' in subnode and subnode['fields']:
                        for field in subnode['fields']:
                            if field.get('path') == ast_node[1]:
                                return field.get('value')

            return None
            
        elif node_type == 'numeric':
            # Retorna o valor numérico
            return ast_node[1]

        elif node_type == 'float':
            # Retorna o valor numérico
            return ast_node[1]

        elif node_type == 'number':
            # Retorna o valor numérico
            return ast_node[1]
            
        elif node_type == 'string':
            # Retorna o valor da string
            return ast_node[1]
            
        elif node_type == 'boolean':
            # Retornma o valor booleano
            return ast_node[1] == 'True'
                
        return None
    
    def _get_path_from_ast(self, ast_node):
        """
        Extrai o caminho de um nó da AST (para funções como first, last, etc.)

        Parâmetros:
            ast_node: Nó da AST contendo um identificador de caminho

        Retorno:
            String do caminho se o nó for um identificador, None caso contrário
        """
        if ast_node[0] == 'identifier':
            return ast_node[1]
        return None

    def _find_value_for_path(self, path, data_nodes):
        """
        Encontra o valor para um determinado caminho nos dados da árvore.

        Parâmetros:
            path: Caminho a ser procurado (ex: "e00001v")
            data_nodes: Lista de nós de dados a serem pesquisados

        Retorno:
            O valor encontrado para o caminho ou None se não encontrado
        """
        # Variável para armazenar os valores
        # Utiliza uma lista para permitir modificação dentro da função aninhada
        values = []
        
        # Percorre os nós de dados recursivamente
        def search_nodes(nodes):
            # Ignora se não for uma lista
            if not nodes or not isinstance(nodes, list):
                return None
                
            for node in nodes:

                # Se o nó for uma lista, pesquisa recursivamente
                if isinstance(node, list):
                    search_nodes(node)

                # Verifica se o nó possui campos
                if isinstance(node, dict) and 'fields' in node and node['fields'] is not None:
                    for field in node['fields']:
                        if field.get('path') == path:
                            values.append(field.get('value'))
                
                # Pesquisa recursivamente em subnós
                if isinstance(node, dict) and 'data' in node and node['data']:
                    # Primeiro, tenta pesquisar diretamente na lista de dados
                    for data_item in node['data']:
                        if isinstance(data_item, dict) and 'path' in data_item and data_item['path'] == path and 'data' in data_item and data_item['data']:
                            # Se encontrar um nó com o caminho correto, retorna o primeiro valor
                            sub_node = data_item['data'][0]
                            if 'fields' in sub_node and sub_node['fields']:
                                values.append(sub_node['fields'][0].get('value'))
                    
                    # Se não encontrado, pesquisa recursivamente em todos os subnós
                    search_nodes(node['data'])
                        
                # Se o nó for um dicionário com subnós aninhados
                elif isinstance(node, dict) and 'data' in node and isinstance(node['data'], list):
                    search_nodes(node['data'])

            # Verifica se encontramos algum valor
            if not values:
                return [None]
            
            return values
            
        return_values = search_nodes(data_nodes)
        return return_values

    def _find_first_value_for_path(self, path, data_nodes):
        """
        Encontra o primeiro valor para um determinado caminho nos dados da árvore.
        
        Parâmetros:
            path: Caminho a ser procurado (ex: "e00001v")
            data_nodes: Lista de nós de dados a serem pesquisados
            
        Retorno:
            O primeiro valor encontrado para o caminho ou None se não encontrado
        """
        # Variável para armazenar o primeiro valor encontrado
        # Utiliza uma lista para permitir modificação dentro da função aninhada
        first_value = [None]

        def set_default_value(value, value_type):
            if not value is None:
                return value
            else:
                if value_type == "numeric":
                    return 0.0
                elif value_type == "key":
                    return ''
                elif value_type == "string":
                    return ''
                else:
                    return ''
        
        # Percorre os nós de dados recursivamente
        def search_nodes(nodes):
            # Se já encontramos um valor, não precisamos continuar a busca
            if first_value[0] is not None:
                return first_value[0]
                
            if not nodes or not isinstance(nodes, list):
                return None
                
            for node in nodes:
                # Se já encontramos um valor, encerra o loop
                if first_value[0] is not None:
                    break
                    
                # Verifica se o nó possui campos
                if 'fields' in node and node['fields'] is not None:
                    for field in node['fields']:
                        if field.get('path') == path:
                            value_type = field.get('type')
                            first_value[0] = field.get('value')
                            return set_default_value(first_value[0], value_type)
                
                # Pesquisa recursivamente em subnós
                if first_value[0] is None and 'data' in node and node['data']:
                    # Primeiro, tenta pesquisar diretamente na lista de dados
                    for data_item in node['data']:
                        if first_value[0] is not None:
                            break
                            
                        if isinstance(data_item, dict) and 'path' in data_item and data_item['path'] == path and 'data' in data_item and data_item['data']:
                            # Se encontrar um nó com o caminho correto, retorna o primeiro valor
                            sub_node = data_item['data'][0]
                            if 'fields' in sub_node and sub_node['fields']:
                                value_type = sub_node['fields'][0].get('type')
                                first_value[0] = sub_node['fields'][0].get('value')
                                return set_default_value(first_value[0], value_type)
                    
                    # Se não encontrado, pesquisa recursivamente em todos os subnós
                    if first_value[0] is None:
                        result = search_nodes(node['data'])
                        if result is not None:
                            return result
                        
                # Se o nó for um dicionário com subnós aninhados
                elif first_value[0] is None and 'data' in node and isinstance(node['data'], list):
                    result = search_nodes(node['data'])
                    if result is not None:
                        return result
                        
            return first_value[0]
            
        return search_nodes(data_nodes)
        
    def _find_last_value_for_path(self, path, data_nodes):
        """
        Encontra o último valor para um determinado caminho nos dados da árvore.
        
        Parâmetros:
            path: Caminho a ser procurado (ex: "e00001v")
            data_nodes: Lista de nós de dados a serem pesquisados
            
        Retorno:
            O último valor encontrado para o caminho ou None se não encontrado
        """
        last_value = None
        
        # Percorre os nós de dados recursivamente
        def search_nodes(nodes):
            nonlocal last_value
            
            if not nodes or not isinstance(nodes, list):
                return None
                
            # Percorre a lista em ordem reversa para encontrar o último valor primeiro
            for node in reversed(nodes):
                # Verifica se o nó possui campos
                if 'fields' in node and node['fields'] is not None:
                    for field in node['fields']:
                        if field.get('path') == path:
                            last_value = field.get('value')
                
                # Pesquisa recursivamente em subnós, em ordem reversa
                if 'data' in node and node['data']:
                    # Verifica subnós específicos para o caminho
                    for data_item in reversed(node['data']):
                        if isinstance(data_item, dict) and 'path' in data_item and data_item['path'] == path and 'data' in data_item and data_item['data']:
                            # Se encontrar um nó com o caminho correto, verifica o último valor
                            sub_nodes = data_item['data']
                            if sub_nodes:
                                sub_node = sub_nodes[-1]  # Toma o último subnó
                                if 'fields' in sub_node and sub_node['fields']:
                                    last_value = sub_node['fields'][0].get('value')
                    
                    # Pesquisa recursivamente em todos os subnós, em ordem reversa
                    search_nodes(node['data'])
                        
                # Se o nó for um dicionário com subnós aninhados
                elif 'data' in node and isinstance(node['data'], list):
                    search_nodes(node['data'])
        
        # Inicia a busca nos nós de dados
        search_nodes(data_nodes)
        return last_value
        
    def _find_firstc_value_for_path(self, path, data_nodes):
        """
        Encontra o primeiro valor para um determinado caminho nos dados da árvore,
        onde a data de "criação" é a mais recente.
        
        Parâmetros:
            path: Caminho a ser procurado (ex: "e00001v")
            data_nodes: Lista de nós de dados a serem pesquisados
            
        Retorno:
            O valor do primeiro nó com o caminho especificado cuja data de criação é a mais recente
        """
        # Lista para armazenar os nós encontrados com suas datas de criação
        found_nodes = []
        
        # Percorre os nós de dados recursivamente
        def search_nodes(nodes):
            if not nodes or not isinstance(nodes, list):
                return
                
            for node in nodes:
                # Verifica se o nó possui campos e data de criação
                if 'fields' in node and node['fields'] is not None and 'creation' in node:
                    for field in node['fields']:
                        if field.get('path') == path:
                            # Armazena o valor, a data de criação e o nó
                            found_nodes.append({
                                'value': field.get('value'),
                                'creation': node.get('creation'),
                                'node': node
                            })
                
                # Pesquisa recursivamente em subnós
                if 'data' in node and node['data']:
                    # Verifica subnós específicos para o caminho
                    for data_item in node['data']:
                        if isinstance(data_item, dict) and 'path' in data_item and data_item['path'] == path and 'data' in data_item and data_item['data']:
                            # Para cada subnó correspondente ao caminho, verifica seus dados
                            for sub_node in data_item['data']:
                                if 'fields' in sub_node and sub_node['fields'] and 'creation' in sub_node:
                                    # Armazena o valor, a data de criação e o nó
                                    found_nodes.append({
                                        'value': sub_node['fields'][0].get('value'),
                                        'creation': sub_node.get('creation'),
                                        'node': sub_node
                                    })
                    
                    # Pesquisa recursivamente em todos os subnós
                    search_nodes(node['data'])
                        
                # Se o nó for um dicionário com subnós aninhados
                elif 'data' in node and isinstance(node['data'], list):
                    search_nodes(node['data'])
        
        # Inicia a busca nos nós de dados
        search_nodes(data_nodes)
        
        # Se nenhum nó for encontrado, retorna None
        if not found_nodes:
            return None
        
        # Ordena os nós encontrados por data de criação (o mais recente primeiro)
        sorted_nodes = sorted(found_nodes, key=lambda x: x['creation'], reverse=True)
        
        # Retorna o valor do nó com a data de criação mais recente
        return sorted_nodes[0]['value'] if sorted_nodes else None
        
    def _find_lastc_value_for_path(self, path, data_nodes):
        """
        Encontra o primeiro valor para um determinado caminho nos dados da árvore,
        onde a data de "criação" é a mais antiga.
        
        Parâmetros:
            path: Caminho a ser procurado (ex: "e00001v")
            data_nodes: Lista de nós de dados a serem pesquisados
            
        Retorno:
            O valor do primeiro nó com o caminho especificado cuja data de criação é a mais antiga
        """
        # Lista para armazenar os nós encontrados com suas datas de criação
        found_nodes = []
        
        # Percorre os nós de dados recursivamente
        def search_nodes(nodes):
            if not nodes or not isinstance(nodes, list):
                return
                
            for node in nodes:
                # Verifica se o nó possui campos e data de criação
                if 'fields' in node and node['fields'] is not None and 'creation' in node:
                    for field in node['fields']:
                        if field.get('path') == path:
                            # Armazena o valor, a data de criação e o nó
                            found_nodes.append({
                                'value': field.get('value'),
                                'creation': node.get('creation'),
                                'node': node
                            })
                
                # Pesquisa recursivamente em subnós
                if 'data' in node and node['data']:
                    # Verifica subnós específicos para o caminho
                    for data_item in node['data']:
                        if isinstance(data_item, dict) and 'path' in data_item and data_item['path'] == path and 'data' in data_item and data_item['data']:
                            # Para cada subnó correspondente ao caminho, verifica seus dados
                            for sub_node in data_item['data']:
                                if 'fields' in sub_node and sub_node['fields'] and 'creation' in sub_node:
                                    # Armazena o valor, a data de criação e o nó
                                    found_nodes.append({
                                        'value': sub_node['fields'][0].get('value'),
                                        'creation': sub_node.get('creation'),
                                        'node': sub_node
                                    })
                    
                    # Pesquisa recursivamente em todos os subnós
                    search_nodes(node['data'])
                        
                # Se o nó for um dicionário com subnós aninhados
                elif 'data' in node and isinstance(node['data'], list):
                    search_nodes(node['data'])
        
        # Inicia a busca nos nós de dados
        search_nodes(data_nodes)
        
        # Se nenhum nó for encontrado, retorna None
        if not found_nodes:
            return None
        
        # Ordena os nós encontrados por data de criação (o mais antigo primeiro - sem reverse=True)
        sorted_nodes = sorted(found_nodes, key=lambda x: x['creation'])
        
        # Retorna o valor do nó com a data de criação mais antiga
        return sorted_nodes[0]['value'] if sorted_nodes else None
    
    def filter_tree_data(
            self,
            tree_data: Dict,
            return_paths: List[str],
            record_id: Optional[str] = None,
            filter_expr: Optional[str] = None,
            lock_node: Optional[bool] = False) -> Union[List[Dict], Dict[str, Any]]:
        """
        Filtra os dados da árvore utilizando uma expressão condicional customizada.

        Esta é a função de API principal para filtrar dados hierárquicos. Ela converte a
        expressão condicional fornecida em uma função Python e utiliza-a para filtrar
        os dados da árvore, com suporte para funções especiais e filtragem hierárquica.

        Parâmetros:
            tree_data: Dados da árvore em formato JSON
            filter_expr: Expressão condicional (ex: "e00001v == 1 and e00002v != True")
            return_paths: Lista opcional de caminhos para extrair valores dos registros filtrados.
                        Se fornecido, a função retorna um dicionário mapeando cada caminho
                        para seus respectivos valores dos registros filtrados.
            record_id: ID opcional para limitar a busca
            lock_node: Flag opcional para bloquear a busca no registro especificado

        Retorno:
            Se return_paths for None:
                Lista de registros filtrados que correspondem à expressão
            Se return_paths for fornecido:
                Dicionário mapeando cada caminho para a lista de valores extraídos dos registros filtrados
        """

        filter_function = None

        def filter_global(records):
            if self.debug:
                self.logger.debug(f"Realizando filtragem global recursiva em {len(records) if isinstance(records, list) else 'não-lista'} registros")
            
            g_filtered_records = []
            
            # Aplica a função de filtro a cada registro
            for record in records:
                
                # Se o registro possuir 'fields'
                if record.get('fields', []):
                    if self.debug:
                        self.logger.debug(f"Avaliando registro com ID: {record.get('id')} caminho {record.get('fields')[0]['path']}")
                    if filter_function is not None and filter_function(record, tree_data):
                        g_filtered_records.append(record)

                if isinstance(record, dict) and 'data' in record and record['data']:
                    g_filtered_records.extend(filter_global(record["data"]))

            return g_filtered_records

        if self.debug:
            if filter_expr:
                self.logger.debug(f"Iniciando operação de filtragem com a expressão: {filter_expr}")
            if record_id:
                self.logger.debug(f"Filtrando pelo record_id: {record_id}")
            if return_paths:
                self.logger.debug(f"Extraindo valores para os caminhos: {return_paths}")

        # Converte a expressão para uma função de filtro Python
        if filter_expr:
            try:
                if self.debug:
                    self.logger.debug("Convertendo a expressão para função de filtro Python")
                filter_function = self.convert_to_python_function(filter_expr)
                if self.debug:
                    self.logger.debug("Função de filtro criada com sucesso")
            except Exception as e:
                error_msg = f"Erro ao converter a expressão '{filter_expr}': {str(e)}"
                self.logger.error(error_msg)
                if self.debug:
                    self.logger.debug(error_msg)
                return []
        
        values_return = []

        # Se tivermos um record_id, precisamos verificar se o caminho (path_expr) é interno a esse registro
        if record_id:
            if self.debug:
                self.logger.info(f"Procurando registro com ID: {record_id} para limitar a busca")

            # Encontra o registro e seus filhos com o ID especificado
            record_node = self._find_record_by_id(tree_data, record_id)

            # Se o registro for encontrado, limita a busca a esse registro e seus filhos
            if record_node:

                if self.debug:
                    self.logger.info(f"Registro com ID: {record_id} encontrado")

                # Limita a busca a esse registro e seus filhos
                records = self._extract_records_from_node(record_node)
                if self.debug:
                    self.logger.info(f"Foram extraídos {len(records)} registros do nó com ID: {record_id}")
                
                # Aplica a função de filtro a cada registro
                if filter_expr:
                    filtered_records = []
                    for record in records:
                        # Garante que filter_function seja "callable" antes de invocar
                        if isinstance(record, dict) and filter_function(record, tree_data): # type: ignore
                            filtered_records.append(record)
                else:
                    filtered_records = records

                if self.debug:
                    self.logger.debug(f"Filtro aplicado: encontrados {len(filtered_records)} registros correspondentes de {len(records)} no nó com ID: {record_id}")
                    self.logger.debug(f"Extraindo valores para {len(return_paths)} caminhos a partir dos registros filtrados")

                # Extrai valores para os caminhos especificados se return_paths for fornecido
                result = self._extract_values_for_paths(filtered_records, return_paths)

                if self.debug:
                    self.logger.debug(f"Foram extraídos valores para {len(result)} caminhos")

                # Verifica se os caminhos são internos ao registro
                for path in return_paths:                        
                    if len(result[path]) > 0:
                        values_return.append({"path": path, "values": result[path]})

                # Se todos os caminhos forem internos ao registro, retorna os valores
                for path in values_return:
                    return_paths.remove(path["path"])

                if return_paths == []:
                    if self.debug:
                        self.logger.info(f"Todos os caminhos processados internamente para o registro {record_id}, retornando {len(values_return)} resultados")
                    return values_return

                # Se lock_node estiver ativo, retorna resultados vazios para os restantes
                if lock_node:
                    for path in return_paths:
                        values_return.append({"path": path, "values": []})                   
                    return values_return

        # Se chegarmos aqui, não estamos limitando a busca a um registro específico ou o caminho não está dentro do record_id, então ignora record_id
        # Obtém todos os registros dos dados da árvore
        records = tree_data.get('data', [])
        
        # Aplica a função de filtro a cada registro
        if filter_expr:
            self.filtered_nodes = []
            r_global = filter_global(records)
            if isinstance(r_global, dict) and 'data' in r_global:
                filtered_records = r_global['data'] # type: ignore
            elif isinstance(r_global, list):
                filtered_records = r_global
            else:
                filtered_records = []
        else:
            filtered_records = records
        
        if self.debug:
            self.logger.info(f"Filtro aplicado: encontrados {len(filtered_records)} registros correspondentes de {len(records)}")

        # Extrai valores para os caminhos especificados se return_paths for fornecido
        result = self._extract_values_for_paths(filtered_records, return_paths)
        if self.debug:
            self.logger.info(f"Foram extraídos valores para {len(result)} caminhos")

        for path in return_paths:                        
            if len(result[path]) > 0:
                values_return.append({"path": path, "values": result[path]})

        return values_return

    def _extract_values_for_paths(self, records: List[Dict], paths: List[str]) -> Dict[str, List[Any]]:
        """
        Extrai valores para os caminhos especificados a partir de uma lista de registros.

        Parâmetros:
            records: Lista de registros filtrados para extrair os valores
            paths: Lista de caminhos para os quais extrair os valores

        Retorno:
            Dicionário mapeando cada caminho para uma lista de valores extraídos dos registros
        """

        result = {path: [] for path in paths}
        converter = tree_data_filter()
        
        for path in paths:
            
            # Inicializa o resultado para o caminho
            result[path] = []

            if self.debug:
                self.logger.debug(f"Processando caminho: {path}")

            # Trata funções especiais (first, last, firstc, lastc)
            if path.startswith("first(") and path.endswith(")"):
                # Extrai o caminho do campo de first(...)
                field_path = path[6:-1]
                if self.debug:
                    self.logger.debug(f"Extraindo o primeiro valor para o campo: {field_path}")
                value = converter._find_first_value_for_path(field_path, records)
                result[path] = [value] if value is not None else []  # type: ignore
                if value is None: # type: ignore
                    self.logger.error("Não foi possível extrair o primeiro valor: %s não encontrado", field_path)
                continue
                
            elif path.startswith("last(") and path.endswith(")"):
                # Extrai o caminho do campo de last(...)
                field_path = path[5:-1]
                if self.debug:
                    self.logger.debug(f"Extraindo o último valor para o campo: {field_path}")
                value = converter._find_last_value_for_path(field_path, records)
                result[path] = [value] if value is not None else []
                continue
                
            elif path.startswith("firstc(") and path.endswith(")"):
                # Extrai o caminho do campo de firstc(...)
                field_path = path[7:-1]
                if self.debug:
                    self.logger.debug(f"Extraindo o primeiro valor pela data de criação para o campo: {field_path}")
                value = converter._find_firstc_value_for_path(field_path, records)
                result[path] = [value] if value is not None else []
                continue
                
            elif path.startswith("lastc(") and path.endswith(")"):
                # Extrai o caminho do campo de lastc(...)
                field_path = path[6:-1]
                if self.debug:
                    self.logger.debug(f"Extraindo o último valor pela data de criação para o campo: {field_path}")
                value = converter._find_lastc_value_for_path(field_path, records)
                result[path] = [value] if value is not None else []
                continue
            
            # Caminho de campo regular
            values = converter._find_value_for_path(path, records)
            result[path] = values if values is not None else []

        return result

    def _find_record_by_id(self, tree_data: Dict, record_id: str) -> Optional[Dict]:
        """
        Encontra um registro específico pelo ID nos dados da árvore.

        Esta função procura recursivamente em todos os dados da árvore por um nó que possua
        o ID especificado. Útil para limitar a busca a um registro específico em consultas hierárquicas.

        Parâmetros:
            tree_data: Dados da árvore em formato JSON
            record_id: ID do registro a ser procurado

        Retorno:
            O nó do registro encontrado ou None se não encontrado
        """

        def search_nodes(nodes):
            # Função interna recursiva para procurar um nó pelo ID
            if not nodes or not isinstance(nodes, list):
                return None
                
            for node in nodes:
                # Verifica se este é o nó que está sendo procurado
                if isinstance(node, dict) and node.get('id') == record_id:
                    return node
                
                # Pesquisa em subnós
                if isinstance(node, dict) and 'data' in node and node['data']:
                    result = search_nodes(node['data'])
                    if result:
                        return result
            
            return None
        
        # Inicia a busca a partir do nível raiz
        if 'data' in tree_data:
            return search_nodes(tree_data['data'])
        return None

    def _extract_records_from_node(self, node: Dict) -> List[Dict]:
        """
        Extrai todos os registros (incluindo subnós) de um nó específico.

        Esta função é útil para extrair toda uma ramificação da árvore a partir de um nó específico,
        incluindo o próprio nó e todos os seus descendentes.

        Parâmetros:
            node: Nó a partir do qual extrair os registros

        Retorno:
            Lista de registros extraídos do nó e de seus subnós
        """
        records = [node]  # Inclui o próprio nó
        
        def extract_recursive(current_node, collected_records):
            # Função interna recursiva para extrair todos os nós de uma ramificação
            # Se o nó possui dados aninhados, adiciona-os também
            if isinstance(current_node, dict) and 'data' in current_node and current_node['data']:
                for subnode in current_node['data']:
                    if isinstance(subnode, dict):
                        collected_records.append(subnode)
                        extract_recursive(subnode, collected_records)
        
        extract_recursive(node, records)
            
        return records