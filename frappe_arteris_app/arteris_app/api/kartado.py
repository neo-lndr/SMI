import frappe
import json
import re
import frappe.utils
import base64
import hashlib
import uuid
from datetime import date, datetime
from .attachment import upload_file

@frappe.whitelist(methods=["POST"])
def write_no_records():
    """
    Insere erros do motor
    """
    body = frappe.form_dict
    
    contract = frappe.form_dict.contract
    errors = frappe.form_dict.errors

    integration_inconsistency = frappe.new_doc("Integration Inconsistency")
    integration_inconsistency.tipo = "Kartado"
    integration_inconsistency.dataehora = frappe.utils.now()
    integration_inconsistency.contrato = contract

    str_error = ""
    for error in errors:
        str_error += f"{error}\n"
        
    integration_inconsistency.observacoes = str_error
    integration_inconsistency.save()

    return {"Processed": True, "message": "Erros escritos com sucesso."}

@frappe.whitelist(methods=["GET"])
def get_process(start_date: str):
    sql = f"""
            SELECT 
                c.name,
                c.contrato,
                c.uuidkartado,
                c.datainiciomedicao,
                s.nome AS subsidiaria
            FROM 
                `tabContract` c
                LEFT JOIN `tabSubsidiary` s ON s.name = c.subsidiaria
            WHERE 
                c.datainiciomedicao <= '{start_date}'
                AND contratoencerrado IS NULL AND 
                (
                    c.uuidosiris IS NULL OR
                    c.uuidosiris = ''
                )
            """

    contracts_to_process = frappe.db.sql(sql, as_dict=True)

    if not contracts_to_process:
        print("Nenhum contrato para processar.")
        return

    # Exemplo: transformar os contratos em uma string, se necessário:
    # str_contracts_to_process = ', '.join([f"'{c}'" for c in contracts_to_process])    
    # return str_contracts_to_process

    return contracts_to_process

@frappe.whitelist(methods=["DELETE"])
def clear_keys():
    """
    Limpa todas as chaves do banco de dados.
    """
    get_result = frappe.db.get_all("Integration Record", fields=["name"], filters={"tipo": "Kartado"})
    for record in get_result:
        doc = frappe.get_doc("Integration Record", record.name)
        doc.delete()

@frappe.whitelist(methods=["GET"])
def get_assets():
    """ 
    Obtém todos os ativos do banco de dados.
    """
    data = []

    data = frappe.db.sql("""
            SELECT
                name,
                nomeativo AS kartado
            FROM
                `tabAsset`
            UNION ALL
            SELECT
                parent AS name,
                descricao AS kartado
            FROM
                `tabAsset Config Kartado`
        """, as_dict=True)

    # # Obter todos os ativos do banco de dados
    # get_result = frappe.db.get_all("Asset", fields=["name", "nomeativo"])
    # data.extend([{"name": l["name"], "kartado": l["nomeativo"]} for l in get_result])

    # # Obter todos os ativos do kartado do banco de dados
    # get_result = frappe.db.get_all("Asset Config Kartado", fields=["parent", "descricao"])
    # data.extend([{"name": l["parent"], "kartado": l["descricao"]} for l in get_result])

    return data

@frappe.whitelist(methods=["GET"])
def get_work_roles():
    """
    Obtém todas as funções de trabalho do banco de dados.
    """
    data = []

    data = frappe.db.sql("""
            SELECT
                name,
                funcao AS kartado
            FROM
                `tabWork Role`
            UNION ALL
            SELECT
                parent AS name,
                descricaokartado AS kartado    
            FROM
                `tabWork Role Config Kartado`
        """, as_dict=True)

    # # Obter todas as funções de trabalho do banco de dados
    # get_result = frappe.db.get_all("Work Role", fields=["name", "funcao"])
    # data.extend([{"name": l["name"], "kartado": l["funcao"]} for l in get_result])

    # # Obter todas as funções de trabalho do kartado do banco de dados
    # get_result = frappe.db.get_all("Work Role Config Kartado", fields=["parent", "descricaokartado"])
    # data.extend([{"name": l["parent"], "kartado": l["descricaokartado"]} for l in get_result])

    return data   

