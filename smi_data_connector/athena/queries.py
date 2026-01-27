from athena.connection import AthenaConnection

def query_data(
    query, 
    database, 
    output_location, 
    region_name=None, 
    aws_access_key_id=None, 
    aws_secret_access_key=None,
    paginate=True,
    max_results_per_page=1000
):
    """
    Executa uma consulta no AWS Athena e retorna os resultados como um DataFrame do pandas.
    Agora suporta paginação automática para recuperar todos os resultados.
    
    Args:
        query (str): Consulta SQL a ser executada.
        database (str): O banco de dados a ser utilizado na consulta.
        output_location (str): Localização S3 onde os resultados da consulta serão armazenados.
        region_name (str, opcional): Nome da região AWS. Padrão obtido da variável de ambiente.
        aws_access_key_id (str, opcional): Chave de acesso da AWS. Padrão obtido da variável de ambiente.
        aws_secret_access_key (str, opcional): Chave secreta da AWS. Padrão obtido da variável de ambiente.
        paginate (bool, opcional): Se deve utilizar paginação para obter todos os resultados. Padrão é True.
        max_results_per_page (int, opcional): Número máximo de resultados por página. Padrão é 1000.
        
    Returns:
        pandas.DataFrame: Resultados da consulta em um DataFrame com todas as linhas.
    """
    # Cria a conexão com o Athena
    connection = AthenaConnection(
        region_name=region_name,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key
    )
    
    # Executa a consulta
    query_execution_id = connection.execute_query(
        query=query,
        database=database,
        output_location=output_location,
        wait=True
    )
    
    # Obtém os resultados da consulta com paginação
    if paginate:
        results = connection.get_query_results(
            query_execution_id, 
            max_results=max_results_per_page
        )
    else:
        # Usa o método antigo (limitado a ~1000 linhas)
        results = connection.get_query_results(query_execution_id)
    
    return results

def query_data_generator(
    query, 
    database, 
    output_location, 
    region_name=None, 
    aws_access_key_id=None, 
    aws_secret_access_key=None,
    max_results_per_page=1000
):
    """
    Executa uma consulta no AWS Athena e gera resultados paginados.
    Útil para processar conjuntos de resultados muito grandes sem carregar tudo na memória.
    
    Args:
        query (str): Consulta SQL a ser executada.
        database (str): O banco de dados a ser utilizado na consulta.
        output_location (str): Localização S3 onde os resultados da consulta serão armazenados.
        region_name (str, opcional): Nome da região AWS. Padrão obtido da variável de ambiente.
        aws_access_key_id (str, opcional): Chave de acesso da AWS. Padrão obtido da variável de ambiente.
        aws_secret_access_key (str, opcional): Chave secreta da AWS. Padrão obtido da variável de ambiente.
        max_results_per_page (int, opcional): Número máximo de resultados por página. Padrão é 1000.
        
    Yields:
        pandas.DataFrame: Cada página de resultados da consulta como um DataFrame.
    """
    # Cria a conexão com o Athena
    connection = AthenaConnection(
        region_name=region_name,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key
    )
    
    # Executa a consulta
    query_execution_id = connection.execute_query(
        query=query,
        database=database,
        output_location=output_location,
        wait=True
    )
    
    # Gera os resultados paginados
    for page_df in connection.get_query_results_paginated(
        query_execution_id, 
        max_results=max_results_per_page
    ):
        yield page_df

def list_databases(
    output_location, 
    region_name=None, 
    aws_access_key_id=None, 
    aws_secret_access_key=None
):
    """
    Lista todos os bancos de dados disponíveis no AWS Athena.
    
    Args:
        output_location (str): Localização S3 onde os resultados da consulta serão armazenados.
        region_name (str, opcional): Nome da região AWS. Padrão obtido da variável de ambiente.
        aws_access_key_id (str, opcional): Chave de acesso da AWS. Padrão obtido da variável de ambiente.
        aws_secret_access_key (str, opcional): Chave secreta da AWS. Padrão obtido da variável de ambiente.
        
    Returns:
        pandas.DataFrame: DataFrame contendo os nomes dos bancos de dados.
    """
    query = "SHOW DATABASES"
    
    # Usa um banco de dados placeholder para esta consulta
    return query_data(
        query=query,
        database="default",
        output_location=output_location,
        region_name=region_name,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        paginate=False  # SHOW DATABASES normalmente retorna poucos resultados
    )

def list_tables(
    database,
    output_location, 
    region_name=None, 
    aws_access_key_id=None, 
    aws_secret_access_key=None
):
    """
    Lista todas as tabelas em um banco de dados especificado no AWS Athena.
    
    Args:
        database (str): O banco de dados do qual listar as tabelas.
        output_location (str): Localização S3 onde os resultados da consulta serão armazenados.
        region_name (str, opcional): Nome da região AWS. Padrão obtido da variável de ambiente.
        aws_access_key_id (str, opcional): Chave de acesso da AWS. Padrão obtido da variável de ambiente.
        aws_secret_access_key (str, opcional): Chave secreta da AWS. Padrão obtido da variável de ambiente.
        
    Returns:
        pandas.DataFrame: DataFrame contendo os nomes das tabelas.
    """
    query = f"SHOW TABLES IN {database}"
    
    return query_data(
        query=query,
        database=database,
        output_location=output_location,
        region_name=region_name,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        paginate=False  # SHOW TABLES normalmente retorna poucos resultados
    )