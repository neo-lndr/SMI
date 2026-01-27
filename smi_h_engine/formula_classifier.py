"""
Classificador de grupos de execução de fórmulas
Propósito:
    Fornecer uma forma determinística de agrupar fórmulas calculadas em níveis de
    execução (grupos 1..N) com base nas dependências diretas internas entre elas,
    facilitando a ordenação topológica por camadas antes da avaliação.
Responsabilidades principais:
    - Extrair caminhos de fórmulas e dependências DAG a partir da estrutura JSON de entrada.
    - Construir um grafo de dependências considerando apenas fórmulas calculadas internamente.
    - Classificar fórmulas em grupos de execução por níveis (ordenamento topológico por camadas).
    - Validar ciclos (dependências circulares) e expor um plano de execução legível.
Posição na arquitetura:
    Componente de pré-processamento/coordenação em pipelines de cálculo de fórmulas.
    Deve ser usado antes do motor de avaliação/executor para definir a ordem segura
    e eficiente de execução das fórmulas em sistemas de transformação de dados ou ETL.
Dependências críticas:
    - Entrada JSON com estrutura esperada: lista de grupos contendo lista 'formulas',
      cada fórmula com 'path' e opcional 'parsed' contendo 'dag_paths'.
    - Bibliotecas padrão do Python (json, typing, collections) — nenhuma dependência externa.
Considerações de segurança:
    - Evitar execução de código contido em campos de fórmula; esta classe só analisa caminhos/strings.
    - Ao carregar arquivos, evitar caminhos arbitrários; restrinja permissões e locais de leitura conforme necessário.
Exemplo de uso básico:
    # carregar dados (assumindo estrutura válida)
    with open("formulas.json", "r", encoding="utf-8") as f:
        formulas_data = load(f)
        # tratar ou logar erros de dependência
        print("Erros:", errors)
    execution_groups = classifier.classify_execution_groups()
    # obter mapeamento por grupos: {1: [path1, ...], 2: [...], ...}
    plan_por_grupo = classifier.get_execution_order()
"""

import logging
from typing import Dict, List, Set
from collections import defaultdict

logger = logging.getLogger(__name__)