@frappe.whitelist(methods=["GET"])
def get_keys(contract_name: str, contract_processing_date: str):
    """
    Obtém todas as chaves para o contrato e kartado.
    """
    keys = []
    # Obter todos os registros de integração do contrato no banco de dados
    get_result = frappe.db.get_all("Integration Record", fields=["name"], filters={
             "contrato": contract_name,
             "data": contract_processing_date,
             "tipo": "Kartado"
        })
    if get_result:
        for l in get_result:
            # Obter as chaves do registro de integração
            get_keys_result = frappe.db.get_all("Integration Record Keys", fields=["uuid"], filters={"parent": l.name})
            if get_keys_result:
                # Se as chaves foram encontradas, adicioná-las à lista
                keys.extend([k.uuid for k in get_keys_result])

    return keys

@frappe.whitelist(methods=["GET"])
def get_keys_performance(contract_name: str):
    """
    Obtém todas as chaves para o contrato com Kartado Performance.
    """
    keys = []
    # Obter todos os registros de integração do contrato no banco de dados
    get_result = frappe.db.get_all("Integration Record", fields=["name"], filters={
             "contrato": contract_name,
             "tipo": "Kartado Performance"
        })
    if get_result:
        for l in get_result:
            # Obter as chaves do registro de integração
            get_keys_result = frappe.db.get_all("Integration Record Keys", fields=["uuid"], filters={"parent": l.name})
            if get_keys_result:
                # Se as chaves foram encontradas, adicioná-las à lista
                keys.extend([k.uuid for k in get_keys_result])

    return keys        

@frappe.whitelist(methods=["GET"])
def get_contract(contract: str, kartado_uuid = None):
    """
    Obtém o nome do contrato para o UUID do kartado.
    """
    # Obter todos os contratos do banco de dados
    get_result = None 
    if kartado_uuid:
        get_result = frappe.db.get_all("Contract", fields=["name", "uuidkartado"], filters={"uuidkartado": kartado_uuid})

    if not get_result:
        # Se nenhum contrato for encontrado com o UUID do kartado, verificar pelo nome do contrato
        get_result = frappe.db.get_all("Contract", fields=["name", "uuidkartado"], filters={"contrato": contract})
        
    if not get_result:
        # Se nenhum contrato for encontrado pelo nome, retornar um dicionário vazio
        return {}

    return {"name": get_result[0].name, "kartado": get_result[0].uuidkartado} if get_result else {}

@frappe.whitelist(methods=["GET"])
def get_contract_items(contract_name: str):
    """
    Obtém todos os itens do contrato do banco de dados.
    """
    data = []
    # Obter todos os itens do contrato do banco de dados
    get_result = frappe.db.get_all(
            "Contract Item", 
            fields=[
                "name", 
                "codigo", 
                "cidade",
                "dom_hora",
                "seg_hora",
                "ter_hora",
                "qua_hora", 
                "qui_hora",
                "sex_hora",
                "sab_hora",
                "percentualhe"], 
            filters={"contrato": contract_name})
    data.extend(
            [
                {
                    "name": l["name"], 
                    "kartado": l["codigo"], 
                    "cidade": l["cidade"],
                    "dom_hora": l["dom_hora"],
                    "seg_hora": l["seg_hora"],
                    "ter_hora": l["ter_hora"],
                    "qua_hora": l["qua_hora"],
                    "qui_hora": l["qui_hora"],
                    "sex_hora": l["sex_hora"],
                    "sab_hora": l["sab_hora"],
                    "percentualhe": l["percentualhe"]
                 } for l in get_result
            ])

    # Obter os itens do contrato do kartado do banco de dados
    for l in get_result:
        # Obter o código do kartado para cada item do contrato
        get_sub_result = frappe.db.get_all("Contract Item Config Kartado", fields=["codigo"], filters={"parent": l["name"]})
        if get_sub_result:
            data.extend([{"name": l["name"], "kartado": s["codigo"]} for s in get_sub_result])

    return data

@frappe.whitelist(methods=["POST"])
def update_contract(contract: str, kartado_uuid: str):
    """
    Atualiza o contrato com o UUID do kartado.
    """
    # Obter o contrato do banco de dados
    get_result = frappe.db.get_all("Contract", fields=["name"], filters={"contrato": contract})
    set_result = frappe.db.set_value("Contract", get_result[0].name, "uuidkartado", kartado_uuid)
    return set_result

