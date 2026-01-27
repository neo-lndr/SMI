"""
Modulo responsavel pela integração com o Kartado.

Propósito:
    Fornece integração batch entre o data lake (Athena/Gold tables) e o sistema Kartado,
    extraindo registros aprovados, consolidando medições e carregando tanto dados quanto imagens.
    Executa verificações, compressão de imagens e chamadas autenticadas à API do Kartado.

Responsabilidades principais:
    - Consultar e agregar registros aprovados de apontamentos/RDOs via query_data_generator (Athena).
    - Mapear contratos e itens, obter/gerar medições e enviar registros de medição para o backend Kartado.
    - Recuperar imagens, comprimir e anexá-las aos reportings no Kartado usando upload autenticado.
    - Registrar estado, gerenciar segredos e carregar assets/roles via cliente de API seguro.

Posição na arquitetura:
    - Módulo de integração/ETL de camada de aplicação: atua como consumidor dos dados processados (prd_gold_data),
      orquestrador de regras de negócio para medições e produtor de atualizações para o serviço Kartado.
    - Normalmente executado como job agendado (batch), podendo ser chamado via CLI para janelas de data.

Dependências críticas:
    - Serviço Athena / query_data_generator (athena.queries.query_data_generator) para leitura dos dados.
    - security.SimpleSecretManager e security.secure_api_client.get_secure_client para gerenciamento de segredos e chamadas seguras à API.
    - API externa Kartado / Arteris (ARTERIS_API_BASE_URL, ARTERIS_API_TOKEN).
    - S3_OUTPUT_LOCATION para resultados intermediários do Athena.
    - requests (para autenticação e download de imagens) e image.compress_bytes para compressão.
    - holidays_br, python-dotenv para suporte a feriados e carregamento de variáveis de ambiente.

Considerações de segurança:
    - Segredos devem ser carregados via SimpleSecretManager; fallback para .env apenas se necessário.
    - Evitar interpolação direta de strings em consultas SQL (o código atual exibe avisos sobre risco de injeção).
    - Não deixar parâmetros de desenvolvimento hardcoded em produção (há avisos e valores temporários que devem ser removidos).
    - Tratar e armazenar imagens e payloads codificados em base64 com cuidado (limitar tamanho, validar conteúdo, respeitar timeouts).
    - Logar erros sem expor tokens/segredos; usar client seguro para chamadas autenticadas e timeouts apropriados.

Exemplo de uso básico:
    - Como função (importando o módulo em um ambiente com variáveis/segredos definidos):
            start_date=datetime(2025, 9, 1),
            end_date=datetime(2025, 9, 18),
            contract_code='CW082025',
            ignore_check=True,
            ignore_images=False
    - Via linha de comando:
        python kartado.py --start-date 2025-09-01 --end-date 2025-09-18 --contract-code CW082025
"""

import holidays_br
import logging
import requests
import base64
import argparse
import os
from dotenv import load_dotenv
from api_client import custom_url
from image import compress_bytes
from datetime import datetime, date, timedelta
from athena.queries import query_data_generator
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

