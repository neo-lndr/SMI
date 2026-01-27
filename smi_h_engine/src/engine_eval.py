"""
EngineEval — Avaliador de Fórmulas Seguro com suporte a NumPy
Propósito:
    Fornecer um mecanismo centralizado para criação de ambientes de avaliação
    seguros (asteval) e execução de fórmulas dinâmicas, com suporte a operações
    numéricas/estatísticas via NumPy e gestão de variáveis/aggregações.
Responsabilidades principais:
    - Criar e configurar interpreters seguros (asteval) com um conjunto limitado
      de símbolos e funções permitidas.
    - Converter tipos NumPy para tipos nativos Python para compatibilidade (ex.: JSON).
    - Substituir referências codificadas (ex.: e00002v, e00002v_4) por variáveis
      concretas e popular a tabela de símbolos antes da avaliação.
    - Avaliar coleções de fórmulas por entidade, lidar com agregações, erros e
      produzir um relatório de resultados por entidade.
Posição na arquitetura:
    - Camada de execução/negócio responsável por avaliar expressões e regras
      calculadas dinamicamente a partir de uma árvore de dados (data_tree).
Dependências críticas:
    - asteval: fornece o interpretador seguro para avaliar expressões Python.
    - numpy: para funções matemáticas/estatísticas e arrays numéricos.
    - logger/local modules (log, logging, update_tree): para
      logging, estrutura de dados e integração com o resto do sistema.
Considerações de segurança:
    - O interpretador é inicializado com um conjunto restrito de símbolos e
      nós AST bloqueados (ex.: Import, Attribute, Exec, Assign em modo readonly)
      para reduzir risco de execução de código arbitrário.
    - builtins_readonly é ativado para evitar sobrescrita de funções críticas.
Exemplo de uso básico:
    engine = EngineEval()
    formulas = [...]          # coleção de definições de fórmula (conforme esperado)
    entities_eval = [...]     # lista de entidades com formula_data e dados
    data_tree = {...}         # árvore de dados com 'referencia' e demais nós
    results = engine.eval_formula(entities_eval, formulas, data_tree)
    # results -> lista com resultados por entidade, contendo status e valores/erros.
"""

import numpy as np
import re
import logging
from asteval import Interpreter
from config.config import get_config