@frappe.whitelist(methods=["POST"])
def update_measurements_main_item():
    # Obter todos os registros de medição do contrato
    m_records = frappe.db.get_all("Contract Measurement Record", fields=["name"], filters={"item": ""})
    # m_records = frappe.db.get_all("Contract Measurement Record", fields=["name"])

    for m_record in m_records:
        item_codes = ""
        # Obter o documento do registro de medição
        measurement_record = frappe.get_doc("Contract Measurement Record", m_record.name)

        # Obter todos os itens do registro de medição
        items = []
        for asset in measurement_record.tabasset:
            if asset.item not in items:
                items.append(asset.item)
        for work_role in measurement_record.tabworkrole:
            if work_role.item not in items:
                items.append(work_role.item)
        for resource in measurement_record.tabrecurso:
            if resource.item not in items:
                items.append(resource.item)

        if items:
            item_codes = get_items_code(items)
            frappe.db.set_value("Contract Measurement Record", m_record.name, "item", item_codes)

    return {"Processed": True, "message": "Registros de medição atualizados com o item principal."}

@frappe.whitelist(methods=["POST"])
def create_kartado_measurement_record(
        contract_name = None,
        contract_meaesurement = None,
        contract_meaesurement_current = None,
        contract_processing_date = None,
        data = None,
        data_performance = None,
        relations = None
    ):
    """
    Cria um registro de medição Kartado.
    """
    if not contract_name:
        # Obter os dados do corpo da requisição e as relações
        body = frappe.form_dict
        contract_name = frappe.form_dict.contract_name
        contract_meaesurement = frappe.form_dict.contract_meaesurement
        contract_meaesurement_current = frappe.form_dict.contract_meaesurement_current
        contract_processing_date = frappe.form_dict.contract_processing_date
        data = frappe.form_dict.data
        data_performance = frappe.form_dict.data_performance
        relations = frappe.form_dict.relations

    # holidays = {}

    # def get_item(item: str) -> dict:
    #     """
    #     Obtém a descrição de um item do contrato.
    #     """
    #     # Obter o kartado para cada item do contrato
    #     for i in relations["contract_item"]:
    #         if i['name'] == item:
    #             return i
    #     return None

    def check_kartado_relation(kartado_description, r_type):
        """
        Verifica a relação entre a descrição do kartado e a lista de relações.
        :param kartado_description: A descrição do kartado.
        :param r_type: O tipo de relação a ser verificado (ex.: "asset", "work_role", "contract_item").
        :return: O nome da relação do kartado se encontrado, caso contrário None.
        """
        for k in relations[r_type]:
            if k['kartado'].upper() == kartado_description.upper():
                return k["name"]

        return None
    
    def get_date_from_string(data_str: str, year: int = 0, month: int =1, day: int = 2) -> date:
        """
        Converte uma string de data para um objeto date.
        :param data_str: A data no formato 'YYYY-MM-DD'.
        :return: Um objeto date.
        """
        data_str = data_str.split('-')
        year = int(data_str[year])
        month = int(data_str[month]) 
        day = int(data_str[day][:2])   
        new_date = date(year, month, day)
        return new_date
    
    def get_week_day(date_obj: date):
        """
        Obtém o nome do dia da semana.
        :param date_obj: O objeto date.
        :return: O nome do dia da semana.
        """
        dias_semana = ['Segunda-feira', 'Terça-feira', 'Quarta-feira', 'Quinta-feira', 'Sexta-feira', 'Sábado', 'Domingo']
        return dias_semana[date_obj.weekday()]

    def save_integration_uuids(contract_name, contract_processing_date, contract_meaesurement, uuid_list, uuid_type):
        if uuid_list:
            integration_record = frappe.new_doc("Integration Record")
            integration_record.contrato = contract_name
            integration_record.data = contract_processing_date
            integration_record.boletimmedicao = contract_meaesurement
            integration_record.tipo = uuid_type
            for uuid_val in uuid_list:
                integration_record_key = integration_record.append("tabchaves")
                integration_record_key.uuid = uuid_val
            integration_record.save()  
    
    # Lista para armazenar dados inconsistentes
    inconsistent_data = []
    inconsistent_keys = []

    # Lista de UUIDs do kartado
    kartado_uuids = []
    kartado_performance_uuids = []
    kartado_logs = []
    items = {}
    str_logs = ""
    str_highways = ""

    # Cabeçalho do registro de medição
    kartado_measurement_record = None

    # Verificação do registro RDO
    kartado_rdo_check = None

    has_itens_data = False

    # Processar os itens
    for d in data:
        # Verificar mudança no registro RDO ou de Relatório
        if d.get('rdo_chave',''):
            rdo_check = f"{d.get('rdo_chave','')}"
        elif d.get('log_chave_relatorio',''):
            rdo_check = f"{d.get('log_chave_relatorio','')}"
        else:
            rdo_check = ""

        rdo_log = f" RDO: {d.get('rdo_serial','')} Apontamento: {d.get('log_codigo_relatorio','')}"

        # Verificar se houve mudança no registro RDO ou de Relatório
        if kartado_rdo_check != rdo_check:
            # Salvar o registro de medição
            if kartado_measurement_record and has_itens_data:
                if items:
                    kartado_measurement_record.item = get_items_code(items)                
                kartado_measurement_record.relatorio = str_logs[0:30]
                kartado_measurement_record.rodovia = str_highways[0:30]
                kartado_measurement_record.save()

            # Reinicializar o valor de kartado_rdo_check
            if d.get('rdo_chave',''):
                kartado_rdo_check = f"{d.get('rdo_chave','')}"
            elif d.get('log_chave_relatorio',''):
                kartado_rdo_check = f"{d.get('log_chave_relatorio','')}"
            else:
                kartado_rdo_check = ""            

            # Reinicializar o registro de medição do kartado
            has_itens_data = False
            kartado_measurement_record = None
            kartado_logs = []
            items = {}
            str_logs = ""
            str_highways = ""

        # Cabeçalho do registro de medição
        if not kartado_measurement_record:
            kartado_measurement_record = frappe.new_doc("Contract Measurement Record")
            kartado_measurement_record.tipo = f"Kartado - Importação de registros de medição - {d['contrato']}"
            kartado_measurement_record.datacriacao = d["data_criacao"].replace(' America/Sao_Paulo', '')
            kartado_measurement_record.dataexecucao = d["data_criacao"].replace(' America/Sao_Paulo', '')
            kartado_measurement_record.dataaprovacao = d["data_aprovacao"].replace(' America/Sao_Paulo', '')
            kartado_measurement_record.contrato = contract_name
            kartado_measurement_record.boletimmedicao = contract_meaesurement
            kartado_measurement_record.kminicial = 0
            kartado_measurement_record.kmfinal = 0
            kartado_measurement_record.medicaovigente = contract_meaesurement_current
            kartado_measurement_record.aprovador = d["aprovado_por"]
            kartado_measurement_record.eh_feriado = False

            if d["tipo_registro"] == "rdo":  # ou record_type == "rpt":
                data_execucao = d["rdo_data"].replace(' America/Sao_Paulo', '').split('-')
                kartado_measurement_record.dataexecucao = f"{data_execucao[2]}-{data_execucao[1]}-{data_execucao[0]}"
                kartado_measurement_record.origem_integracao = "Kartado RDO"
            elif d["tipo_registro"] == "log":
                kartado_measurement_record.dataexecucao = d["log_data_execucao"].replace(' America/Sao_Paulo', '') 
                kartado_measurement_record.origem_integracao = "Kartado Apontamento"
            else:
                kartado_measurement_record.origem_integracao = "Kartado Outros"

            # Definir código usando o código do relatório
            if d["log_codigo_relatorio"]:
                kartado_measurement_record.codigo = d["log_codigo_relatorio"]

            # Caso o RDO contenha dados
            if d["rdo_chave"]:
                kartado_measurement_record.responsavel = d["rdo_responsavel"]
                kartado_measurement_record.codigo = d["rdo_serial"]  # d["rdo_chave"]
                kartado_measurement_record.climadamanha = d["rdo_clima_manha"]
                kartado_measurement_record.condicoesdamanha = d["rdo_condicoes_manha"]
                kartado_measurement_record.climadatarde = d["rdo_clima_tarde"]
                kartado_measurement_record.condicoesdatarde = d["rdo_condicoes_tarde"]
                kartado_measurement_record.climadanoite = d["rdo_clima_noite"]
                kartado_measurement_record.condicoesdanoite = d["rdo_condicoes_noite"]
                kartado_measurement_record.criadopor = d["rdo_criado_por"]
                kartado_measurement_record.equipe = d["rdo_equipe"]

        # Verificar dados inconsistentes
        has_inconsistent_data = False

        # Verificar se a relação do kartado existe para ativo, função e item do contrato
        d["chave_ativo"] = check_kartado_relation(d.get("recurso_item"), "asset")
        d["chave_funcao"] = check_kartado_relation(d.get("recurso_item"), "work_role")
        d["chave_recurso"] = check_kartado_relation(d.get("codigo_item"), "contract_item")
        
        # Verificar se é registro administrativo
        if d["tipo_administracao"]:
            if not d["chave_ativo"] and not d["chave_funcao"]:
                msg = f"Relação de ativo ou função '{d.get('recurso_item')}' não localizada. {rdo_log}"
                if msg not in inconsistent_data:
                    inconsistent_data.append(msg)
                has_inconsistent_data = True

        # Sempre verificar se a relação com o item do contrato existe
        if not d["chave_recurso"]:
            msg = f"Relação com item do contrato '{d.get('codigo_item')}' não localizada. {rdo_log}"
            if msg not in inconsistent_data:
                inconsistent_data.append(msg)
            has_inconsistent_data = True

        # Adicionar o UUID do kartado às chaves inconsistentes
        if has_inconsistent_data:
            chave_inconsistencia = f"{d['data_aprovacao'].replace(' America/Sao_Paulo', '')} - {d['chave_utilizacao']}"
            if chave_inconsistencia not in inconsistent_keys:
                inconsistent_keys.append(chave_inconsistencia)
        else:
            # Verificar se o UUID do kartado já está na lista e ignorá-lo se estiver
            if d["chave_utilizacao"] in kartado_uuids:
                continue
            else:
                kartado_uuids.append(d["chave_utilizacao"])

                # Criar registro de medição para função de trabalho
                if d["chave_funcao"]:
                    has_itens_data = True
                    kartado_measurement_work_role_record = kartado_measurement_record.append("tabworkrole")
                    kartado_measurement_work_role_record.item = d["chave_recurso"]
                    kartado_measurement_work_role_record.funcao = d["chave_funcao"]
                    kartado_measurement_work_role_record.quantidademedida = d["quantidade"]
                    kartado_measurement_work_role_record.valortotal = d["valor_total"]
                    kartado_measurement_work_role_record.valorcalculado = 0.0
                    kartado_measurement_work_role_record.tipo = d["tipo_item"]
                    kartado_measurement_work_role_record.peso = d["peso"]
                    if d["chave_recurso"] not in items:
                        desc = get_item_description(d["chave_recurso"])
                        items.setdefault(d["chave_recurso"], desc)

                # Criar registro de medição para ativo
                if d["chave_ativo"]:
                    has_itens_data = True
                    kartado_measurement_asset_record = kartado_measurement_record.append("tabasset")
                    kartado_measurement_asset_record.item = d["chave_recurso"]
                    kartado_measurement_asset_record.maquina_equipamento_ou_ferramenta = d["chave_ativo"]
                    kartado_measurement_asset_record.quantidademedida = d["quantidade"]
                    kartado_measurement_asset_record.valortotal = d["valor_total"]
                    kartado_measurement_asset_record.valorcalculado = 0.0
                    kartado_measurement_asset_record.tipo = d["tipo_item"]
                    kartado_measurement_asset_record.peso = d["peso"]                
                    if d["chave_recurso"] not in items:
                        desc = get_item_description(d["chave_recurso"])
                        items.setdefault(d["chave_recurso"], desc)

                if (d["tipo_item"] == "administração" and (d["chave_funcao"] or d["chave_ativo"])):
                    # Definir a data padrão para processamento
                    date_process = get_date_from_string(d["data_criacao"])
                    # Data para processamento
                    if d["tipo_registro"] == "rdo":
                        date_process = get_date_from_string(d["rdo_data"], 2, 1, 0)
                    if d["tipo_registro"] == "log":
                        date_process = get_date_from_string(d["log_data_execucao"])
                    if d["tipo_registro"] == "others":
                        date_process = get_date_from_string(d["data_criacao"])
                    
                    # Strings de timestamp
                    ts_start = "2000-01-01 00:00:00.000"
                    ts_end = "2000-01-01 00:00:00.000"

                    # Obter a hora de início
                    if ts_start == ts_end and d["rdo_hora_inicio_manha"]:
                        ts_start = f'2000-01-01 {d["rdo_hora_inicio_manha"]}:00.000'
                    if ts_start == ts_end and d["rdo_hora_inicio_tarde"]:                            
                        ts_start = f'2000-01-01 {d["rdo_hora_inicio_tarde"]}:00.000'
                    if ts_start == ts_end and d["rdo_hora_inicio_noite"]:                            
                        ts_start = f'2000-01-01 {d["rdo_hora_inicio_noite"]}:00.000'

                    # Obter a hora de término
                    if d["rdo_hora_fim_manha"]:
                        ts_end =  f'2000-01-01 {d["rdo_hora_fim_manha"]}:00.000'
                    if d["rdo_hora_fim_tarde"]:
                        ts_end =  f'2000-01-01 {d["rdo_hora_fim_tarde"]}:00.000'
                    if d["rdo_hora_fim_noite"]:
                        ts_end =  f'2000-01-01 {d["rdo_hora_fim_noite"]}:00.000'

                    # Converter para datetime
                    time_start = datetime.strptime(ts_start, '%Y-%m-%d %H:%M:%S.%f')
                    time_end = datetime.strptime(ts_end, '%Y-%m-%d %H:%M:%S.%f')                        

                    # Registro de horas
                    kartado_measurement_record_time = kartado_measurement_record.append("tabhoras")
                    kartado_measurement_record_time.item = d["chave_recurso"]
                    kartado_measurement_record_time.funcao = d["chave_funcao"]
                    kartado_measurement_record_time.maquina_equipamento_ou_ferramenta = d["chave_ativo"]
                    kartado_measurement_record_time.quantidade = d["quantidade"]  # 1
                    kartado_measurement_record_time.horainicial = time_start.strftime('%H:%M:%S')
                    kartado_measurement_record_time.horafinal = time_end.strftime('%H:%M:%S')
                    kartado_measurement_record_time.compensacoes = 0.0
                    kartado_measurement_record_time.horaextra100 = 0.0
                    kartado_measurement_record_time.horaextra = 0.0
                    kartado_measurement_record_time.horanormal = 0.0
                    kartado_measurement_record_time.horanormalda = 0.0
                    kartado_measurement_record_time.valorcalculado = 0.0

                    # Obter o nome do dia da semana
                    kartado_measurement_record.diasemana = get_week_day(date_process)                        

                # Criar registro de medição para recurso
                if not d["chave_ativo"] and not d["chave_funcao"]:
                    if d["chave_recurso"]:
                        has_itens_data = True
                        kartado_measurement_reseource_record = kartado_measurement_record.append("tabrecurso")
                        kartado_measurement_reseource_record.item = d["chave_recurso"]
                        kartado_measurement_reseource_record.quantidademedida = d["quantidade"]
                        kartado_measurement_reseource_record.valortotal = d["valor_total"]
                        kartado_measurement_reseource_record.tipo = d["tipo_item"]
                        kartado_measurement_reseource_record.peso = d["peso"]      
                        kartado_measurement_reseource_record.valorcalculado = 0.0
                        if d["chave_recurso"] not in items:
                            desc = get_item_description(d["chave_recurso"])
                            items.setdefault(d["chave_recurso"], desc)

                        # Verificar equipe no nome
                        re_default = r'EQ\d+$'
                        re_match = re.search(re_default, items[d["chave_recurso"]])
                        if re_match:
                            kartado_measurement_reseource_record.equipe = re_match.group(0)[:30]
                        
                        # Equipe do lançamento
                        if d["prodc_equipe"]:
                            kartado_measurement_reseource_record.equipe = d["prodc_equipe"][:30]

            # Criar registro de log do kartado
            if d["log_codigo_relatorio"]:
                log_codigo = f"{d['log_codigo_relatorio']}"
                if log_codigo not in kartado_logs:
                    kartado_logs.append(log_codigo)
                    has_itens_data = True
                    kartado_measurement_log_record = kartado_measurement_record.append("tablog")
                    kartado_measurement_log_record.codigorelatorio = d["log_codigo_relatorio"]
                    kartado_measurement_log_record.uuidrelatorio = d["log_chave_relatorio"]
                    kartado_measurement_log_record.dataexecucao = d["log_data_execucao"].replace(' America/Sao_Paulo', '')
                    kartado_measurement_log_record.rodovia = d["log_nome_rodovia"]
                    kartado_measurement_log_record.kminicial = d["log_km_inicial"]
                    kartado_measurement_log_record.kmfinal = d["log_km_final"]
                    kartado_measurement_log_record.latitude = d["log_latitude"]
                    kartado_measurement_log_record.longitude = d["log_longitude"]
                    kartado_measurement_log_record.observacoes = d["log_notas_formulario_json"]
                    kartado_measurement_log_record.sentido = d["log_sentido"]
                    kartado_measurement_log_record.faixa = d["log_pista"]
                    kartado_measurement_log_record.rap = 0.0
                    if d["prodc_comprimento"]:
                        kartado_measurement_log_record.length = d["prodc_comprimento"]
                    if d["prodc_largura"]:
                        kartado_measurement_log_record.width = d["prodc_largura"]
                    if d["prodc_altura"]:
                        kartado_measurement_log_record.height = d["prodc_altura"]
                    if d["prodc_rap"]:
                        kartado_measurement_log_record.rap = d["prodc_rap"].replace('%', '')

                    if str_logs:
                        str_logs += ", "
                    str_logs += d["log_codigo_relatorio"]
                    if str_highways:
                        str_highways += ", "
                    str_highways += d["log_nome_rodovia"]

    # Salvar o registro de medição
    if has_itens_data:
        if items:
            kartado_measurement_record.item = get_items_code(items)
        kartado_measurement_record.relatorio = str_logs[0:30]
        kartado_measurement_record.rodovia = str_highways[0:30]
        kartado_measurement_record.save()

    save_integration_uuids(
        contract_name,
        contract_processing_date,
        contract_meaesurement,
        kartado_uuids,
        "Kartado"
    )

    # Escrever dados inconsistentes no banco de dados
    if inconsistent_data:
        s_inconsistency = ""
        s_inconsistency += f"Inconsistências:\n"
        for data in inconsistent_data:
            s_inconsistency += f"{data}\n"
        s_inconsistency += f"Chaves:\n"
        for key in inconsistent_keys:
            s_inconsistency += f"{key}\n"

        # Criar um registro de inconsistência do Kartado
        kartado_inconsistent = frappe.new_doc("Integration Inconsistency")
        kartado_inconsistent.boletimmedicao = contract_meaesurement
        kartado_inconsistent.tipo = "Kartado"
        kartado_inconsistent.dataehora = frappe.utils.now()
        kartado_inconsistent.observacoes = s_inconsistency
        kartado_inconsistent.save()

    # Registros de performance
    if data_performance and contract_meaesurement:
        measurement_doc = frappe.get_doc("Contract Measurement", contract_meaesurement)
        for p in data_performance:
            measurement_doc_performance = measurement_doc.append("tabperfm")
            measurement_doc_performance.datacriacao = p["data_criacao"].replace(' America/Sao_Paulo', '')
            measurement_doc_performance.dataexecucao = p["data_execucao"].replace(' America/Sao_Paulo', '')
            measurement_doc_performance.dataaprovacao = p["data_aprovacao"].replace(' America/Sao_Paulo', '')
            measurement_doc_performance.mediaponderada = p["nota_media_ponderada"]
            measurement_doc_performance.aprovadopor = p["aprovado_por_nome"]
            measurement_doc_performance.boletimkartado = p["boletim_medicao_numero"]
            measurement_doc_performance.save()
            kartado_performance_uuids.append(p["uuid"])
        
        save_integration_uuids(
            contract_name,
            contract_processing_date,
            contract_meaesurement,
            kartado_performance_uuids,
            "Kartado Performance"
        )
       
    if has_itens_data:
        return {
            "message": "Registro de Medição Kartado criado com sucesso.",
            "inconsistent_data": inconsistent_data
        }
    else:
        return {
            "message": "Nenhum item de kartado válido foi encontrado para criar um registro de medição.",
            "inconsistent_data": inconsistent_data
        }

