
"""
Processador de Fórmulas Hierárquicas (EngineProcessor)
Propósito:
    Módulo responsável por pré-processar, enriquecer e avaliar fórmulas declaradas em uma
    estrutura de dados hierárquica de contrato/medição. Carrega a árvore de dados, extrai
    variáveis (simples e agregadas), avalia fórmulas e persiste/atualiza resultados.
Responsabilidades principais:
    - Construir e manipular a árvore de dados do contrato (engine_entities.engine_data).
    - Extrair e parsear fórmulas a partir da árvore (engine_parser) e classificar ordem de execução.
    - Enriquecer cada fórmula com valores de variáveis (escopo local e global, filtros e agregações).
    - Avaliar fórmulas (engine_eval), atualizar a árvore de dados e sincronizar resultados com API externa (SmiApi / ufrappe).
Posição na arquitetura:
    Componente de pré-processamento e execução dentro da camada de regras de negócio/engine.
    Atua entre a camada de dados (engine_entities / fonte JSON) e a camada de persistência/integração
    (update_tree, SmiApi). Orquestra parser, avaliador e atualizações de estado por medição.
Dependências críticas:
    - filters.filters_paths.tree_data_filter: busca e filtragem na árvore hierárquica.
    - engine_parser.FormulaParser: parsing de fórmulas e extração de variáveis/agregações.
    - engine_entities (get_doctypes, engine_data): construção e fornecimento da árvore de dados.
    - engine_eval.EngineEval: mecanismo de avaliação das fórmulas enriquecidas.
    - update_tree.UpdateTreeData: aplicação dos resultados de volta na árvore.
    - variable_filter.FilterVariableExtractor: extração e substituição de variáveis em expressões de filtro.
    - formula_classifier.FormulaExecutionClassifier: ordenação de execução das fórmulas.
    - engine_entities.api_smi.SmiApi (ufrappe): integração externa para persistência e relatórios.
Considerações de segurança:
    - Validação e sanitização de entradas: expressões de filtro recebem substituições de valores
    — evite avaliar/interpretar conteúdo não confiável como código. Não executar strings arbitrárias.
Exemplo de uso básico:
    # Processar todas as medições usando dados em cache
    processor.calculate_measurements(use_cached_data=True)
    # Processar uma medição específica
    processor.calculate_measurements(use_cached_data=True, measurement='BM-CW42452-003')
    # Executável (linha de comando)
    python engine_exec.py <measurement_id>
"""

import copy
import engine_entities
import engine_parser
import engine_eval
import update_tree
import logging
import engine_entities.engine_data
import engine_entities.get_doctypes
from typing import Dict, List, Any
from filters.filters_paths import tree_data_filter
from filters.variable_filter import FilterVariableExtractor
from formula_classifier import FormulaExecutionClassifier
from engine_entities.api_smi import SmiApi
from engine_entities.file_manager import FileManager
import argparse

