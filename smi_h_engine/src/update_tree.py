"""
Atualizador de Árvore com Resultados de Fórmulasa
Propósito:
    Gerencia a aplicação de resultados de fórmulas numa estrutura de árvore em memória: localiza um nó pela chave de caminho e atualiza os campos dos seus filhos com os resultados das fórmulas quando apropriado. Fornece busca recursiva por caminho e mescla resultados de fórmulas que não estejam em erro.
Responsabilidades principais:
    - Localizar recursivamente um nó na estrutura de árvore pelo seu caminho (path).
    - Aplicar resultados de fórmulas (formulas_results) aos campos dos nós correspondentes.
    - Ignorar resultados marcados com status de erro e tratar exceções durante a atualização.
    - Retornar a árvore atualizada em memória.
Posição na arquitetura:
    Componente de transformação/serviço do domínio: atua entre o motor que gera resultados de fórmulas e as camadas que consomem a árvore (por exemplo, apresentação, persistência ou exportação). Opera sobre estruturas de dados em memória e não faz persistência por si só.
Dependências críticas:
    - Estrutura esperada de tree_data: um dicionário com chave 'data' contendo uma lista de nós; cada nó pode ter chaves 'path', 'id', 'fields' e 'data' (filhos).
    - Estrutura de formulas: dicionário contendo pelo menos a chave 'path' que identifica o nó alvo para atualização.
    - Estrutura de formulas_results: iterável de dicionários com chaves 'id' e 'results' onde cada resultado tem 'path', 'result' e 'status'.
    - Comportamento recursivo de search_node_path para navegar a árvore.
Considerações de segurança:
    - Não executar ou avaliar (eval) conteúdo vindo de resultados de fórmulas; tratar somente como dados.
    - Evitar logar ou imprimir informações sensíveis dos nós ou resultados em ambientes de produção.
    - Proteger contra recursão excessiva (árvores muito profundas) que possa causar stack overflow; considerar implementação iterativa ou limites de profundidade.
    - Se a árvore for compartilhada entre threads/processos, aplicar sincronização para evitar condições de corrida durante mutações in-place.
Exemplo de uso básico:
    tree = { 'data': [ ... ] }                     # estrutura com nós e campos
    formulas = { 'path': 'path/to/target_node' }  # nó cujo filhos serão atualizados
    results = [
        {
            'id': 'child-node-id',
            'results': [
                {'path': 'field.path', 'result': 123, 'status': 'ok'},
                {'path': 'other.field', 'result': 'x', 'status': 'error'}
            ]
        }
    ]
    updater = UpdateTreeData(tree, formulas, results)
    updated_tree = updater.update_tree()
"""

import logging

logger = logging.getLogger(__name__)


class UpdateTreeData:
    """
    Atualiza a árvore com os resultados das fórmulas.
    """

    def __init__(self, tree_data: dict, formulas: dict, formulas_results: dict):
        try:
            self.tree_data = tree_data
            self.formulas = formulas
            self.formulas_results = formulas_results
        except Exception as e:
            logger.exception("Erro inesperado na inicialização: %s", e)
            raise

    def search_node_path(self, path: str, data: dict) -> dict: # type: ignore
        """
        Procura um nó nos dados da árvore com base no caminho fornecido.
        Parâmetros:
            path (str): O caminho a ser procurado.
            data (dict): Os dados da árvore onde procurar.
        Retorno:
            dict: O nó se encontrado, caso contrário None.
        """
        try:
            for node in data:
                if 'path' in node and node.get('path') == path:
                    return node
                if 'data' in node and node['data']:
                    found_node = self.search_node_path(path, node['data'])
                    if found_node:
                        return found_node
        except Exception as e:
            logger.exception("Erro inesperado na busca do nó: %s", e)
            return None

    def update_tree(self):
        """
        Atualiza a árvore com os resultados das fórmulas.
        Retorno:
            dict: A árvore atualizada.
        """
        try:
            path_node = self.formulas.get('path')
            update_node = self.search_node_path(path_node, self.tree_data['data']) # type: ignore

            if not update_node:
                logger.error("Nó não encontrado para o caminho: %s", path_node)
                return self.tree_data

            for formula_result in self.formulas_results:
                try:
                    for node in update_node['data']:
                        if formula_result['id'] == node['id']:
                            for path_result in formula_result['results']:
                                try:
                                    for field in node['fields']:
                                        if field['path'] == path_result['path'] and path_result['status'] != 'error':
                                            field['value'] = path_result['result']
                                except Exception as e:
                                    logger.exception("Erro atualizando campo: %s", e)
                                    continue
                except Exception as e:
                    logger.exception("Erro processando resultado da fórmula: %s", e)
                    continue

        except Exception as e:
            logger.exception("Erro inesperado atualizando árvore: %s", e)

        return self.tree_data