def get_item_description(item: list):
    """
    Obtém a descrição do item do contrato.
    """
    get_description = ""
    get_description = frappe.db.get_value("Contract Item", item, "descricao") 
    return get_description

def get_items_code(items: list):
    """
    Obtém todos os códigos dos itens do contrato.
    """
    get_code = ""
    # Obter todos os itens do contrato do banco de dados
    for i in items:
        # Obter o código do kartado para cada item do contrato
        get_code += frappe.db.get_value("Contract Item", i, "codigo") + ", "
        get_code = get_code[:250]            
    return get_code.rstrip(", ")

@frappe.whitelist(methods=["GET"])
def get_list_log_to_attach_images():
    records = frappe.db.sql("""
        SELECT DISTINCT
            cmr.name AS measurement_record,
            cml.uuidrelatorio
        FROM
            `tabContract Measurement Record Log` cml
            INNER JOIN `tabContract Measurement Record` cmr ON cmr.name = cml.parent
            INNER JOIN `tabContract Measurement` cm ON cm.name = cmr.boletimmedicao
        WHERE
            cm.workflow_state = 'Aberto' AND 
            NOT cml.uuidrelatorio IS NULL AND 
            cmr.datahoraimagens IS NULL AND 
            cmr.origem_integracao LIKE '%Kartado%'
        ORDER BY
            cmr.name,
            cml.uuidrelatorio
    """, as_dict=True)

    get_images = {}
    for record in records:
        get_images.setdefault(record.measurement_record, {"uuids": []})
        get_images[record.measurement_record]["uuids"].append(record.uuidrelatorio)

    return get_images