class EngineProcessor():
    """
    A classe Engine Processor atua como um componente central para o processamento de fórmulas e cálculos de dados.
    Esta classe orquestra o carregamento de dados, a análise de fórmulas, o enriquecimento
    de fórmulas com valores de variáveis e a avaliação dessas fórmulas.
    Ela integra vários componentes, como filtragem de dados, análise de fórmulas
    e interações com APIs externas.
    """

    def __init__(self, debug: bool = False):
        self.logger = logging.getLogger(__name__)
        self.data_filter = tree_data_filter(debug=debug)
        self.file_manager = FileManager()
        self.debug = debug

    def enrich_formulas_with_values(self, extracted_formulas: List[Dict[str, Any]], tree_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Processa fórmulas extraídas e as enriquece com valores de variáveis para cada chave.

        Esta função é o núcleo do pré-processamento de fórmulas. Ela recebe as fórmulas analisadas
        e para cada combinação de fórmula e chave:
        1. Extrai referências de variáveis simples diretamente da árvore
        2. Processa funções de agregação, lidando com contextos globais e locais (específicos do chave)
        3. Combina os resultados em um formato de saída estruturado

        A função lida com dois tipos de extração de variáveis:
        - Variáveis não agregadas: Referências diretas a variáveis simples
        - Variáveis agregadas: Variáveis usadas dentro de funções de agregação (soma, média, etc.)
        com filtros opcionais e escopo global/local

        Parâmetros:
            extracted_formulas: Lista de grupos de fórmulas, cada um contendo fórmulas e chaves associados
                            (saída da função parse_formulas do engine_parser)
            tree_data: A estrutura de dados da árvore completa (carregada a partir do JSON)

        Retorno:
            Lista de dicionários contendo fórmulas processadas com seus valores de variáveis
            para cada chave. A estrutura inclui entidade, chave e dados da fórmula com valores extraídos
            dos valores das variáveis.
        """

        if self.debug:
            self.logger.debug(f"Iniciando o processamento de variáveis de fórmula para {len(extracted_formulas)} grupos de fórmulas")
        
        group_result = []

        # Contadores para monitoramento de progresso    
        count_01 = 0
        count_02 = 0
        count_03 = 0        

        # Processa cada grupo de fórmulas
        for i, formula_group in enumerate(extracted_formulas):
            count_01 += 1
            if self.debug:
                self.logger.debug(f"Processando grupo de fórmulas {i+1}/{len(extracted_formulas)}: {formula_group.get('path', 'unknown')}")
            
            id_obj_count = 0
            count_02 = 0

            # Processa cada chave do grupo
            for id_obj in formula_group.get("ids", []):
                count_02 += 1
                
                if self.debug:
                    self.logger.debug(f"Processando objeto chave {id_obj_count + 1}/{len(formula_group['ids'])} para o grupo {formula_group.get('path', 'unknown')}")
                
                # Extrai o valor do chave
                id_obj_count += 1
                id_value = id_obj["id"]                
                formula_ids = {}

                # Para cada fórmula, extrai os valores das variáveis
                formula_count = 0                
                count_03 = 0

                # Processa cada fórmula no grupo
                for formula in formula_group["formulas"]:
                    count_03 += 1
                    if self.debug:
                        self.logger.debug(f"Processando fórmula {formula_count + 1}/{len(formula_group['formulas'])} para o chave {id_value}: {formula.get('path', 'unknown')}")
                    formula_count += 1

                    # Cria nova entrada para este caminho de fórmula se não existir
                    formula_ids.setdefault(formula["path"], [])

                    # Processa variáveis não agregadas
                    # Estas são referências de variáveis diretas sem funções de agregação
                    vars = formula.get("parsed", []).get("vars", [])

                    if vars:
                        try:
                            # Aplica a transformação "first" para obter apenas a primeira correspondência para cada variável
                            node = self.data_filter.filter_tree_data(
                                tree_data,
                                [f"first({v})" for v in vars], 
                                id_value, 
                                filter_expr=None)
                            #self.log_debug(f"Found {len(node)} non-aggregated variable nodes")
                            for n in node:
                                formula_ids[formula["path"]].append({"non_aggr": n})
                        except Exception as e:
                            self.logger.exception("Erro inesperado ao processar variáveis não agregadas: %s", e)
                            raise

                    # Processa funções de agregação (soma, média, etc.)
                    aggr_funcs = formula.get("parsed", []).get("aggr", [])

                    # Processa cada função de agregação
                    for aggr in aggr_funcs:

                        vars = aggr["vars"]
                        filter_expr = aggr["filter"]
                        is_global = aggr["global"]
                        filter_aggr_expr = []

                        # Verifica se existem campos de variáveis no lado direito da expressão de filtro
                        if filter_expr:
                            # Extrai variáveis únicas da expressão de filtro
                            filter_vars = FilterVariableExtractor().extract_unique_variables(filter_expr)
                            # Se houver variáveis na expressão de filtro, precisamos processá-las
                            if filter_vars:
                                # Destaca variáveis na expressão de filtro
                                new_filter_expr = FilterVariableExtractor().highlight_variables(filter_expr)
                                try:
                                    # Aplica a transformação "first" para obter apenas a primeira correspondência para cada variável
                                    for v in filter_vars:
                                        # Seta a função para obter o primeiro valor da variável
                                        var_list = [f"first({v})"]
                                        # Busca a variável nos dados da árvore
                                        node = self.data_filter.filter_tree_data(
                                            tree_data,
                                            return_paths=var_list,
                                            record_id=id_value,
                                            lock_node=True)
                                        
                                        if node:
                                             # Extrai o valor da variável
                                            n_value = node[0]["values"][0] # type: ignore

                                            # Adiciona a variável e seu valor ao filtro de agregação
                                            filter_aggr_expr.append({v:n_value})

                                            try:
                                                # Testa se é um número para não colocar aspas
                                                float(n_value)
                                            except (ValueError, TypeError):
                                                # Se não for número, trata como string
                                                n_value = f"'{n_value}'"  
                                            # Substitui a variável destacada pelo seu valor na expressão de filtro
                                            new_filter_expr = new_filter_expr.replace(f"__{v}__", n_value)

                                except Exception as e:
                                    self.logger.exception("Erro inesperado ao processar variáveis de filtro: %s", e)
                                    raise

                                # Troca a expressão de filtro pela nova com valores substituídos
                                filter_expr = new_filter_expr
                        
                        if self.debug:
                            self.logger.debug(f"Processando função de agregação - vars: {vars}, filter: {filter_expr}, global: {is_global}")

                        # Localiza a variável nos dados da árvore
                        # Agregações globais buscam em toda a árvore
                        if is_global:
                            if self.debug:
                                self.logger.debug("Processando agregação global")
                            try:
                                if filter_expr:
                                    # Para variáveis em funções de agregação com filtro
                                    # O filtro global ignora o chave
                                    node = self.data_filter.filter_tree_data(
                                        tree_data, 
                                        vars, 
                                        filter_expr=filter_expr)
                                else:
                                    # Se sem filtro, apenas obtenha todos os valores
                                    node = self.data_filter.filter_tree_data(
                                        tree_data, 
                                        vars)
                                # Adiciona todos os valores ao formula_ids
                                for n in node:
                                    formula_ids[formula["path"]].append({"aggr": {"base": aggr["base"], "vars": n, "filter": filter_aggr_expr}})
                                # Se não houver nós encontrados
                                if not node:
                                    formula_ids[formula["path"]].append({"aggr": {"base": aggr["base"], "vars": [], "filter": filter_aggr_expr}})
                            except Exception as e:
                                self.logger.exception("Erro inesperado ao processar agregação global: %s", e)
                                raise

                        # Agregações locais buscam apenas dentro do chave atual e seus subnós
                        else:
                            if self.debug:
                                self.logger.debug("Processando agregação local (específica do chave)")
                            try:
                                if filter_expr:
                                    # Para variáveis em funções de agregação com filtro
                                    node = self.data_filter.filter_tree_data(
                                        tree_data, 
                                        vars, 
                                        id_value, 
                                        filter_expr, 
                                        lock_node=True)
                                else:
                                    # Se sem filtro, apenas obtenha todos os valores
                                    node = self.data_filter.filter_tree_data(
                                        tree_data, 
                                        vars, 
                                        id_value, 
                                        lock_node=True)
                                # Adiciona todos os valores ao formula_ids
                                for n in node:  
                                    formula_ids[formula["path"]].append({"aggr": aggr["base"], "vars": n, "filter": filter_aggr_expr})
                                # Se não houver nós encontrados
                                if not node:
                                    formula_ids[formula["path"]].append({"aggr": {"base": aggr["base"], "vars": [], "filter": filter_aggr_expr}})
                            except Exception as e:
                                self.logger.exception("Erro inesperado ao processar agregação local: %s", e)
                                raise

                # Armazenamento temporario 
                id_result = {
                    "formulas": []
                }
                for key, value in formula_ids.items():
                    id_result["formulas"].append({"formula": key, "data": copy.deepcopy(value)})

                # Adiciona os resultados deste chave ao grupo
                group_item = {
                    "entity": formula_group["path"],
                    "id": id_value,
                    "formula_data": copy.deepcopy(id_result)
                }
                group_result.append(group_item)
        if self.debug:          
            self.logger.info(f"Processamento de variáveis de fórmula concluído. Processados {len(group_result)} itens.")
        return group_result

    def calculate_measurements(self, use_cached_data: bool = False, measurement = None, clear_cache: bool = True) -> None:
        """
        Função principal para orquestrar o fluxo de trabalho de pré-processamento de fórmulas.

        Esta função serve como o ponto de entrada para o módulo de pré-processamento de fórmulas,
        orquestrando todo o fluxo de trabalho:

        1. Carregar dados da árvore a partir do arquivo JSON
        2. Extrair e avaliar fórmulas a partir dos dados da árvore
        3. Processar variáveis de fórmula para cada fórmula e chave
        4. Se necessário, salvar os resultados no arquivo JSON de saída

        Esta função trata erros em cada etapa, registrando-os adequadamente e
        impedindo processamento adicional se um erro crítico ocorrer.
        Parâmetros:
            use_cached_data: Se verdadeiro, usa dados em cache para contratos/medições
            measurement: Se fornecido, processa apenas a medição específica (chave do boletim)
        """

        # Limpa arquivos temporários antes de iniciar o processamento
        if clear_cache:
            self.file_manager.clear_temp_files()
        else:
            self.file_manager.clear_temp_engine_files()

        def find_formula_group(structure) -> list[str] | None:
            """
            Localiza o grupo de fórmulas dentro da estrutura de dados fornecida.
            Parametros:
                structure (list|dict): A estrutura de dados (lista ou dicionário) para
                procurar o grupo de fórmulas.
            Retorno:
                list|None: A lista de chaves do grupo de fórmulas se encontrada, caso contrário None
            """

            # Verifica se a estrutura é uma lista
            if isinstance(structure, list):
                for item in structure:
                    result = find_formula_group(item)
                    if result:
                        return result
            
            # Verifica se a estrutura é um dicionario
            elif isinstance(structure, dict):
                # Verifica se o dicionario tem uma chave "grupoformulas"
                if "grupoformulas" in structure:
                    return structure["grupoformulas"]

                # Se não itera no dicionario de valores
                for value in structure.values():
                    result = find_formula_group(value)
                    if result:
                        return result
            # Se nada foi encontrado, retorna None
            return None

        def find_measurement(structure, path) -> str | None:
            """
            Localiza o chave da medição dentro da estrutura de dados fornecida.
            Parametros:
                structure (list|dict): A estrutura de dados (lista ou dicionário) para
                procurar o chave da medição.
                path (str): O caminho para a medição dentro da estrutura de dados.
            Retorno:
                str|None: O chave da medição se encontrado, caso contrário None
            """ 

            # Verifica se a estrutura é uma lista
            if isinstance(structure, list):
                for item in structure:
                    result = find_measurement(item, path)
                    if result:
                        return result

            # Verifica se a estrutura é dicionario
            elif isinstance(structure, dict):
                # Verifica se o dicionario tem uma chave "grupoformulas"
                if "data" in structure:
                    if path in structure:
                        return structure["data"][0]["id"]

                # Se não, itera no dicionario de valores
                for value in structure.values():
                    result = find_measurement(value, path)
                    if result:
                        return result
            
            return None        

        print("Iniciando o motor...")

        # Início do processamento
        if self.debug:
            self.logger.debug("Iniciando o processamento de fórmulas")

        # Instancia o processador de entidades
        entities_processor = engine_entities.get_doctypes.DoctypeProcessor()
        
        # Obtem todas as fórmulas
        formulas = entities_processor.get_formula_data(using_cached_data=False)

        # Instancia a API do SMI
        ufrappe = SmiApi()

        # Obtem as chaves do contrato
        contracts_list = ufrappe.get_contracts()

        # Se uma medição específica for fornecida, filtra os contratos para essa medição
        if measurement:
            contracts = {'contracts': []}
            for c in contracts_list['contracts']:
                if c['boletimmedicao'] == measurement:
                    contracts = {'contracts': [c]}
                    break
        else:
            contracts = contracts_list

        for c in contracts['contracts']: 

            engine_results_converted = []

            print(f"Processando contrato {c['contrato']} com medição {c['boletimmedicao']}")

            # Atualiza registros de cidades e rotinas associadas ao boletim de medição
            print("Atualizando cidades e rotinas associadas...")
            ufrappe.update_cities(c['boletimmedicao'])
            # Recarrega os itens do boletim de medição
            print("Recarregando itens do boletim de medição...")
            ufrappe.create_measurement_items(c['boletimmedicao'])
            # Atualiza os registros de medição do boletim de medição
            print("Atualizando registros de medição...")
            ufrappe.update_measurement_records(c['boletimmedicao']) 
            # Atualiza as produtividades horárias do boletim de medição
            print("Atualizando produtividades horárias...")
            ufrappe.update_hours_measurement_record(c['boletimmedicao'])
            # Atualiza os valores de produtividade do boletim de medição
            print("Atualizando valores de produtividade...")
            ufrappe.update_measurement_productivity(c['boletimmedicao'])
            # Aplica condições de performance e fatores aos itens do boletim de medição
            print("Aplicando condições de performance e fatores...")
            ufrappe.apply_measurement_performance_conditions(c['boletimmedicao'])
            # Aplica fatores aos itens do boletim de medição
            print("Aplicando fatores aos itens do boletim de medição...")
            ufrappe.apply_measurement_items_factor(c['boletimmedicao'])
            # Totaliza os valores do boletim de medição
            print("Totalizando valores do boletim de medição...")
            ufrappe.sumarize_measurement(c['boletimmedicao'])

            print(f"Processando contrato {c['contrato']} com medição {c['boletimmedicao']}")

            if self.debug:
                self.logger.debug(f"Processando contrato {c['contrato']} com medição {c['boletimmedicao']}")

            # Verifica se deve usar dados em cache
            contract_data = None
            if use_cached_data:

                print(f"Usando dados em cache para o contrato {c['contrato']}")

                if self.debug:
                    self.logger.debug(f"Usando dados em cache para o contrato {c['contrato']}")

                # Carrega dados do contrato do cache
                f = f"contract_data_{c['contrato']}.json"
                if self.file_manager.check_file_exists(f):
                    contract_data = self.file_manager.load_json(f)
                else:
                    if self.debug:
                        self.logger.warning(f"Arquivo de cache {f} não encontrado.")    
            
            if not use_cached_data or contract_data is None:

                print(f"Buscando dados do contrato {c['contrato']} via API")

                # Obtem os dados do contrato via API
                try:
                    contract_data = entities_processor.get_data(c['contrato'], [{"parameter": "#MEASUREMENT#", "value": c['boletimmedicao']}])
                except Exception as e:
                    print(f"Erro ao buscar dados do contrato {c['contrato']} via API: {e}")
                    self.logger.exception("Erro ao buscar dados do contrato %s via API: %s", c['contrato'], e)

            find_contract = [item for item in contract_data['data'] if 'Contract' in item]

            # Verifica se encontrou dados do contrato
            if not find_contract:

                print(f"Nenhum dado de contrato encontrado para {c['contrato']}. Ignorando.")

                self.logger.error(f"Nenhum dado de contrato encontrado para {c['contrato']}. Ignorando.")
                continue

            # Extrai os chaves das fórmulas do contrato
            contract_formula_id = None

            # Tenta extrair os chaves das fórmulas do contrato
            try:
                contract_formula_id = find_formula_group(find_contract[0])
            except Exception as e:
                print(f"Erro inesperado ao extrair chaves das fórmulas do contrato {c.get('contrato')}: {e}")   
                self.logger.exception("Erro inesperado ao extrair chaves das fórmulas do contrato %s: %s", c.get('contrato'), e)
                continue

            # Verifica se encontrou o grupo de fórmulas
            if not contract_formula_id:
                print(f"Sem grupo de fórmulas encontrado para o contrato {c['contrato']}. Ignorando.")
                self.logger.error(f"Sem grupo de fórmulas encontrado para o contrato {c['contrato']}. Ignorando.")
                continue   

            # Filtra as fórmulas relevantes para o contrato
            contract_formula = [f for f in formulas if f.get("name") in contract_formula_id]  

            # Constroi a árvore de dados do contrato (valida contract_data antes de acessar .get)
            print("Construindo a árvore de dados do contrato...")
            # data_builder = engine_entities.engine_data.EngineDataBuilder(
            #     contract_data['hierarchical'], 
            #     contract_formula, 
            #     contract_data['data'], 
            #     "data",
            #     compact_mode=True
            # )
            data_builder = None
            data_builder = engine_entities.engine_data.EngineDataBuilder(
                contract_data['hierarchical'], 
                contract_formula, 
                contract_data['data'], 
                "data"
            )
            
            # Cria a árvore de dados do contrato
            engine_data_tree = {}
            engine_data_tree = data_builder.build()

            # Salva a árvore de dados do contrato para inspeção
            self.file_manager.save_json(f"contract_data_{c['contrato']}.json", engine_data_tree)

            # Parseia as fórmulas
            print("Parseando fórmulas...")
            parser = engine_parser.FormulaParser(debug=self.debug)
            extract_formulas = parser.parse_formulas(engine_data_tree)

            # Classifica a ordem de execução das fórmulas
            classifier = FormulaExecutionClassifier(extract_formulas)
            classifier_groups = classifier.get_execution_order()

            # Executa as fórmulas por grupo
            for g in classifier_groups:

                print(f"Processando grupo de fórmulas {g}...")

                group_formulas = {}

                # Localiza as fórmulas deste grupo
                for formula_path in extract_formulas:
                    for formula in formula_path["formulas"]:
                        if formula["path"] in classifier_groups[g]:
                            fp = formula_path["path"]
                            if fp not in group_formulas:
                                group_formulas[fp] = {
                                    'path': fp,
                                    'formulas': [],
                                    'ids': formula_path["ids"]
                                }
                            group_formulas[fp]['formulas'].append(formula)

                # Prepara a estrutura para processamento
                group_extract_formulas = []
                for gp, gv in group_formulas.items():
                    group_extract_formulas.append({
                        "path": gp,
                        "formulas": gv["formulas"],
                        "ids": gv["ids"]
                    })

                # Enriquecer as fórmulas com valores de variáveis
                enrich_formulas = self.enrich_formulas_with_values(group_extract_formulas, engine_data_tree)

                # Salva os dados enriquecidos em JSON para inspeção
                if self.debug:
                    self.file_manager.save_json(f"enriched_data_{c['contrato']}-{g}.json", enrich_formulas)

                # Instancia o motor
                engine = engine_eval.EngineEval(debug=self.debug)

                if self.debug:
                    self.logger.debug("Iniciando a avaliação das fórmulas")

                # Avalia as fórmulas enriquecidas
                engine_results = engine.eval_formula(enrich_formulas, group_extract_formulas, engine_data_tree)

                # Conta sucessos e erros para relatório
                success_count = sum(1 for entity in engine_results for fr in entity["results"] if fr["status"] == "success")
                error_count = sum(1 for entity in engine_results for fr in entity["results"] if fr["status"] == "error")

                if self.debug:
                    self.logger.debug(f"Avaliação das fórmulas concluída. Com sucesso: {success_count}, Erros: {error_count}")

                if error_count > 0:
                    str_errors = []
                    for r in engine_results:
                        for error in r["results"]:
                            if error["status"] == "error":
                                str_erro = f"Erro na fórmula: {error['path']}, Id: {r['id']}, Erro: {error['error']}"
                                str_errors.append(str_erro)
                                if self.debug:
                                    self.logger.error(str_erro)

                        if len(str_errors)>0:
                            ufrappe.write_errors(c['boletimmedicao'], str_errors)

                # Converte os valores de tipos numpy para tipos nativos do Python antes de salvar
                _engine_results = engine.convert_numpy_types(engine_results)
                engine_results_converted.extend(_engine_results)

                # Salva os resultados da avaliação em JSON para inspeção
                if self.debug:
                    self.file_manager.save_json(f"engine_result_g{g}_{c['contrato']}.json", _engine_results)

                # Percorre as fórmulas do grupo para atualizar a árvore de dados
                print("Atualizando a árvore de dados com os resultados das fórmulas...")
                for to_update_formula in group_extract_formulas:

                    # Atualiza a árvore de dados com os resultados da fórmula
                    utree = update_tree.UpdateTreeData(
                        engine_data_tree, 
                        to_update_formula, 
                        _engine_results
                    )
                    engine_data_tree = utree.update_tree()

            # Percorre todas as fórmulas para atualizar os resultados finais
            for to_update_formula in extract_formulas:
                # Envia os resultados finais para o SMI
                ufrappe.update(engine_results_converted, to_update_formula)

            # Sumariza o boletim de medição após todas as atualizações
            print("Sumarizando o boletim de medição...")
            ufrappe.sumarize_measurement(c['boletimmedicao'])
            # Atualiza os registros de REIDI dos pedidos SAP associados ao boletim de medição
            print("Atualizando registros de REIDI dos pedidos SAP...")
            ufrappe.update_reidi_measurement_record(c['boletimmedicao'])
            # Cria ou atualiza os saldos dos itens de medição
            print("Atualizando saldos dos itens de medição...")
            ufrappe.create_measurement_items_balance(c['boletimmedicao'])
            # Cria ou atualiza os registros dos pedidos SAP associados ao boletim de medição
            print("Atualizando registros dos pedidos SAP associados...")    
            ufrappe.create_measurement_sap_orders_records(c['boletimmedicao'])

            if self.debug:
                self.logger.debug(f"Boletim de medição: {c['boletimmedicao']}")

        # Após processar todos os contratos, atualiza os saldos dos pedidos SAP
        print("FIM: Atualizando saldos dos pedidos SAP...")
        ufrappe.update_sap_orders_balance()

if __name__ == "__main__":
    import sys
    parser = argparse.ArgumentParser(description='Executar o processador de fórmulas.')

    parser.add_argument('--measurement',
                        type=str,
                        help='Código do boletim de medição para processar (opcional).')
    
    parser.add_argument('--no-clear-cache',
                        action='store_false',
                        help='Não limpa o cache de dados globais antes de processar (opcional).')    

    args = parser.parse_args()

    if args.measurement:
        measurement = args.measurement
    else:
        measurement = None

    measurement='BM-CW31501-001'

    no_clear_cache = args.no_clear_cache

    # measurement="BM-CW082025-001"
    # no_clear_cache = True

    processor = EngineProcessor(debug=True)
    try:
        if measurement:
            processor.logger.debug(f"Processando medição específica: {measurement}")
            processor.calculate_measurements(use_cached_data=True, measurement=measurement, clear_cache=no_clear_cache)
        else:
            processor.logger.debug("Processando todas as medições")

            # Instancia a API do SMI
            ufrappe = SmiApi()

            # Obtem as chaves do contrato
            contracts_list = ufrappe.get_contracts()
            no_clear_cache = args.no_clear_cache

            for c in contracts_list['contracts']:

                processor.logger.info(f"Processando contrato {c['contrato']} com medição {c['boletimmedicao']}")
                processor.calculate_measurements(use_cached_data=True, measurement=c['boletimmedicao'], clear_cache=args.no_clear_cache)

                # Mantem o cache a partir do segundo contrato
                if not no_clear_cache:
                    no_clear_cache = True
            

    except Exception as e:
        if 'processor' in locals():
            processor.logger.exception("Erro inesperado durante o processamento da fórmula: %s", e)
        else:
            logger = logging.getLogger(__name__)
            logger.exception("Erro inesperado durante o processamento da fórmula: %s", e)
        raise
    finally:
        processor.logger.info("Processamento da fórmula concluído.")