def create_kartado_measurement_records(
        start_date: datetime, 
        end_date: datetime = datetime.now(), 
        contract_code = None, 
        ignore_check = False, 
        ignore_images = False
    ) -> None:

    """
    Cria registros de medição do Kartado para os apontamentos/RDOs aprovados no SMI

    Parâmetros:
        start_date (datetime): Data inicial para filtrar apontamentos/RDOs
        end_date (datetime): Data final para filtrar apontamentos/RDOs (default: agora)
        contract_code (str, opcional): Código do contrato para processar apenas um contrato específico
        ignore_check (bool): Ignorar verificação de contratos com dados no Kartado (default: False)
        ignore_images (bool): Processar apenas imagens, não criar registros de medição (default: True)
    """

    def get_performance_data(start_date: datetime, end_date: datetime, contract_kartado: str, contract_name: str) -> List[Dict[str, Any]]:
        """
        Obtém dados de performance para um contrato específico dentro do intervalo de datas.
        
        Parâmetros:
            start_date (datetime): Data inicial
            end_date (datetime): Data final
            contract_kartado (str): Identificador do contrato no Kartado
            contract_name (str): Nome do contrato
        
        Retorna:
            List[Dict]: Lista de registros de performance
        """

        # Consulta SQL para obter dados de performance
        str_query_performance = f"""
            SELECT uuid,
                contract_id,
                data_execucao,
                data_criacao,
                data_aprovacao,
                nota_media_ponderada,
                aprovado_por_nome,
                criado_por_nome,
                boletim_medicao_numero
            FROM
                prd_gold_data.avaliacoes_campo
            WHERE
                data_execucao BETWEEN TIMESTAMP '{start_date} 00:00:00' AND TIMESTAMP '{end_date} 00:00:00'
                AND contract_id = '{contract_kartado}'
            """        
        
        # Obter chaves de performance já existentes no SMI
        keys_perfm = get_kartado_performance_keys(contract_name)
        
        # Executar a consulta e agregar resultados
        perfm_records = []
        for page_df_perfm in query_data_generator(
            query=str_query_performance,
            database="prd_gold_data",
            output_location=OUTPUT_LOCATION,
            max_results_per_page=5
        ):
            pagerecord_perfm = page_df_perfm.to_dict('records')
            for record_perfm in pagerecord_perfm:
                if not record_perfm["uuid"] in keys_perfm:
                    perfm_records.append(record_perfm)

        return perfm_records
    
    def write_measurement_record(
            measurement_records, 
            performance_records, 
            contract,
            measurement) -> None:
        """
        Envia os registros de medição para o SMI via API

        Parâmetros:
            measurement_records (List[Dict]): Registros de medição a serem enviados
            performance_records (List[Dict]): Registros de performance a serem enviados
            contract (Dict): Dados do contrato
            measurement (Dict): Dados da medição
        """

        # Se não houver registros de medição, não faz nada
        if not measurement_records:
            return None

        # Monta o payload
        data = {
            "contract_name": contract["name"],
            "contract_meaesurement": measurement["name"],
            "contract_meaesurement_current": measurement["current"],
            "contract_processing_date": contract["processing_date"],
            "data": measurement_records,
            "data_performance": performance_records,
            "relations": {
                "asset": kartado_assets,
                "work_role": kartado_work_roles,
                "contract_item": contract["itens"]
            }
        }

        # Envia registro de medição usando cliente de API
        _url = f"{API_BASE_URL}/method/arteris_app.api.kartado.create_kartado_measurement_record"
        try:
            post_response = custom_url(
                api_base_url=_url,
                api_token=API_TOKEN,
                body=data,
                method="POST")
        except Exception as e:
            logger.error(f"Falha ao enviar registro de medição: {e}")

    def get_measurement(current_date: str, execution_date: str, contract: str) -> Optional[Dict[str, Any]]:
        """
        Obter ou criar a medição com o cliente de API

        Parâmetros:
            current_date: Data atual em formato string
            execution_date: Data de execução em formato string
            contract: Identificador do contrato

        Retorno:
            Dados da medição ou None se falhar
        """

        _url = f"{API_BASE_URL}/method/arteris_app.api.measurement.get_measurement?current_date_str={current_date}&execution_date_str={execution_date}&contract={contract}"

        try:
            data = custom_url(
                api_base_url=_url,
                api_token=API_TOKEN,
                method="POST",
                timeout=360)
            if data and "message" in data:
                return data["message"]
            else:
                return None
        except Exception as e:
            logger.error(f"Falha ao obter medição para o contrato {contract}: {e}")
            return None

    def get_kartado_keys(contract_name: str, contract_processing_date: str) -> List[str]:
        """
        Obter chaves de registros Kartado do SMI de dados já processados para evitar duplicação.

        Parâmetros:
            contract_name: Nome do contrato
            contract_processing_date: Data de processamento do contrato

        Retorno:
            Lista de chaves do kartado ou lista vazia se falhar
        """


        _url = f"{API_BASE_URL}/method/arteris_app.api.kartado.get_keys?contract_name={contract_name}&contract_processing_date={contract_processing_date}"

        try:
            data = custom_url(
                api_base_url=_url,
                api_token=API_TOKEN,
                method="GET")
            if data and "message" in data:
                return data["message"]
            else:
                return []
        except Exception as e:
            logger.error(f"Falha ao obter chaves do kartado para {contract_name}: {e}")
            return []
    
    def get_kartado_performance_keys(contract_name) -> List[str]:
        """
        Obter chaves de registros Kartado do SMI de dados já processados para evitar duplicação.

        Parâmetros:
            contract_name: Nome do contrato

        Retorno:
            Lista de chaves de performance ou lista vazia se falhar
        """

        _url = f"{API_BASE_URL}/method/arteris_app.api.kartado.get_keys_performance?contract_name={contract_name}"

        try:
            data = custom_url(
                api_base_url=_url,
                api_token=API_TOKEN,
                method="GET")
            if data and "message" in data:
                return data["message"]
            else:
                return []
        except Exception as e:
            logger.error(f"Falha ao obter chaves do kartado para {contract_name}: {e}")
            return []
    
    def get_contract_to_process(start_date: date) -> List[Dict[str, Any]]:
        """
        Obter o contrato a ser processado com base na data de início.

        Parâmetros:
            start_date (date): Data de início para filtrar contratos

        Retorno:
            List[Dict]: Lista de contratos a serem processados
        """

        _url = f"{API_BASE_URL}/method/arteris_app.api.kartado.get_process?start_date={start_date.strftime('%Y-%m-%d')}"

        try:
            data = custom_url(
                api_base_url=_url,
                api_token=API_TOKEN,
                method="GET")
            if data and "message" in data:
                return data["message"]
            else:
                return []
        except Exception as e:
            logger.error(f"Falha ao obter chaves do kartado: {e}")
            return []
    
    def load_kartado_data():
        """
        Processar e carregar dados do Kartado para o SMI
        """

        def set_current_measurement(measurement) -> Dict[str, Any]:
            """
            Define a medição atual com base nas datas

            Parâmetros:
                measurement (Dict): Dados da medição

            Retorno:
                Dict: Dados da medição com campos de data convertidos
            """

            current = measurement["measurements"][0]
            current["start_date"] = datetime.strptime(
                current["start"], "%Y-%m-%d").date()
            current["end_date"] = datetime.strptime(
                current["end"], "%Y-%m-%d").date()
            current["approval_start_date"] = datetime.strptime(
                current["approval_start"], "%Y-%m-%d").date()
            current["approval_end_date"] = datetime.strptime(
                current["approval_end"], "%Y-%m-%d").date()
            return current

        # Lista de contratos
        contracts ={}
        search_date = start_date
        counter = 0

        # Tipo RDO
        # Type RDO - Novo
        str_rdo_where = """ NOT u.rdo_id IS NULL AND 
                            rdo_aprovado.is_last_transition = true AND 
                            UPPER(rdo_aprovado.final_approval_step_name) LIKE '%APROVADO%' AND 
                            NOT c.status_nome = 'Encerrado' AND """
        
        str_rdo_from = """  INNER JOIN prd_gold_data.rdo rdo on rdo.mdruuid = u.rdo_id
                            INNER JOIN prd_gold_data.rdo_approval_transitions rdo_aprovado on rdo_aprovado.uuid = u.rdo_id
                            LEFT JOIN prd_gold_data.rdo_reporting_relationship r on r.mdruuid = u.rdo_id
                            LEFT JOIN prd_gold_data.apontamentos log on log.uuid_reportings = r.reportinguuid 
                            LEFT JOIN prd_gold_apontamentos.arteris_via_paulista prodc ON prodc.uuid = log.uuid_reportings """
        
        # Type RDO - Antigo
        str_rdo_where_old = """ NOT u.rdo_id IS NULL AND 
                            NOT c.status_nome = 'Encerrado' AND 
                            u.status_aprovacao = 'aprovado' AND 
                            rdo_aprovado.uuid IS NULL AND """

        str_rdo_from_old = """ INNER JOIN prd_gold_data.rdo rdo on rdo.mdruuid = u.rdo_id
                            LEFT JOIN prd_gold_data.rdo_approval_transitions rdo_aprovado on rdo_aprovado.uuid = u.rdo_id
                            LEFT JOIN prd_gold_data.rdo_reporting_relationship r on r.mdruuid = u.rdo_id
                            LEFT JOIN prd_gold_data.apontamentos log on log.uuid_reportings = r.reportinguuid 
                            LEFT JOIN prd_gold_apontamentos.arteris_via_paulista prodc ON prodc.uuid = log.uuid_reportings """        

        # # Type log - Novo
        str_log_where = """ NOT u.reporting_id IS NULL AND 
                            rdo.mdruuid IS NULL AND 
                            apontamento_aprovado.is_last_transition = true AND
                            UPPER(apontamento_aprovado.final_approval_step_name) LIKE '%APROVADO%' AND 
                            NOT c.status_nome = 'Encerrado' AND """

        str_log_from = """ INNER JOIN prd_gold_data.apontamentos log on log.uuid_reportings = u.reporting_id 
                           INNER JOIN prd_gold_data.reportings_approval_transitions apontamento_aprovado on apontamento_aprovado.uuid = u.reporting_id 
                           LEFT JOIN prd_gold_data.rdo rdo on rdo.mdruuid = null 
                           LEFT JOIN prd_gold_apontamentos.arteris_via_paulista prodc ON prodc.uuid = log.uuid_reportings """
        
        # # Type log - Antigo
        str_log_where_old = """ NOT u.reporting_id IS NULL AND 
                            NOT c.status_nome = 'Encerrado' AND 
                            u.status_aprovacao = 'aprovado' AND 
                            apontamento_aprovado.uuid IS NULL AND """

        str_log_from_old = """ INNER JOIN prd_gold_data.apontamentos log on log.uuid_reportings = u.reporting_id 
                           LEFT JOIN prd_gold_data.reportings_approval_transitions apontamento_aprovado on apontamento_aprovado.uuid = u.reporting_id 
                           LEFT JOIN prd_gold_data.rdo rdo on rdo.mdruuid = null 
                           LEFT JOIN prd_gold_apontamentos.arteris_via_paulista prodc ON prodc.uuid = log.uuid_reportings """        
        
        # # Type Others
        str_oth_where = """ u.reporting_id IS NULL AND u.rdo_id IS NULL AND 
                            NOT c.status_nome = 'Encerrado' AND 
                            u.status_aprovacao = 'aprovado' AND """

        str_oth_from = """ LEFT JOIN prd_gold_data.apontamentos log on log.uuid_reportings = null 
                           LEFT JOIN prd_gold_data.rdo rdo on rdo.mdruuid = null 
                           LEFT JOIN prd_gold_apontamentos.arteris_via_paulista prodc ON prodc.uuid = log.uuid_reportings """

        # SELECT comum
        str_select = """SELECT
                            c.uuid AS chave_contrato,
                            u.uuid AS chave_utilizacao,
                            u.item_contratual_id AS chave_item_contrato,
                            c.numero_objeto AS contrato,
                            u.data_criacao AT TIME ZONE 'America/Sao_Paulo' AS data_criacao,
                            ic.codigo_item,
                            ic.nome AS recurso_item,
                            ic.unidade_medida,
                            ic.tipo_item,
                            ic.peso,
                            ic.tipo_administracao,
                            u.quantidade,
                            u.valor_total,
                            u.valor_unitario,
                            [DATA]  AT TIME ZONE 'America/Sao_Paulo' AS data_aprovacao,
                            [STATUS] AS status_aprovacao,
                            u.resource_id AS chave_recurso,
                            u.aprovado_por_nome AS aprovado_por,
                            log.uuid_reportings AS log_chave_relatorio,
                            log.number_reportings AS log_codigo_relatorio,
                            log.executed_at_reportings AT TIME ZONE 'America/Sao_Paulo' AS log_data_execucao,
                            log.created_at_reportings  AT TIME ZONE 'America/Sao_Paulo' AS log_criado_em,
                            log.updated_at_reportings  AT TIME ZONE 'America/Sao_Paulo' AS log_atualizado_em,
                            log.due_at_reportings  AT TIME ZONE 'America/Sao_Paulo' AS log_data_vencimento,
                            log.start_date_work_plan  AT TIME ZONE 'America/Sao_Paulo' AS log_data_inicio_planejamento,
                            log.end_date_work_plan  AT TIME ZONE 'America/Sao_Paulo' AS log_data_fim_planejamento,
                            log.road_name_reportings AS log_nome_rodovia,
                            log.km_reference_reportings AS log_km_referencia,
                            log.km_reportings AS log_km_inicial,
                            log.end_km_reportings AS log_km_final,
                            log.longitude_reportings AS log_longitude,
                            log.latitude_reportings AS log_latitude,
                            log.form_data_reportings AS log_notas_formulario,
                            log.form_data_reportings AS log_notas_formulario_json,
                            log.direction_reportings AS log_sentido,
                            log.lane_reportings AS log_pista,
                            rdo.mdruuid AS rdo_chave,
                            rdo.number AS rdo_serial,
                            rdo."date" AS rdo_data,
                            rdo.createdby AS rdo_criado_por,
                            rdo.responsible AS rdo_responsavel,
                            rdo.morningweather AS rdo_clima_manha,
                            rdo.afternoonweather AS rdo_clima_tarde,
                            rdo.nightweather AS rdo_clima_noite,
                            rdo.morningconditions AS rdo_condicoes_manha,
                            rdo.afternoonconditions AS rdo_condicoes_tarde,
                            rdo.nightconditions AS rdo_condicoes_noite,
                            rdo.firm AS rdo_equipe,
                            rdo.morningstart AS rdo_hora_inicio_manha,
                            rdo.morningend AS rdo_hora_fim_manha,
                            rdo.afternoonstart AS rdo_hora_inicio_tarde,
                            rdo.afternoonend AS rdo_hora_fim_tarde,
                            rdo.nightstart AS rdo_hora_inicio_noite,
                            rdo.nightend AS rdo_hora_fim_noite,
                            prodc.length AS prodc_comprimento,
                            prodc.width AS prodc_largura,
                            prodc.height AS prodc_altura,
                            prodc.rap AS prodc_rap,
                            prodc.firm AS prodc_equipe, """

        # FROM comum
        str_from = """ FROM 
                            prd_gold_data.itens_contratuais ic 
                            INNER JOIN prd_gold_data.contratos c on c.uuid = ic.contrato_id
                            INNER JOIN prd_gold_data.utilizacoes u on ic.uuid = u.item_contratual_id """
        
        str_where = ""

        # Se passado por parametro processa o contrato
        no_data_contracts = set()
        contracts_name_to_process = set()
        if contract_code:

            print(f"Apenas o contrato {contract_code} será processado!")
            
            _url = f"{API_BASE_URL}/method/arteris_app.api.kartado.get_contract?contract={contract_code}"

            try:
                data = custom_url(
                    api_base_url=_url,
                    api_token=API_TOKEN,
                    method="GET"
                )
            except Exception as e:
                logger.error(f"Falha ao obter chaves do kartado para {contract_code}: {e}")
                return []

            if not data:
                return {'Erro': 'Contrato não localizado'}
            
            contracts_to_process = [
                {'name': data['message']['name'], 
                 'contrato': contract_code, 
                 'uuidkartado': data['message']['kartado']
                }]
        else:
            print(f"Processando todos os contratos com dados no período de {start_date.strftime('%Y-%m-%d')} a {end_date.strftime('%Y-%m-%d')}!")
            contracts_to_process = get_contract_to_process(end_date)

        # Para evitar processar contratos desnecessariamente
        # verifica se o contrato possui dados no Kartado
        ccount = 0
        # Existe a flag para ignorar a verificação
        if not ignore_check:

            for c in contracts_to_process:
                ccount += 1

                print(f"Checando contrato {c['contrato']} {c['name']} {ccount:03}/{len(contracts_to_process):03}")
                logger.info(f"Checando contrato {c['contrato']} {c['name']} {ccount:03}/{len(contracts_to_process):03}")

                str_where = ""

                # Verifica se o contrato já não foi mapeado ou é um contrato avulso
                if not c["uuidkartado"] or contract_code:

                    # Consulta SQL para contar registros aprovados no período
                    str_where += f"c.numero_objeto = '{c['contrato']}' AND "
                    str_query = f"""SELECT 
                                    MAX(rdo_aprovado.transition_date AT TIME ZONE 'America/Sao_Paulo') AS ultima_data,
                                    COUNT(c.uuid) AS registros,
                                    'rdo' AS tipo_registro
                                    {str_from}
                                    {str_rdo_from}
                                where
                                    {str_rdo_where}
                                    {str_where}
                                    rdo_aprovado.transition_date AT TIME ZONE 'America/Sao_Paulo' BETWEEN TIMESTAMP '{start_date.strftime("%Y-%m-%d")} 00:00:00' AND TIMESTAMP '{end_date.strftime("%Y-%m-%d")} 23:59:59'
                                union all
                                SELECT
                                    MAX(u.data_aprovacao AT TIME ZONE 'America/Sao_Paulo') AS ultima_data,
                                    COUNT(c.uuid) AS registros,
                                    'rdo' AS tipo_registro
                                    {str_from}
                                    {str_rdo_from_old}
                                where
                                    {str_rdo_where_old}
                                    {str_where}
                                    u.data_aprovacao AT TIME ZONE 'America/Sao_Paulo' BETWEEN TIMESTAMP '{start_date.strftime("%Y-%m-%d")} 00:00:00' AND TIMESTAMP '{end_date.strftime("%Y-%m-%d")} 23:59:59'
                                union all
                                SELECT
                                    MAX(apontamento_aprovado.transition_date AT TIME ZONE 'America/Sao_Paulo') AS ultima_data,
                                    COUNT(c.uuid) AS registros,
                                    'log' AS tipo_registro
                                    {str_from}
                                    {str_log_from}
                                where
                                    {str_log_where}
                                    {str_where}
                                    apontamento_aprovado.transition_date AT TIME ZONE 'America/Sao_Paulo' BETWEEN TIMESTAMP '{start_date.strftime("%Y-%m-%d")} 00:00:00' AND TIMESTAMP '{end_date.strftime("%Y-%m-%d")} 23:59:59'
                                union all
                                SELECT 
                                    MAX(u.data_aprovacao AT TIME ZONE 'America/Sao_Paulo') AS ultima_data,
                                    COUNT(c.uuid) AS registros,
                                    'log' AS tipo_registro
                                    {str_from}
                                    {str_log_from_old}
                                where
                                    {str_log_where_old}
                                    {str_where}
                                    u.data_aprovacao AT TIME ZONE 'America/Sao_Paulo' BETWEEN TIMESTAMP '{start_date.strftime("%Y-%m-%d")} 00:00:00' AND TIMESTAMP '{end_date.strftime("%Y-%m-%d")} 23:59:59'
                                union all
                                SELECT
                                    MAX(u.data_aprovacao AT TIME ZONE 'America/Sao_Paulo') AS ultima_data,
                                    COUNT(c.uuid) AS registros,
                                    'others' AS tipo_registro
                                    {str_from}
                                    {str_oth_from}
                                where
                                    {str_oth_where}
                                    {str_where}
                                    u.data_aprovacao AT TIME ZONE 'America/Sao_Paulo' BETWEEN TIMESTAMP '{start_date.strftime("%Y-%m-%d")} 00:00:00' AND TIMESTAMP '{end_date.strftime("%Y-%m-%d")} 23:59:59';"""                

                    records = []
                    for page_df in query_data_generator(
                        query=str_query,
                        database="prd_gold_data",
                        output_location=OUTPUT_LOCATION,
                        max_results_per_page=500
                    ):
                        pagerecord = page_df.to_dict('records')
                        records.extend(pagerecord)

                    total_records = 0
                    for r in records:

                        total_records += 0 if r["registros"] == '0' else 1

                    print(f"Registros localizados para o contrato {c['contrato']}, no periodo de {start_date.strftime('%Y-%m-%d')} a {end_date.strftime('%Y-%m-%d')}: {total_records}")

                    # Se não houver registros, armazena o contrato para não processar
                    if total_records == 0:

                        print(f"Nenhum registro localizado para o contrato {c['contrato']}, no periodo de {start_date.strftime('%Y-%m-%d')} a {end_date.strftime('%Y-%m-%d')}!")
                        no_data_contracts.add(c['name'])
                        inconsistency = f"Nenhum registro localizado para o contrato {c['contrato']}, no periodo de {start_date.strftime('%Y-%m-%d')} a {end_date.strftime('%Y-%m-%d')}!\nConsulta: {str_query}"

                        # Armazena a informação de que o contrato não possui dados
                        json_post = {
                            "contract": c['name'],
                            "errors": [inconsistency]
                        }

                        # Gravar a informação no SMI
                        _url = f"{API_BASE_URL}/method/arteris_app.api.kartado.write_no_records"

                        try:
                            custom_url(
                                api_base_url=_url,
                                api_token=API_TOKEN,
                                body=json_post,
                                method="POST"
                            )
                        except Exception as e:
                            logger.error(f"Falha ao obter chaves do kartado para {contract_code}: {e}")

        # Incializa variáveis para processamento
        current_measurement = None
        contract = None
        last_contract = ""
        measurement_records = []
        performance_records = []

        # Laço while para iterar em cada dia
        while search_date <= end_date:

            print(f"Localizando registros para o dia: {search_date.strftime('%Y-%m-%d')}")

            logger.info(f"Localizando registros para o dia: {search_date.strftime('%Y-%m-%d')}")

            # Obtem a lista de contratos a processar, que estejam dentro do período
            contracts_to_process = get_contract_to_process(search_date)            
                
            # Se apenas um contrato, filtra
            if contract_code and len(contracts_to_process) > 0:
                contracts_to_process = [c for c in contracts_to_process if c['contrato'] == contract_code]

            # Sem dados para a data
            if len(contracts_to_process) == 0:
                # Próximo dia
                search_date += timedelta(days=1)
                continue

            # Monta a lista de contratos a processar, removendo os que não possuem dados
            for contract in contracts_to_process:
                if not contract['name'] in no_data_contracts:
                    contracts_name_to_process.add(contract['name'])

            # Se apenas um contrato, filtra na query
            str_where = ""
            if len(contracts_name_to_process) == 1:
                for c in contracts_to_process:
                    if c['name'] in contracts_name_to_process:
                        if c['uuidkartado']:
                            str_where = f"c.uuid = '{c['uuidkartado']}' AND "
                        else:
                            str_where = f"c.numero_objeto = '{c['contrato']}' AND "
 
            # Consulta SQL para obter registros aprovados no período
            str_query = f"""{str_select
                                .replace("[DATA]","rdo_aprovado.transition_date")
                                .replace("[STATUS]", "rdo_aprovado.final_approval_step_name")}
                                0 AS ordem,
                                'rdo' AS tipo_registro
                                {str_from}
                                {str_rdo_from}
                            where
                                {str_rdo_where}
                                {str_where}
                                rdo_aprovado.transition_date AT TIME ZONE 'America/Sao_Paulo' BETWEEN TIMESTAMP '{search_date.strftime("%Y-%m-%d")} 00:00:00' AND TIMESTAMP '{search_date.strftime("%Y-%m-%d")} 23:59:59'
                            union all
                            {str_select
                                .replace("[DATA]","u.data_aprovacao")
                                .replace("[STATUS]", "u.status_aprovacao")}
                                0 AS ordem,
                                'rdo' AS tipo_registro
                                {str_from}
                                {str_rdo_from_old}
                            where
                                {str_rdo_where_old}
                                {str_where}
                                u.data_aprovacao AT TIME ZONE 'America/Sao_Paulo' BETWEEN TIMESTAMP '{search_date.strftime("%Y-%m-%d")} 00:00:00' AND TIMESTAMP '{search_date.strftime("%Y-%m-%d")} 23:59:59'
                            union all                            
                            {str_select
                                .replace("[DATA]","apontamento_aprovado.transition_date")
                                .replace("[STATUS]", "apontamento_aprovado.final_approval_step_name")}
                                1 AS ordem,
                                'log' AS tipo_registro
                                {str_from}
                                {str_log_from}
                            where
                                {str_log_where}
                                {str_where}
                                apontamento_aprovado.transition_date AT TIME ZONE 'America/Sao_Paulo' BETWEEN TIMESTAMP '{search_date.strftime("%Y-%m-%d")} 00:00:00' AND TIMESTAMP '{search_date.strftime("%Y-%m-%d")} 23:59:59'
                            union all
                            {str_select
                                .replace("[DATA]","u.data_aprovacao")
                                .replace("[STATUS]", "u.status_aprovacao")}
                                1 AS ordem,
                                'log' AS tipo_registro
                                {str_from}
                                {str_log_from_old}
                            where
                                {str_log_where_old}
                                {str_where}
                                u.data_aprovacao AT TIME ZONE 'America/Sao_Paulo' BETWEEN TIMESTAMP '{search_date.strftime("%Y-%m-%d")} 00:00:00' AND TIMESTAMP '{search_date.strftime("%Y-%m-%d")} 23:59:59'
                            union all
                            {str_select
                                .replace("[DATA]","u.data_aprovacao")
                                .replace("[STATUS]", "u.status_aprovacao")}
                                2 AS ordem,
                                'others' AS tipo_registro
                                {str_from}
                                {str_oth_from}
                            where
                                {str_oth_where}
                                {str_where}
                                u.data_aprovacao AT TIME ZONE 'America/Sao_Paulo' BETWEEN TIMESTAMP '{search_date.strftime("%Y-%m-%d")} 00:00:00' AND TIMESTAMP '{search_date.strftime("%Y-%m-%d")} 23:59:59'
                            order by 
                                ordem,
                                rdo_chave,
                                log_chave_relatorio,
                                chave_contrato,
                                rdo_data,
                                log_data_execucao;"""  

            records = []
            for page_df in query_data_generator(
                query=str_query,
                database="prd_gold_data",
                output_location=OUTPUT_LOCATION,
                max_results_per_page=500
            ):
                pagerecord = page_df.to_dict('records')
                records.extend(pagerecord)

            last_contract = ""
            measurement_records = []
            performance_records = []

            print(f"Registros para {search_date.strftime('%Y-%m-%d')}: {len(records)}")

            logger.info(f"Registros para {search_date.strftime('%Y-%m-%d')}: {len(records)}")

            # Verifica se os resultados estão vazios
            for record in records:
                
                counter += 1

                # Verificar se o registro já está nos itens do contrato
                if last_contract != record["chave_contrato"]:

                    # Se não for o primeiro registro
                    if last_contract:
                        if measurement_records:
                            write_measurement_record(
                                measurement_records, 
                                performance_records, 
                                contract,
                                current_measurement)
                            measurement_records = []
                            performance_records = []

                    # Reiniciar os registros de medição para o novo contrato
                    measurement_records = []
                    last_contract = record["chave_contrato"]            

                # Verificar se o registro já está no dicionário de contratos
                if record["chave_contrato"] not in contracts:

                    contract = { 
                        "name": "",
                        "code": "",
                        "kartado": "",
                        "processing_date": None,
                        "process": True,
                        "itens": [],
                        "keys": [],
                        "measurements": []
                    }
                    contracts[record["chave_contrato"]] = contract

                    # Obter contrato
                    _url = f"{API_BASE_URL}/method/arteris_app.api.kartado.get_contract?contract={record['contrato']}&kartado_uuid={record['chave_contrato']}"

                    try:
                        data = custom_url(
                            api_base_url=_url,
                            api_token=API_TOKEN,
                            method="GET"
                        )
                    except Exception as e:
                        logger.error(f"Falha ao obter dados do contrato: {e}")

                    if data["message"]: # type: ignore

                        # Verificar relacionamento do contrato
                        if not data["message"]["kartado"]: # type: ignore

                            # Gravar relacionamento no kartado
                            _url = f"{API_BASE_URL}/method/arteris_app.api.kartado.update_contract?contract={record['contrato']}&kartado_uuid={record['chave_contrato']}"

                            try:
                                data = custom_url(
                                    api_base_url=_url,
                                    api_token=API_TOKEN,
                                    method="POST"
                                )
                            except Exception as e:
                                logger.error(f"Falha ao gravar relacionamento de contrato: {e}")    

                        if not data['message']['name'] in contracts_name_to_process: # type: ignore
                            logger.info(f"Contrato não está na lista para processar! {record['contrato']}")
                            contract["process"] = False

                        else:
                            
                            # Atualizar informações do contrato
                            contract["name"] = data["message"]["name"] # type: ignore
                            contract["kartado"] = record["chave_contrato"]
                            contract["code"] = record["contrato"] 

                            # Obter itens do contrato
                            _url = f"{API_BASE_URL}/method/arteris_app.api.kartado.get_contract_items?contract_name={contract['name']}"

                            try:
                                data = custom_url(
                                    api_base_url=_url,
                                    api_token=API_TOKEN,
                                    method="GET"
                                )
                            except Exception as e:
                                logger.error(f"Falha ao obter itens do contrato: {e}")

                            itens = data["message"] # type: ignore
                            contract["itens"].extend(itens)

                    else:
                        # Falha ao obter contrato
                        contract["process"] = False

                else:

                    contract = contracts[record["chave_contrato"]]

                # Definir data de processamento
                s_processing_date = search_date.strftime("%Y-%m-%d")
                if not contract["processing_date"] == s_processing_date:
                    contract["processing_date"] = s_processing_date
                    contract["keys"] = get_kartado_keys(contract["name"], s_processing_date)

                # Se a data for maior que a última data de medição, criar uma nova medição
                execution_date_str = None
                if record["tipo_registro"] == 'rdo':
                    execution_date_str = record["rdo_data"].split('-')                    
                    execution_date = datetime.strptime(f"{execution_date_str[2]}-{execution_date_str[1]}-{execution_date_str[0]}", "%Y-%m-%d")
                elif record["tipo_registro"] == 'log':
                    if not record["log_data_execucao"]:
                        execution_date_str = record["data_aprovacao"].replace(' America/Sao_Paulo', '')[:10]
                    else:    
                        execution_date_str = record["log_data_execucao"].replace(' America/Sao_Paulo', '')[:10]
                    execution_date = datetime.strptime(execution_date_str, "%Y-%m-%d")
                else:
                    execution_date_str = record["data_aprovacao"].replace(' America/Sao_Paulo', '')[:10]
                    execution_date = datetime.strptime(execution_date_str, "%Y-%m-%d")

                # Continuar somente se o contrato tiver um nome
                if contract["name"] and contract["process"]:       

                    # Verificar medição atual do contrato
                    if not contract["measurements"]:
                        
                        measurement = get_measurement(
                            search_date.strftime("%Y-%m-%d"), 
                            execution_date.strftime("%Y-%m-%d"), 
                            contract["name"])
                        
                        if measurement:
                            current_measurement = set_current_measurement(measurement)
                            contract["measurements"].append(current_measurement)

                            # Obter performance uma vez para a medição
                            performance_records = get_performance_data(
                                current_measurement["start"], 
                                current_measurement["end"], 
                                contract["kartado"],
                                contract["name"]
                                )

                        else:
                            # Falha ao obter medição atual
                            contract["process"] = False

                if contract["process"]:

                    use_current = False

                    for m in contract["measurements"]:

                        m_start = m["start_date"]
                        m_end = m["end_date"]
                        m_approval_end = m["approval_end_date"]

                        # Aprovação fora do período, com execução anterior à data inicial da medição
                        if (execution_date.date() < m_start and 
                            search_date.date() >= m_start and 
                            search_date.date() <= m_approval_end):
                            use_current = True

                        # Aprovação dentro do período
                        if (execution_date.date() >= m_start and 
                            execution_date.date() <= m_end and 
                            search_date.date() <= m_approval_end):
                            use_current = True

                        # Grave aprovação dentro do período de aprovação, desde que a execução seja anterior ao final da medição
                        if use_current:
                            if not current_measurement == m:
                                if measurement_records:
                                    write_measurement_record(
                                        measurement_records, 
                                        performance_records, 
                                        contract,
                                        current_measurement)
                                    measurement_records = []
                                    performance_records = []
                                current_measurement = m
                            break

                    # Verificar se a medição foi carregada
                    if (not use_current):

                        if measurement_records:
                            write_measurement_record(
                                measurement_records, 
                                performance_records, 
                                contract,
                                current_measurement)
                            measurement_records = []
                            performance_records = []

                        # Obter nova medição
                        measurement = get_measurement(
                            search_date.strftime("%Y-%m-%d"), 
                            execution_date.strftime("%Y-%m-%d"), 
                            contract["name"])

                        # Define medição atual
                        current_measurement = set_current_measurement(measurement)
                        contract["measurements"].append(current_measurement)

                        # Obter performance apenas uma vez para a medição
                        performance_records = get_performance_data(
                            current_measurement["start"], 
                            current_measurement["end"], 
                            contract["kartado"],
                            contract["name"]
                        )

                    # Adicionar o registro aos registros da medição
                    if not record["chave_utilizacao"] in contract["keys"]:
                        measurement_records.append(record)
                    else:
                        logger.info(f"Registro {record['chave_utilizacao']} já utilizado!")

            # Próximo dia
            search_date += timedelta(days=1)

            # Escrever o último registro de medição
            if measurement_records:

                write_measurement_record(
                    measurement_records, 
                    performance_records, 
                    contract,
                    current_measurement)
                measurement_records = []
                performance_records = []


        # Escrever o último registro de medição
        if measurement_records:

            write_measurement_record(
                measurement_records, 
                performance_records, 
                contract,
                current_measurement)
            measurement_records = []
            performance_records = []

    def load_kartado_images() -> None:
        """
        Carrega as imagens dos apontamentos no Kartado
        """

        # Consulta SQL para obter apontamentos do Kartado com imagens
        str_sql = """
        SELECT
            log.uuid_reportings AS log_chave_relatorio,
            log.number_reportings AS log_codigo_relatorio
        FROM
            prd_gold_data.apontamentos log
        WHERE 
            NOT log.number_reportings IS NULL AND
            log.number_reportings IN """

        # Verifica se há registros de apontamentos sem UUID no SMI
        _url = f"{API_BASE_URL}/method/arteris_app.api.kartado.get_list_log_without_uuid"

        try:
            data = custom_url(
                api_base_url=_url,
                api_token=API_TOKEN,
                method="GET"
            )
        except Exception as e:
            logger.error(f"Falha ao obter registros de apontamentos sem UUID: {e}")

        print("Iniciando carga de imagens no Kartado...")

        if data: # type: ignore

            # Constroi a consulta para obter UUID dos apontamentos
            count_record = 0
            total_record = 0
            str_reports = "("
            if data["message"]:
                list_count = len(data["message"])

                for log in data["message"]:
                    count_record += 1
                    total_record += 1
                    logger.info(f"Processing {total_record:04d} of {list_count:04d}")

                    str_reports += f"'{log['codigorelatorio']}',"

                    records = []
                    if count_record == 25 or total_record == list_count:
                        count_record = 0
                        str_reports += "'NONE')"
                        str_query = f"""{str_sql}{str_reports};"""
                        str_reports = "("

                        for page_df in query_data_generator(
                            query=str_query,
                            database="prd_gold_data",
                            output_location=OUTPUT_LOCATION,
                            max_results_per_page=100
                        ):
                            pagerecord = page_df.to_dict('records')
                            records.extend(pagerecord)

                    # Atualizar os registros no Kartado com o UUID
                    for r in records:
                        _url = f"{API_BASE_URL}/method/arteris_app.api.kartado.update_log_without_uuid?report_code={r['log_codigo_relatorio']}&report_uuid={r['log_chave_relatorio']}"
                        try:
                            data = custom_url(
                                api_base_url=_url,
                                api_token=API_TOKEN,
                                method="POST"
                            )
                        except Exception as e:
                            logger.error(f"Falha ao atualizar registros de apontamentos sem UUID: {e}")                        

        # Carregar os apontamentos para carga das imagens
        str_sql = """
        SELECT
            link,
            reporting_id
        FROM
            prd_gold_data.imagens img
        WHERE 
            reporting_id IN """

        # Verifica se há registros de apontamentos para anexar imagens
        _url = f"{API_BASE_URL}/method/arteris_app.api.kartado.get_list_log_to_attach_images"

        try:
            data = custom_url(
                api_base_url=_url,
                api_token=API_TOKEN,
                method="GET"
            )
        except Exception as e:
            logger.error(f"Falha ao obter registros de apontamentos para anexar imagens: {e}")

        if not data or not data["message"]: # type: ignore
            logger.info("Nenhum apontamento para carga de imagens...")
            return

        # Obter as credenciais do Kartado
        _url = f"{API_BASE_URL}/method/arteris_app.api.kartado.get_up"
        try:
            data_up = custom_url(
                api_base_url=_url,
                api_token=API_TOKEN,
                method="GET"
            )
        except Exception as e:
            logger.error(f"Falha ao obter credenciais do Kartado: {e}")
            return

        if not data_up or not data_up["message"]:
            logger.info("Nenhuma credencial do Kartado para carga de imagens...")
            return

        kartado_username = data_up["message"]["username"]
        kartado_password = data_up["message"]["password"]

        # Contar a quantidade de registros
        list_count = len(data["message"])
        count_record = 0
        total_record = 0
        str_reports = "("
        keys = {}

        for key, values in data["message"].items():

            count_record += 1
            total_record += 1
            logger.info(f"Processando registro {total_record:04d} de {list_count:04d}")

            # Carregar as chaves do relatório
            for v in values['uuids']:
                keys.setdefault(v, [])
                if not key in keys[v]:
                    keys[v].append(key)
                str_reports += f"'{v}',"

            records = []
            if count_record == 25 or total_record == list_count:
                count_record = 0
                str_reports += "'NONE')"
                str_query = f"""{str_sql}{str_reports};"""
                str_reports = "("

                for page_df in query_data_generator(
                    query=str_query,
                    database="prd_gold_data",
                    output_location=OUTPUT_LOCATION,
                    max_results_per_page=100
                ):
                    pagerecord = page_df.to_dict('records')
                    records.extend(pagerecord)

                if not records:
                    logger.info("Nenhum apontamento para carga de imagens...")

            # *** USA REQUESTS PARA INTERAGIR COM A API DO KARTADO NA EXTRAÇÃO DE IMAGENS ***

            # Obter os logs 
            if records:

                # Obter o token de acesso do Kartado
                url = "https://api.kartado.com.br/token/login/"
                headers = {
                    "Content-Type": "application/vnd.api+json",
                    "Accept": "application/vnd.api+json"
                }
                payload = {
                    "data": {
                        "type": "ObtainJSONWebToken",
                        "attributes": {
                            "username": kartado_username,
                            "password": kartado_password
                        }
                    }
                }
                response = requests.post(url, json=payload, headers=headers)
                response.raise_for_status()
                jwt_token = response.json()['data']['token']
                logger.info("Token JWT Kartado obtido com sucesso.")

                for r in records:
                    # Baixar a imagem
                    url = r['link']
                    headers = {
                        "Authorization": f"JWT {jwt_token}",
                        "Accept": "application/vnd.api+json"
                    }
                    response = requests.get(url, headers=headers)
                    response.raise_for_status()
                    if response.status_code == 200:
                        content_bytes = response.content
                        compressed_image = compress_bytes(85, content_bytes)
                        if compressed_image["Error"]:
                            logger.error(f"Erro ao comprimir a imagem: {compressed_image['Error']}")
                            continue

                        # Enviar imagem para o Kartado
                        _url = f"{API_BASE_URL}/method/arteris_app.api.kartado.upload_image"

                        # Extrair os 5 primeiros e 5 últimos caracteres do reporting_id
                        reporting_id = r["reporting_id"]
                        data64 = base64.b64encode(compressed_image['data']).decode('utf-8')

                        for record in keys[reporting_id]:

                            # record é um uuid, pegue os 5 primeiros e 5 últimos caracteres
                            record_name = f"{record[:5]}-{record[-5:]}"
                            filename = f'{record_name}-FILENAME.{compressed_image["format"].lower()}'
                            has_gps = compressed_image.get('has_gps', False)
                            gps_coords = compressed_image.get('gps_coordinates', {})
                            json_post = {
                                "reporting_id": reporting_id,
                                "name": record,
                                "data": data64,
                                "filename": filename,
                                "has_gps": has_gps,
                                "gps_coordinates": gps_coords
                            }

                            try:
                                result = custom_url(
                                    api_base_url=_url,
                                    api_token=API_TOKEN,
                                    method="POST",
                                    body=json_post, 
                                    timeout=300)
                                if result:
                                    logger.info(f"Sucesso ao enviar imagem para o SMI {record_name}")
                                else:
                                    logger.warning(f"Falha ao enviar imagem para o SMI {record_name}")
                            except Exception as e:
                                logger.error(f"Erro ao enviar imagem para o SMI {record_name}: {e}")

    # Carregar variáveis de ambiente
    load_dotenv()

    # Obter variáveis de ambiente necessárias
    API_BASE_URL = os.getenv("ARTERIS_API_BASE_URL")
    API_TOKEN = os.getenv("ARTERIS_API_TOKEN")
    OUTPUT_LOCATION = os.getenv("S3_OUTPUT_LOCATION")

    # Carregar ativos usando cliente de API seguro
    try:

        _url = f"{API_BASE_URL}/method/arteris_app.api.kartado.get_assets"

        data = custom_url(
            api_base_url=_url,
            api_token=API_TOKEN,
            method="GET")
        if data and "message" in data:
            kartado_assets = data["message"]
        else:
            raise ValueError("Falha ao carregar ativos do Kartado")
    except Exception as e:
        logger.error(f"Falha ao carregar ativos do Kartado: {e}")
        return

    # Carregar funções de trabalho usando cliente de API seguro
    try:
        _url = f"{API_BASE_URL}/method/arteris_app.api.kartado.get_work_roles"
        data = custom_url(
            api_base_url=_url,
            api_token=API_TOKEN,
            method="GET")
        if data and "message" in data:
            kartado_work_roles = data["message"]
        else:
            raise ValueError("Falha ao carregar funções de trabalho do Kartado")
    except Exception as e:
        logger.error(f"Falha ao carregar funções de trabalho do Kartado: {e}")
        return

    # Registrar feriados
    holidays_br.Brazil(start_date.year).update_holidays()
    if start_date.year != end_date.year:
        holidays_br.Brazil(end_date.year).update_holidays()

    # Carregar os dados do Kartado
    try:

        load_kartado_data()
        
        if not ignore_images:
            load_kartado_images()

    except Exception as e:
        logger.error(f"Falha ao processar dados do Kartado: {e}")
        return

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Processar dados do Kartado')
    
    # Adicionar argumentos opcionais para as datas
    parser.add_argument('--start-date', 
                        type=str,
                        help='Data de início no formato YYYY-MM-DD (padrão: ontem)')
    
    parser.add_argument('--end-date',
                        type=str, 
                        help='Data de fim no formato YYYY-MM-DD (padrão: hoje)')
    
    parser.add_argument('--contract-code',
                        type=str,
                        help='Código do contrato específico')
    
    parser.add_argument('--ignore-check',
                        action='store_true',
                        help='Ignorar verificações de dados nos contratos')
    
    parser.add_argument('--ignore-images',
                        action='store_true',
                        help='Ignorar processamento de imagens')
    
    args = parser.parse_args()
    
    # Definir datas padrão ou usar as fornecidas
    if args.start_date:
        start_date = datetime.strptime(args.start_date, '%Y-%m-%d')
    else:
        start_date = datetime.combine(date.today() - timedelta(days=3), datetime.min.time())
    
    if args.end_date:
        end_date = datetime.strptime(args.end_date, '%Y-%m-%d')
    else:
        end_date = datetime.combine(date.today(), datetime.min.time())

    # start_date = datetime.strptime('2025-10-06', '%Y-%m-%d')
    # end_date = datetime.strptime('2025-10-06', '%Y-%m-%d')
    # args.ignore_check = True

    try:
    
        create_kartado_measurement_records(
            start_date=start_date,
            end_date=end_date,
            contract_code=args.contract_code,
            ignore_check=args.ignore_check,
            ignore_images=args.ignore_images
        )

    except Exception as e:
        logger.error(f"Falha ao processar dados do Kartado: {e}")
        exit(1)