@frappe.whitelist(methods=["GET"])
def get_list_log_without_uuid():
    records = frappe.db.sql("""
        SELECT DISTINCT
            codigorelatorio
        FROM
            `tabContract Measurement Record Log` cml
            INNER JOIN `tabContract Measurement Record` cmr ON cmr.name = cml.parent
            INNER JOIN `tabContract Measurement` cm ON cm.name = cmr.boletimmedicao
        WHERE
            cm.medicaovigente = 'Sim' AND 
            cml.uuidrelatorio IS NULL
    """, as_dict=True)
    return records

@frappe.whitelist(methods=["GET"])
def get_up():
    doc = frappe.get_doc("SMI Config")
    username = doc.kartado_usuario
    password = doc.get_password("kartado_senha")
    return {"username": username, "password": password}

@frappe.whitelist(methods=["POST"])
def update_log_without_uuid(report_code, report_uuid):
    records = frappe.db.sql("""
        UPDATE
            `tabContract Measurement Record Log` cml
        SET
            uuidrelatorio = %s
        WHERE
            codigorelatorio = %s
    """, (report_uuid, report_code), as_dict=True)

@frappe.whitelist(methods=["POST"])
def upload_image():
    try:
        image_uuid = str(uuid.uuid4())
        doctype = "Contract Measurement Record"
        reporting_id = frappe.form_dict.reporting_id
        record_name = frappe.form_dict.name
        file_64 = frappe.form_dict.data
        file_name = frappe.form_dict.filename.replace("FILENAME", image_uuid)
        has_gps = frappe.form_dict.has_gps
        gps_coords = frappe.form_dict.gps_coords

        upload_response = upload_file(doctype, record_name, file_64, file_name)

        doc = frappe.get_doc(doctype, record_name)
        doc.datahoraimagens = frappe.utils.now()
        doc_image = doc.append("tabimagens")
        doc_image.name = file_name
        doc_image.reportid = reporting_id
        doc_image.geotag = has_gps if has_gps else False
        if gps_coords:
            doc_image.longitude = gps_coords.get("longitude", 0.0) if gps_coords else 0.0
            doc_image.latitude = gps_coords.get("latitude", 0.0) if gps_coords else 0.0
        doc.save(ignore_permissions=True)
        frappe.db.commit()

        # Buscar todos os arquivos privados
        files = frappe.get_all("File", filters={"is_private": 1}, fields=["name"])
        # Alterar diretamente no banco
        for file in files:
            frappe.db.set_value("File", file.name, "is_private", 0)        
        frappe.db.commit()

        print(reporting_id)

        return upload_response

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "upload_image")
        return {"success": False, "message": str(e)}