class FormulaExecutionClassifier:
    """
    Classifica fórmulas em grupos de execução com base em dependências DAG.
    
    Os grupos são determinados dinamicamente com base na profundidade das dependências:
    - Grupo 1: Fórmulas sem dependências internas (dependem somente de entradas externas)
    - Grupo 2: Fórmulas que dependem apenas do Grupo 1
    - Grupo 3: Fórmulas que dependem dos Grupos 1-2
    - Grupo N: Fórmulas que dependem dos grupos anteriores
    """
    
    def __init__(self, formulas_data: List[Dict]):
        try:
            # Inicializa com os dados JSON das fórmulas
            self.formulas_data = formulas_data
            self.formula_paths: Set[str] = set()
            self.dependencies: Dict[str, Set[str]] = defaultdict(set)
            self.execution_groups: Dict[str, int] = {}

            self._extract_formulas_and_dependencies()
        except Exception as e:
            logger.exception("Erro inesperado na inicialização: %s", e)
            raise

    def _extract_formulas_and_dependencies(self) -> None:
        """
        Extrai todas as fórmulas e suas dependências do JSON.
        """
        try:
            # Extrai todos os caminhos das fórmulas
            for group in self.formulas_data:
                if 'formulas' in group:
                    for formula in group['formulas']:
                        formula_path = formula['path']
                        self.formula_paths.add(formula_path)
                        # Extrai as dependências do DAG
                        if 'parsed' in formula and 'dag_paths' in formula['parsed']:
                            for dep_path in formula['parsed']['dag_paths']:
                                # Considere apenas dependências internas (calculadas por outras fórmulas)
                                if dep_path in self.formula_paths or self._is_calculated_formula(dep_path):
                                    self.dependencies[formula_path].add(dep_path)
        except Exception as e:
            logger.exception("Erro inesperado ao extrair fórmulas e dependências: %s", e)
            raise
    
    def _is_calculated_formula(self, path: str) -> bool:
        """
        Verifica se um caminho é calculado por alguma fórmula.
        Parâmetros:
            path (str): O caminho da fórmula a ser verificado.

        Retorno:
            bool: Verdadeiro se o caminho for calculado por uma fórmula, falso caso contrário.
        """
        try:
            for group in self.formulas_data:
                if 'formulas' in group:
                    for formula in group['formulas']:
                        if formula['path'] == path:
                            return True
            return False
        except Exception as e:
            logger.exception("Erro inesperado ao verificar fórmula calculada: %s", e)
            return False
    
    def _build_dependency_graph(self):
        """
        Reconstrói o grafo de dependências considerando apenas fórmulas calculadas.
        """
        try:
            # Limpa dependências anteriores
            self.dependencies.clear()

            # Reconstrói o grafo de dependências
            for group in self.formulas_data:
                if 'formulas' in group:
                    for formula in group['formulas']:
                        formula_path = formula['path']
                        # Garante que a fórmula esteja na lista de fórmulas conhecidas
                        if 'parsed' in formula and 'dag_paths' in formula['parsed']:
                            for dep_path in formula['parsed']['dag_paths']:
                                # Adicione apenas se a dependência for uma fórmula calculada
                                if dep_path in self.formula_paths:
                                    self.dependencies[formula_path].add(dep_path)
        except Exception as e:
            logger.exception("Erro inesperado ao construir grafo de dependências: %s", e)
            raise
    
    def classify_execution_groups(self) -> Dict[str, int]:
        """
        Classifica as fórmulas em grupos de execução usando ordenação topológica.

        Retorno:
            Dict mapeando o caminho da fórmula para o grupo de execução (1-N)
        """
        try:
            # Reconstrói o grafo de dependências
            self._build_dependency_graph()

            # Calcula o grau de entrada (quantas dependências cada fórmula possui)
            in_degree = {path: 0 for path in self.formula_paths}

            # Conta as dependências internas
            for formula_path in self.formula_paths:
                in_degree[formula_path] = len(self.dependencies[formula_path])

            # Ordenação topológica por níveis
            current_group = 1
            processed = set()

            # Enquanto houver fórmulas não processadas
            while len(processed) < len(self.formula_paths):

                # Encontrar fórmulas sem dependências não processadas
                current_level = []

                for path in self.formula_paths:
                    if path not in processed:
                        # Verifica se todas as dependências já foram processadas
                        deps_satisfied = all(
                            dep in processed or dep not in self.formula_paths
                            for dep in self.dependencies[path]
                        )
                        # Se todas as dependências forem satisfeitas, adiciona ao nível atual
                        if deps_satisfied:
                            current_level.append(path)

                # Se nenhuma fórmula for encontrada no nível atual, há um ciclo
                if not current_level:

                    # Adiciona as restantes no último grupo
                    for path in self.formula_paths:
                        if path not in processed:
                            self.execution_groups[path] = current_group
                            processed.add(path)
                    break

                # Atribui o grupo atual às fórmulas encontradas
                for path in current_level:
                    self.execution_groups[path] = current_group
                    processed.add(path)

                # Avança para o próximo grupo
                current_group += 1

            return self.execution_groups
        except Exception as e:
            logger.exception("Erro inesperado ao classificar grupos de execução: %s", e)
            return {}
    
    def get_execution_order(self) -> Dict[int, List[str]]:
        """
        Retorna as fórmulas agrupadas pela ordem de execução.

        Retorna:
            Dicionário com grupos (1-N) mapeando para uma lista de caminhos das fórmulas
        """
        try:
            # Garante que os grupos de execução estejam classificados
            if not self.execution_groups:
                self.classify_execution_groups()

            groups = defaultdict(list)
            for path, group in self.execution_groups.items():
                groups[group].append(path)

            return dict(groups)
        except Exception as e:
            logger.exception("Erro inesperado ao obter ordem de execução: %s", e)
            return {}
        
    def validate_dependencies(self) -> List[str]:
        """
        Valida se há dependências circulares ou problemas no grafo.

        Retorna:
            Lista de erros encontrados
        """
        try:
            errors = []

            # Verifica dependências circulares usando DFS
            def has_cycle(node, visited, rec_stack):
                try:
                    visited.add(node)
                    rec_stack.add(node)

                    for neighbor in self.dependencies.get(node, set()):
                        if neighbor in self.formula_paths:  # Verifica apenas dependências internas
                            if neighbor not in visited:
                                if has_cycle(neighbor, visited, rec_stack):
                                    return True
                            elif neighbor in rec_stack:
                                return True

                    rec_stack.remove(node)
                    return False
                except Exception as e:
                    logger.exception("Erro inesperado na detecção de ciclos: %s", e)
                    return False

            # Verifica cada nó para ciclos
            visited = set()
            for path in self.formula_paths:
                if path not in visited:
                    if has_cycle(path, visited, set()):
                        errors.append(f"Circular dependency detected involving {path}")

            # Todas as dependências são validadas durante a construção do grafo
            return errors
        except Exception as e:
            logger.exception("Erro inesperado ao validar dependências: %s", e)
            return []
