import os
import time
import boto3
import pandas as pd
from dotenv import load_dotenv

class AthenaConnection:
    """Classe para gerenciar conexões e consultas ao AWS Athena."""
    
    def __init__(self, region_name=None, aws_access_key_id=None, aws_secret_access_key=None):
        """
        Inicializa a conexão com o Athena.
        
        Args:
            region_name (str, opcional): Nome da região da AWS. Padrão obtido da variável de ambiente.
            aws_access_key_id (str, opcional): Chave de acesso da AWS. Padrão obtido da variável de ambiente.
            aws_secret_access_key (str, opcional): Chave secreta da AWS. Padrão obtido da variável de ambiente.
        """
        # Carrega as variáveis de ambiente do arquivo .env, se existir
        load_dotenv()
        
        # Usa os parâmetros fornecidos ou obtidos das variáveis de ambiente
        self.region_name = region_name or os.getenv('AWS_REGION')
        self.aws_access_key_id = aws_access_key_id or os.getenv('AWS_ACCESS_KEY_ID')
        self.aws_secret_access_key = aws_secret_access_key or os.getenv('AWS_SECRET_ACCESS_KEY')
        
        # Inicializa o cliente do Athena
        self.client = boto3.client(
            'athena',
            region_name=self.region_name,
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key
        )

    def execute_query(self, query, database, output_location, wait=True):
        """
        Executa uma consulta no AWS Athena.
        
        Args:
            query (str): Consulta SQL a ser executada.
            database (str): O banco de dados a ser usado na consulta.
            output_location (str): Localização S3 onde os resultados da consulta serão armazenados.
            wait (bool, opcional): Se deve aguardar a conclusão da consulta. Padrão é True.
            
        Returns:
            str: ID da execução da consulta
        """
        response = self.client.start_query_execution(
            QueryString=query,
            QueryExecutionContext={
                'Database': database
            },
            ResultConfiguration={
                'OutputLocation': output_location
            }
        )
        
        query_execution_id = response['QueryExecutionId']
        
        if wait:
            self._wait_for_query_completion(query_execution_id)
            
        return query_execution_id
    
    def _wait_for_query_completion(self, query_execution_id, max_attempts=50):
        """
        Aguarda a conclusão de uma consulta no Athena.
        
        Args:
            query_execution_id (str): ID da execução da consulta.
            max_attempts (int, opcional): Número máximo de tentativas de checagem do status. Padrão é 50.
        
        Returns:
            str: Estado final da consulta ('SUCCEEDED', 'FAILED', 'CANCELLED')
            
        Raises:
            Exception: Se a consulta falhar ou for cancelada.
        """
        state = 'RUNNING'
        attempts = 0
        
        while state in ['RUNNING', 'QUEUED'] and attempts < max_attempts:
            attempts += 1
            response = self.client.get_query_execution(QueryExecutionId=query_execution_id)
            state = response['QueryExecution']['Status']['State']
            
            if state in ['RUNNING', 'QUEUED']:
                time.sleep(2)  # Aguarda 2 segundos antes de verificar novamente
        
        if state == 'FAILED':
            reason = response['QueryExecution']['Status'].get('StateChangeReason', 'Nenhuma razão fornecida')
            raise Exception(f"Consulta falhou: {reason}")
        elif state == 'CANCELLED':
            raise Exception("Consulta foi cancelada")
            
        return state
    
    def get_query_results(self, query_execution_id, max_results=1000, include_columns=True):
        """
        Obtém os resultados de uma consulta como um pandas DataFrame com paginação automática.
        
        Args:
            query_execution_id (str): ID da execução da consulta.
            max_results (int, opcional): Número máximo de linhas por página. Padrão é 1000.
            include_columns (bool, opcional): Se deve incluir os cabeçalhos das colunas. Padrão é True.
            
        Returns:
            pandas.DataFrame: Resultados da consulta com todas as linhas.
        """
        all_rows = []
        columns = None
        next_token = None
        
        while True:
            # Prepara os parâmetros para a chamada da API
            params = {
                'QueryExecutionId': query_execution_id,
                'MaxResults': max_results
            }
            
            # Adiciona NextToken se existir (para paginação)
            if next_token:
                params['NextToken'] = next_token
            
            # Realiza a chamada da API
            response = self.client.get_query_results(**params)
            
            # Obtém os nomes das colunas na primeira resposta
            if columns is None and include_columns:
                columns = [col['Label'] for col in response['ResultSet']['ResultSetMetadata']['ColumnInfo']]
            
            # Extrai as linhas de dados
            rows = response['ResultSet']['Rows']
            
            # Pula a linha de cabeçalho somente na primeira resposta, se include_columns for True
            start_index = 1 if (next_token is None and include_columns) else 0
            
            for row in rows[start_index:]:
                data_row = []
                for datum in row['Data']:
                    data_row.append(datum.get('VarCharValue', ''))
                all_rows.append(data_row)
            
            # Verifica se há mais resultados
            next_token = response.get('NextToken')
            if not next_token:
                break
                
            print(f"Obtidas {len(all_rows)} linhas até o momento...")
        
        # Cria o DataFrame
        if columns:
            df = pd.DataFrame(all_rows, columns=columns)
        else:
            df = pd.DataFrame(all_rows)
            
        print(f"Total de linhas obtidas: {len(df)}")
        return df
    
    def get_query_results_paginated(self, query_execution_id, max_results=1000, include_columns=True):
        """
        Gera resultados paginados de uma consulta no Athena.
        Útil para processar conjuntos de resultados grandes sem carregar tudo na memória.
        
        Args:
            query_execution_id (str): ID da execução da consulta.
            max_results (int, opcional): Número máximo de linhas por página. Padrão é 1000.
            include_columns (bool, opcional): Se deve incluir os cabeçalhos das colunas. Padrão é True.
            
        Yields:
            pandas.DataFrame: Cada página de resultados da consulta como um DataFrame.
        """
        columns = None
        next_token = None
        page_number = 0
        
        while True:
            page_number += 1
            
            # Prepara os parâmetros para a chamada da API
            params = {
                'QueryExecutionId': query_execution_id,
                'MaxResults': max_results
            }
            
            # Adiciona NextToken se existir (para paginação)
            if next_token:
                params['NextToken'] = next_token
            
            # Realiza a chamada da API
            response = self.client.get_query_results(**params)
            
            # Obtém os nomes das colunas na primeira resposta
            if columns is None and include_columns:
                columns = [col['Label'] for col in response['ResultSet']['ResultSetMetadata']['ColumnInfo']]
            
            # Extrai as linhas de dados
            rows = response['ResultSet']['Rows']
            
            # Pula a linha de cabeçalho somente na primeira resposta, se include_columns for True
            start_index = 1 if (next_token is None and include_columns) else 0
            
            page_rows = []
            for row in rows[start_index:]:
                data_row = []
                for datum in row['Data']:
                    data_row.append(datum.get('VarCharValue', ''))
                page_rows.append(data_row)
            
            # Cria um DataFrame para esta página
            if columns:
                page_df = pd.DataFrame(page_rows, columns=columns)
            else:
                page_df = pd.DataFrame(page_rows)
            
            print(f"Página {page_number}: {len(page_df)} linhas")
            yield page_df
            
            # Verifica se há mais resultados
            next_token = response.get('NextToken')
            if not next_token:
                break