@frappe.whitelist(methods=["GET"])
def get_measurement_images_list(measurement: str):
    """
    Obtém todas as imagens para um registro de medição.
    """
    # Obter todas as imagens do banco de dados
    images = frappe.db.sql("""  
        SELECT
            record.origem_integracao AS 'Origem da integração',
            DATE_FORMAT(record.dataexecucao, '%%d/%%m/%%Y %%H:%%i:%%s') AS 'Data da execução',
            log.codigorelatorio AS "Código do apontamento",
            log.latitude AS "Latitude",
            log.longitude AS "Longitude",
            log.rodovia AS "Rodovia",
            log.kminicial AS "Km inicial",
            log.kmfinal AS "Km final",
            log.via AS "Via",
            log.sentido AS "Sentido",
            f.file_url AS "URL da imagem",
            image.geotag AS "Geo Tag"
        FROM
            `tabContract Measurement Record Image` image
            INNER JOIN `tabContract Measurement Record` record ON record.name = image.parent
            INNER JOIN `tabContract Measurement Record Log` log ON log.uuidrelatorio = image.reportid
            INNER JOIN `tabFile` f ON f.file_name = image.name
        WHERE
            record.boletimmedicao=%s
        ORDER BY
            record.dataexecucao""", (measurement,), as_dict=True)

    return images