class EngineEval():
    """
    Classe responsável pela avaliação de fórmulas com asteval.

    Fornece métodos para criar um interpretador, avaliar fórmulas
    e lidar com substituições de variáveis de maneira segura.
    """

    def __init__(self, debug: bool = False):
        try:
            self.debug = debug
            self.logger = logging.getLogger(__name__)
            if self.debug:
                self.logger.setLevel(logging.DEBUG)
                self.logger.debug("EngineEval initialized")
        except Exception as e:
            self.logger.exception("Erro inesperado na inicialização: %s", e)
            raise

    def convert_numpy_types(self, obj):
        """
        Converte tipos de dados do NumPy para tipos nativos do Python para serialização JSON.

        Esta função converte recursivamente inteiros, floats e arrays do NumPy
        para seus equivalentes em Python para garantir compatibilidade com a
        serialização JSON.

        Parâmetros:
            obj: O objeto a ser convertido (pode ser dict, list, tipo numpy, etc.)

        Retorno:
            O objeto convertido com todos os tipos numpy substituídos por tipos nativos do Python
        """
        try:
            if isinstance(obj, np.integer):
                return int(obj)
            elif isinstance(obj, np.floating):
                return float(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, dict):
                return {key: self.convert_numpy_types(value) for key, value in obj.items()}
            elif isinstance(obj, list):
                return [self.convert_numpy_types(item) for item in obj]
            return obj
        except Exception as e:
            self.logger.exception("Erro inesperado na conversão de tipos numpy: %s", e)
            return obj

    def create_interpreter(self, use_numpy=True, max_time=5.0, readonly=False):
        """
        Cria um interpretador asteval com suporte opcional ao NumPy e recursos de segurança.

        Esta função inicializa um avaliador de expressões Python restrito com
        funções seguras cuidadosamente selecionadas. Ela impede o acesso a operações
        potencialmente perigosas, enquanto fornece uma rica funcionalidade matemática.

        Parâmetros:
            use_numpy (bool): Indica se as funções do NumPy devem ser incluídas no interpretador. O padrão é True.
            max_time (float): Tempo máximo de execução em segundos para evitar loops infinitos. O padrão é 5.0.
            readonly (bool): Indica se deve ser executado em modo somente leitura (bloqueia operações de atribuição para maior segurança). O padrão é False.

        Retorno:
            Interpreter: Instância do interpretador asteval configurada e pronta para avaliação segura de fórmulas
        """
        try:
            # Inicia com um conjunto mínimo de builtins seguros
            numpy_functions = get_config().numpy_functions

            # Funções que permaneceriam inalteradas:
            default_functions = get_config().default_functions

            # Funções AST bloqueadas
            blocked_nodes = list(get_config().blocked_ast)

            # Combina os símbolos permitidos
            all_symbols = {}
            all_symbols.update(numpy_functions)
            all_symbols.update(default_functions)

            # Se estiver no modo somente leitura, bloqueia mais nós para maior segurança
            if readonly:
                blocked_nodes.extend(['Assign', 'AugAssign', 'AnnAssign'])
                if self.debug:
                    self.logger.debug("Adicionado nós de atribuição à lista bloqueada no modo somente leitura")

            # Cria o interpretador com nossa configuração
            interpreter = Interpreter(
                usersyms=all_symbols,
                use_numpy=use_numpy,
                readonly=readonly,
                max_time=max_time,
                no_if=False,  # Permitir expressões if-else para lógica de fórmula
                builtins_readonly=True,  # Impedir a sobrescrição de builtins
                blocked_nodes=blocked_nodes
            )

            if self.debug:
                self.logger.debug(f"Criado interpretador asteval: numpy={use_numpy}, max_time={max_time}s, readonly={readonly}, {len(all_symbols)} símbolos disponíveis")

            return interpreter
        except Exception as e:
            self.logger.exception("Erro inesperado ao criar interpretador: %s", e)
            return None

    def evaluate_formula(self, formula, variables=None, use_numpy=True, max_time=5.0):
        """
        Valida a fórmula usando asteval com as variáveis fornecidas.

        Esta função cria um ambiente de avaliação seguro, o preenche com
        as variáveis fornecidas e avalia a fórmula dada com um tratamento
        abrangente de erros e registro.

        Parâmetros:
            formula (str): A fórmula a ser avaliada
            variables (dict): Dicionário de variáveis a serem usadas na avaliação
            use_numpy (bool): Indica se as funções do NumPy devem ser incluídas
            max_time (float): Tempo máximo de execução em segundos

        Retorno:
            Any: Resultado da avaliação da fórmula ou None se a avaliação falhar
        """

        # Cria o interpretador
        interpreter = self.create_interpreter(use_numpy=use_numpy, max_time=max_time)

        # Adiciona Add variables to interpreter's symbol table
        if variables:
            for name, value in variables.items():
                interpreter.symtable[name] = value

        # Avalia a fórmula
        try:
            if self.debug:
                self.logger.debug(f"Iniciando avaliação da fórmula: '{formula}'")
            result = interpreter.eval(formula)
            if self.debug:
                self.logger.debug("Avaliação da fórmula concluída")

            # Verifica se há erros no interpretador
            if len(interpreter.error) > 0:
                error_msg = interpreter.error[0].get_error()
                self.logger.error("Erro ao avaliar a fórmula '%s': %s", formula, error_msg)
                return None

            if self.debug:
                # Registra o resultado detalhadamente
                self.logger.debug(f"Resultado da avaliação: {result}")
                if isinstance(result, (list, np.ndarray)) and len(str(result)) > 100:
                    self.logger.debug(f"Tipo de resultado: {type(result).__name__}, forma/comprimento: {getattr(result, 'shape', len(result) if hasattr(result, '__len__') else 'N/A')}")
                else:
                    self.logger.debug(f"Resultado: {result} (tipo: {type(result).__name__})")

            return result
        
        except Exception as e:
            self.logger.exception("Erro inesperado ao avaliar fórmula '%s': %s", formula, e)
            return None

    def find_vars_position(self, formula_str):
        """
        Localiza as posições dos padrões de variáveis em uma string de fórmula.

        Identifica todas as ocorrências de variáveis que correspondem ao padrão 'eXXXXXv'
        onde XXXXX é um número de 5 dígitos.

        Parâmetros:
            formula_str (str): A string da fórmula a ser pesquisada

        Retorno:
            list: Lista de tuplas (start_index, end_index, matched_text)
        """
        try:
            if self.debug:
                self.logger.debug(f"Localizando posições de variáveis na fórmula: '{formula_str}'")

            # Usa regex para verficar a posição das variáveis
            pattern = r'e\d{5}v'
            matches = re.finditer(pattern, formula_str)

            # Cria lista com as ocorrências encontradas
            positions = [(match.start(), match.end(), match.group()) for match in matches]

            if self.debug:
                self.logger.debug(f"Encontradas {len(positions)} variáveis na fórmula")

            return positions
        except Exception as e:
            self.logger.exception("Erro inesperado ao localizar posições de variáveis: %s", e)
            return []

    def get_formula(self, formulas, path):
        """
        Localiza uma fórmula pelo seu caminho na coleção de fórmulas.

        Parâmetros:
            formulas (list): Lista de coleções de fórmulas
            path (str): Identificador de caminho da fórmula a ser encontrada

        Retorno:
            dict: O objeto da fórmula se encontrado, None caso contrário
        """
        try:
            # Percorre as coleções de fórmulas para encontrar a fórmula com o caminho correspondente
            for f0 in formulas:
                for f1 in f0["formulas"]:
                    # Verifica se o caminho corresponde
                    if f1["path"] == path:
                        if self.debug:
                            self.logger.debug(f"Encontrada: {f1['path']}")
                        return f1

            if self.debug:
                self.logger.warning(f"Fórmula com caminho {path} não encontrada")

            return None
        except Exception as e:
            self.logger.exception("Erro inesperado ao buscar fórmula: %s", e)
            return None

    def get_aggr(self, formula, base):
        """
        Obtém informações de agregação para uma variável base a partir de uma fórmula.

        Parâmetros:
            formula (dict): O objeto da fórmula
            base (str): Identificador base da agregação

        Retorno:
            dict: Informações de agregação se encontradas, None caso contrário
        """
        try:
            # Verifica se a fórmula tem dados de agregação
            if "parsed" not in formula or "aggr" not in formula["parsed"]:
                if self.debug:
                    self.logger.debug("Nenhuma agregação analisada encontrada na fórmula")
                return None

            for aggr in formula["parsed"]["aggr"]:
                if aggr["base"] == base:
                    if self.debug:
                        self.logger.debug(f"Encontrada agregação: {base}")
                    return aggr

            if self.debug:
                self.logger.warning(f"Agregação com base {base} não encontrada na fórmula")
            return None
        except Exception as e:
            self.logger.exception("Erro inesperado ao buscar agregação: %s", e)
            return None

    def simple_reference_substitution(self, formula, references):
        """
        Substitui referências (por exemplo, e00002v, e00002v_4) pelos seus valores correspondentes na fórmula.

        Parâmetros:
            formula (str): A fórmula em Python contendo referências codificadas
            references (dict): Dicionário com referências e seus valores

        Retorno:
            str: A fórmula com referências substituídas
        """
        try:
            # Encontra todas as referências na fórmula (como e00002v ou e00002v_4)
            pattern = re.compile(r'e\d{5}v(?:_\d+)?')
            found_references = pattern.findall(formula)

            # Para cada referência encontrada, substitui pelo valor correspondente
            processed_str = formula

            for ref in found_references:
                # Extrai a chave base (por exemplo, e00002v de e00002v_4)
                base_key = ref.split('_')[0]

                # Verifica se a chave existe no dicionário de referências
                if base_key in references:
                    # Substitui a referência pelo valor correspondente
                    # Aqui vamos substituir por um marcador temporário para evitar afetar substituições subsequentes
                    value = str(references[base_key])
                    processed_str = re.sub(rf'\b{re.escape(ref)}\b', value, processed_str)

            return processed_str
        except Exception as e:
            self.logger.exception("Erro inesperado na substituição de referências: %s", e)
            return formula        

    def eval_formula(self, entities_eval, formulas, data_tree):
        """
        Valida e avalia fórmulas para múltiplas entidades com seus dados associados.

        Esta função processa uma coleção de entidades, avalia suas fórmulas
        substituindo variáveis por valores e retorna os resultados da avaliação.
        Ela lida tanto com variáveis regulares quanto com funções de agregação.

        Parâmetros:
            entities_eval (list): Lista de entidades com dados de fórmula
            formulas (list): Coleção de definições de fórmula

        Retorno:
            list: Resultados da avaliação das fórmulas para cada entidade
        """
        if self.debug:
            self.logger.debug("Iniciando avaliação em lote de fórmulas")
        
        results = []
        counter = 0

        # Obtém as referências da árvore de dados
        references = data_tree.get("referencia", {})[0]

        for entity_idx, entity in enumerate(entities_eval):

            if self.debug:
                self.logger.debug(f"Avaliando entidade: {entity.get('id', f'entity_{entity_idx}')}")

            # Resultados para a entidade atual
            entity_results = {"id": entity.get("id", f"entity_{entity_idx}"), "results": []}
            
            # Verifica se a entidade tem dados de fórmula
            if "formula_data" not in entity or "formulas" not in entity["formula_data"]:
                if self.debug:
                    self.logger.warning(f"Entidade {entity_idx} não possui dados de fórmula - Pulando")
                continue
            
            # Avalia cada fórmula para a entidade
            for id_eval in entity["formula_data"]["formulas"]:

                if self.debug:
                    self.logger.debug(f"Avaliando fórmula: {id_eval['formula']}")

                # Cria um novo interpretador para cada avaliação de fórmula
                aeval = self.create_interpreter(use_numpy=True, max_time=5.0, readonly=False)

                # Carrega a árvore de dados na tabela de símbolos do interpretador
                aeval.symtable["data_tree"] = data_tree

                # Obtém a fórmula
                formula = self.get_formula(formulas, id_eval["formula"])
                # Verifica se a fórmula foi encontrada
                if not formula:
                    if self.debug:
                        self.logger.debug(f"Fórmula não encontrada: {id_eval['formula']}")
                    continue
                    
                # Prepara a string da fórmula para avaliação
                formula_str = formula["value"].replace("return ", "")
                formula_str += "\n"  # Certifica-se de que a fórmula termina com uma nova linha
                if self.debug:
                    self.logger.debug(f"Id:{entity.get('id')}")

                # Rastreia as substituições de variáveis para depuração
                var_replacements = {}

                # Primeiro processa as funções de agregação
                if "data" not in id_eval:
                    if self.debug:
                        self.logger.debug(f"Sem dados para a fórmula: {id_eval['formula']}")
                    continue

                # Processa as variáveis de agregação primeiro
                for i, value in enumerate(id_eval["data"]):
                    if "aggr" in value:
                        # Obtém a função de agregação
                        aggr = self.get_aggr(formula, value["aggr"]["base"])
                        if not aggr:
                            if self.debug:
                                self.logger.warning(f"Função de agregação não encontrada para a base: {value['aggr']['base']}")
                            continue
                        # Processa cada variável na agregação
                        for v in aggr["vars"]:
                            # Adiciona um sufixo numérico para evitar colisões de nomes
                            counter += 1
                            new_var = f"{v}_{counter}"
                            old_formula = formula_str
                            formula_str = formula_str.replace(aggr["base"], aggr["eval"].replace(v, new_var))
                            # Registra a substituição se ocorreu
                            if old_formula != formula_str:
                                if self.debug:
                                    self.logger.debug(f"Substituição: {aggr['base']} → {new_var}")
                                var_replacements[aggr["base"]] = aggr["eval"].replace(v, new_var)
                            # Adiciona a variável ao interpretador
                            aggregation_var = value["aggr"]["vars"]
                            if "values" in aggregation_var and len(aggregation_var["values"]) > 0:
                                if aggregation_var["values"][0] is None:
                                    if self.debug:
                                        self.logger.debug("Nenhum valor None, usando 0.0")
                                    # Adiciona a variável como um array numpy com valor padrão
                                    aeval.symtable[new_var] = np.array([0.0])
                                else:
                                    # Adiciona a variável como um array numpy
                                    aeval.symtable[new_var] = np.array(aggregation_var["values"])
                                if self.debug:
                                    self.logger.debug(f"Adicionado: {new_var} = array[{len(aggregation_var['values'])} valores]")
                                    self.logger.debug(f"Valores: {aggregation_var['values']}")
                            else:
                                if self.debug:
                                    self.logger.debug("Nenhum valor, usando: 0.0")
                                # Adiciona a variável como um array numpy vazio
                                aeval.symtable[new_var] = np.array([0.0])

                # Processa outras variáveis (não agregadas)
                for i, value in enumerate(id_eval["data"]):
                    # Processa apenas variáveis não agregadas
                    if "non_aggr" in value:
                        if self.debug:
                            self.logger.debug(f"Id:{entity.get('id')}")
                        # Adiciona um sufixo numérico para evitar colisões de nomes
                        counter += 1
                        pattern = r'e\d{5}v'
                        matches = re.search(pattern, value["non_aggr"]["path"])
                        # Verifica se houve correspondência
                        if not matches:
                            if self.debug:
                                self.logger.debug(f"Nenhum padrão de variável encontrado em: {value['non_aggr']['path']}")
                            continue
                        # Extrai a variável correspondente
                        var = matches.group()
                        new_var = f"{var}_{counter}"
                        old_formula = formula_str
                        formula_str = formula_str.replace(var, new_var)
                        # Registra a substituição se ocorreu
                        if old_formula != formula_str:
                            var_replacements[var] = new_var
                        # Adiciona a variável ao interpretador
                        if "values" in value["non_aggr"]:
                            if value["non_aggr"]["values"][0] is None:
                                if self.debug:
                                    self.logger.debug("Nenhum valor None, usando 0.0")
                                # Adiciona a variável com valor padrão
                                aeval.symtable[new_var] =  0.0
                            else:
                                # Adiciona a variável com o valor fornecido
                                aeval.symtable[new_var] = value["non_aggr"]["values"][0]
                            if self.debug:
                                self.logger.debug(f"Adicionado: {new_var}")
                                self.logger.debug(f"Valor: {value['non_aggr']['values'][0]}")
                        else:
                            if self.debug:
                                self.logger.debug("Nenhum valor, usando: 0.0")
                            # Adiciona a variável com valor padrão
                            aeval.symtable[new_var] = 0.0  # Empty array

                # Executa a avaliação da fórmula
                try:
                    if self.debug:
                        self.logger.debug(
                            "Executando fórmula:\nSubstituições de variáveis:%s\n"
                            "Referências keys: %s\nReferências: %s\nFórmula original: %s\nFórmula processada: %s",
                            var_replacements, list(references.keys()), references,
                            id_eval['formula'], formula_str
                        )

                    # Regex sem atribuição
                    result = aeval(formula_str)
                    
                    # Verifica se houve erro na avaliação
                    if result is None or (hasattr(aeval, 'error') and aeval.error):
                        if hasattr(aeval, 'error') and aeval.error:
                            error_msg = str(aeval.error[0])
                        else:
                            error_msg = "Unknown error"
                        self.logger.error(
                            "Erro ao avaliar a fórmula '%s': %s",
                            id_eval['formula'], error_msg
                        )

                        # Registra o erro na lista de resultados
                        entity_results["results"].append({
                            "path":  self.simple_reference_substitution(id_eval["formula"], references),
                            "status": "error",
                            "error": error_msg
                        })
                        continue
                    
                    if self.debug:
                        # Amostra limitada para evitar logs enormes
                        sample = result.flatten()[:5].tolist() if result.size else []
                        truncated_note = "" if result.size <= 5 else " (truncado)"
                        msg = (
                            f"Sucesso - Formula: {id_eval['formula']}\n"
                            f"Tipo de resultado: numpy.ndarray\n"
                            f"Forma: {result.shape}\n"
                            f"Valores de amostra (primeiros 5): {sample}{truncated_note}\n"
                        )

                        self.logger.debug(msg)
                    else:
                        self.logger.debug(f"Sucesso - Formula: {id_eval['formula']}\nResultado: {result}")

                    # Converte tipos numpy para tipos nativos Python
                    entity_results["results"].append({
                        "path": id_eval["formula"],
                        "status": "success",
                        "result": result.tolist() if isinstance(result, np.ndarray) else result,
                    })
                    
                except Exception as e:
                    self.logger.exception(
                        "Erro inesperado na avaliação - Formula: %s, Expressão: %s, Erro: %s",
                        id_eval['formula'],
                        formula_str,
                        e
                    )

                    # Registra o erro na lista de resultados
                    entity_results["results"].append({
                        "path": self.simple_reference_substitution(id_eval["formula"], references),
                        "status": "error",
                        "error": str(e)
                    })
            
            results.append(entity_results)

        if self.debug:
            self.logger.debug(f"Processamento concluído: {len(results)}")

        return results
