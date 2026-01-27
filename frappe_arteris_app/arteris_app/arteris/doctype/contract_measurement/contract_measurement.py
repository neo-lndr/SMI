# apps/arteris_app/arteris/doctype/contract_measurement/contract_measurement.py

import frappe
from frappe.model.document import Document
from frappe.utils import flt
from frappe import throw, _
from arteris_app.api.measurement_workflow import approve_measurement, suspend_measurement_approvement
from arteris_app.api.adobesign import send_measurement_to_adobesign
from arteris_app.api.support import measurement_data_support, check_pending_process
from arteris_app.api.measurement import delete_measurement

class ContractMeasurement(Document):     

    @frappe.whitelist()
    def check_measurement(self):
        """
        Verifica pendências para a medição
        """
        start_year = 0
        try:
            start_year = self.datainicialmedicao.year
        except:
            start_year = self.datainicialmedicao[:4]
        end_year = 0
        try:
            end_year = self.datafinalmedicao.year
        except:
            end_year = self.datafinalmedicao[:4]

        # Itens sem pedido SAP
        items = frappe.db.sql("""
            WITH avulso AS (
                -- Lancamento avulso
                SELECT
                    contract_item.name AS item
                FROM
                    (
                        SELECT
                            cmr.apontamentodireto,
                            cmr.boletimmedicao,
                            sap_period.name AS pedidolinha
                        FROM
                            `tabContract Measurement Record` cmr
                            INNER JOIN `tabContract Measurement Note` cmn ON cmn.name = cmr.apontamentodireto
                            INNER JOIN `tabContract Measurement Note SAP Order` cmso ON cmso.parent = cmn.name
                            INNER JOIN `tabSAP Order Period` sap_period ON sap_period.name = cmso.pedidolinha
                            INNER JOIN `tabSAP Order` sap_order ON sap_order.name = sap_period.parent
                        WHERE
                            cmr.boletimmedicao=%(measurement)s
                    ) AS note
                    INNER JOIN `tabContract Measurement Note Resource` cmnr ON cmnr.parent = note.apontamentodireto
                    INNER JOIN `tabContract Item` contract_item ON contract_item.name = cmnr.item
                    INNER JOIN `tabContract Measurement Item` cm_item ON cm_item.itemcontrato = contract_item.name
                    AND cm_item.parent = note.boletimmedicao
            ), linha_vinculada AS (
                -- Linha de pedido vinculada ao item
                SELECT
                    contract_item.name AS item
                FROM
                    `tabContract Item` contract_item
                    INNER JOIN `tabContract Item Order` item_order ON contract_item.name = item_order.parent
                    INNER JOIN `tabSAP Order Period` sap_period ON sap_period.name = item_order.pedidolinha
                    INNER JOIN `tabSAP Order` sap_order ON sap_order.name = sap_period.parent
                    INNER JOIN `tabContract Measurement Item` cm_item ON cm_item.itemcontrato = contract_item.name
                WHERE
                    NOT item_order.pedidolinha IS NULL AND
                    NOT cm_item.valorpago = 0 AND
                    sap_period.saldo > 0 AND
                    sap_order.faturamentodireto = 0 AND
                    cm_item.parent = %(measurement)s AND
                    contract_item.contrato = %(contract)s AND
                    NOT sap_period.name IN (SELECT pedidolinha FROM avulso)
                UNION ALL
                SELECT
                    item
                FROM
                    avulso
            ), pep_vinculado AS (
                -- PEP da linha do pedido com PEP do item
                SELECT
                    contract_item.name AS item
                FROM
                    `tabContract Item` contract_item
                    INNER JOIN `tabContract Item Order` item_order ON contract_item.name = item_order.parent AND
                                                                    item_order.pedidolinha IS NULL
                    INNER JOIN `tabSAP Order Period` sap_period ON sap_period.parent = item_order.pedidosap AND
                                                                YEAR(sap_period.datainicial) <= %(start_year)s AND
                                                                YEAR(sap_period.datafinal) >= %(end_year)s AND
                                                                sap_period.pep = contract_item.codigopep
                    INNER JOIN `tabSAP Order` sap_order ON sap_order.name = sap_period.parent
                    INNER JOIN `tabContract Measurement Item` cm_item ON cm_item.itemcontrato = contract_item.name
                WHERE
                    contract_item.is_group = 0 AND
                    NOT cm_item.valorpago = 0 AND
                    sap_period.saldo > 0 AND
                    sap_order.faturamentodireto = 0 AND
                    cm_item.parent = %(measurement)s AND
                    contract_item.contrato = %(contract)s AND
                    NOT sap_period.name IN (SELECT pedidolinha FROM linha_vinculada)
                UNION ALL
                SELECT
                    item
                FROM
                    linha_vinculada
            ), pedido_vinculado AS (
                -- Apenas pedido vinculado, porem sem PEP ou linha vincualda ao item
                SELECT
                    contract_item.name AS item
                FROM
                    `tabContract Item` contract_item
                    INNER JOIN `tabContract Item Order` item_order ON contract_item.name = item_order.parent AND
                                                                    item_order.pedidolinha IS NULL
                    INNER JOIN `tabSAP Order Period` sap_period ON sap_period.parent = item_order.pedidosap AND
                                                                YEAR(sap_period.datainicial) <= %(start_year)s AND
                                                                YEAR(sap_period.datafinal) >= %(end_year)s
                    INNER JOIN `tabSAP Order` sap_order ON sap_order.name = sap_period.parent
                    INNER JOIN `tabContract Measurement Item` cm_item ON cm_item.itemcontrato = contract_item.name
                WHERE
                    contract_item.is_group = 0 AND
                    NOT cm_item.valorpago = 0 AND
                    sap_period.saldo > 0 AND
                    sap_order.faturamentodireto = 0 AND
                    cm_item.parent = %(measurement)s AND
                    contract_item.contrato = %(contract)s AND
                    NOT sap_period.name IN (SELECT pedidolinha FROM pep_vinculado)
                UNION ALL
                SELECT
                    item
                FROM
                    pep_vinculado
            ), nenhum_vinculo AS (
                -- Nenhum vinculo, pesquisa linhas para o contrato
                SELECT
                    contract_item.name AS item
                FROM `tabContract Item` contract_item
                    INNER JOIN `tabSAP Order Period` sap_period ON sap_period.contrato = contract_item.contrato AND
                                                                    YEAR(sap_period.datainicial) <= %(start_year)s AND
                                                                    YEAR(sap_period.datafinal) >= %(end_year)s
                    INNER JOIN `tabSAP Order` sap_order ON sap_order.name = sap_period.parent
                    INNER JOIN `tabContract Measurement Item` cm_item ON cm_item.itemcontrato = contract_item.name
                    LEFT JOIN `tabContract Item Order` item_order ON contract_item.name = item_order.parent
                WHERE
                    contract_item.is_group = 0
                    AND item_order.name IS NULL
                    AND item_order.pedidolinha IS NULL
                    AND NOT cm_item.valorpago = 0
                    AND sap_period.saldo > 0
                    AND sap_order.faturamentodireto = 0
                    AND cm_item.parent = %(measurement)s
                    AND contract_item.contrato = %(contract)s
                    AND NOT sap_period.name IN (SELECT pedidolinha FROM pedido_vinculado)
                UNION ALL
                SELECT
                    item
                FROM
                    pedido_vinculado
            ), items AS (
                SELECT
                    item
                FROM
                    nenhum_vinculo
            )
            SELECT
                ci.codigo,
                ci.descricao,
                cmi.valorpago
            FROM
                `tabContract Measurement Item` cmi
                INNER JOIN `tabContract Item` ci ON cmi.itemcontrato = ci.name
            WHERE
                cmi.parent = %(measurement)s AND
                NOT ci.name IN (SELECT item FROM items) AND
                cmi.valorpago > 0
            """,
                        {
                'start_year': start_year,
                'end_year': end_year,
                'measurement': self.name,
                'contract': self.contrato
            }, as_dict=True)

        items_total = {}
        for item in items:
            if not item.codigo in items_total:
                items_total[item.codigo] = {
                    "codigo": item.codigo,
                    "descricao": item.descricao,
                    "valorpago": item.valorpago,
                    "pedido_sap": 0
                }
        items_sem_pedido = [item for item in items_total.values()]   

        # Mão de obra orfã
        wks = frappe.db.sql("""
            SELECT
                wk.funcao,
                ci.codigo,
                ci.descricao
            FROM
                `tabContract Measurement Record` cmr 
                INNER JOIN `tabContract Measurement Record Work Role` cmrwr ON cmr.name = cmrwr.parent
                INNER JOIN `tabContract Item` ci ON ci.name = cmrwr.item
                INNER JOIN `tabWork Role` wk ON wk.name = cmrwr.funcao
                LEFT JOIN `tabContract Measurement Work Role` cmwr ON cmwr.funcao = cmrwr.funcao AND
                                                                      cmwr.item = cmrwr.item
            WHERE
                cmr.boletimmedicao = %s
            GROUP BY
                wk.funcao,
                ci.codigo,
                ci.descricao
            HAVING 
                COUNT(cmwr.item) = 0""",
            (self.name,), as_dict=True)

        mao_de_obra_orfa = []
        for wk in wks:
            mao_de_obra_orfa.append({
                "funcao": wk.funcao,
                "codigo": wk.codigo,
                "descricao": wk.descricao
            })

        # Ativo orfão
        assets = frappe.db.sql("""
            SELECT
                asset.nomeativo,
                ci.codigo,
                ci.descricao
            FROM
                `tabContract Measurement Record` cmr 
                INNER JOIN `tabContract Measurement Record Asset` cmra ON cmr.name = cmra.parent
                INNER JOIN `tabContract Item` ci ON ci.name = cmra.item
                INNER JOIN `tabAsset` asset ON asset.name = cmra.maquina_equipamento_ou_ferramenta
                LEFT JOIN `tabContract Measurement Asset` cma ON cma.maquina_equipamento_ou_ferramenta = cmra.maquina_equipamento_ou_ferramenta AND 
                                                          cma.item = cmra.item
            WHERE
                cmr.boletimmedicao = %s
            GROUP BY
                asset.nomeativo,
                ci.codigo,
                ci.descricao
            HAVING
                COUNT(cma.name) = 0
        """, 
        (self.name ,), 
        as_dict=True)

        ativo_orfao = []
        for asset in assets:
            ativo_orfao.append({
                "ativo": asset.nomeativo,
                "codigo": asset.codigo,
                "descricao": asset.descricao
            })

        cities = frappe.db.sql("""
            SELECT
                cidade
            FROM
                `tabContract`
            WHERE
                name = %s
        """,
        (self.contrato,), as_dict=True)

        cidades = []
        if cities:
            if not cities[0].cidade:
                cidades.append("Cidade base não informada no contrato.")
            
        cities = frappe.db.sql("""
            WITH t_cities AS (
                SELECT
                    cmr.name AS record_name,
                    cmrl.cidade_name  AS cidade
                FROM
                    `tabContract Measurement Record` cmr
                    INNER JOIN `tabContract Measurement Record Log` cmrl ON cmr.name = cmrl.parent
                WHERE
                    cmr.boletimmedicao = %(measurement)s
                    AND NOT cmrl.cidade_name IS NULL
                    AND NOT cmrl.rodovia_name IS NULL
            ), t_items AS (
                SELECT
                    t_cities.cidade,
                    cmwk.item
                FROM
                    t_cities
                    INNER JOIN `tabContract Measurement Record` cmr ON t_cities.record_name = cmr.name
                    INNER JOIN `tabContract Measurement Record Work Role` cmrwk ON cmr.name = cmrwk.parent
                    LEFT JOIN `tabContract Measurement Work Role` cmwk ON cmwk.item = cmrwk.item AND
                                                                        cmwk.funcao = cmrwk.funcao AND
                                                                        cmwk.parent = cmr.boletimmedicao
                    LEFT JOIN `tabContract Measurement Item` cmi ON cmwk.item = cmi.itemcontrato AND
                                                                    cmi.parent = cmr.boletimmedicao
                    LEFT JOIN `tabContract Item` ci ON ci.name = cmrwk.item
                WHERE
                    NOT cmi.valorpago = 0
                UNION ALL
                SELECT
                    t_cities.cidade,
                    cma.item
                FROM
                    t_cities
                    INNER JOIN `tabContract Measurement Record` cmr ON t_cities.record_name = cmr.name
                    INNER JOIN `tabContract Measurement Record Asset` cmra ON cmr.name = cmra.parent
                    LEFT JOIN `tabContract Measurement Asset` cma ON cma.item = cmra.item AND
                                                                    cma.maquina_equipamento_ou_ferramenta =
                                                                    cmra.maquina_equipamento_ou_ferramenta AND
                                                                    cma.parent = cmr.boletimmedicao
                    LEFT JOIN `tabContract Measurement Item` cmi ON cma.item = cmi.itemcontrato AND
                                                                    cmi.parent = cmr.boletimmedicao
                    LEFT JOIN `tabContract Item` ci ON ci.name = cmra.item
                WHERE
                    cmi.valorpago > 0
                UNION ALL
                SELECT
                    t_cities.cidade,
                    cmrr.item
                FROM
                    t_cities
                    INNER JOIN `tabContract Measurement Record` cmr ON t_cities.record_name = cmr.name
                    INNER JOIN `tabContract Measurement Record Resource` cmrr ON cmr.name = cmrr.parent
                    LEFT JOIN `tabContract Measurement Item` cmi ON cmrr.item = cmi.itemcontrato AND
                                                                    cmi.parent = cmr.boletimmedicao
                    LEFT JOIN `tabContract Item` ci ON ci.name = cmrr.item
                WHERE
                    NOT cmi.valorpago = 0
            ), t_geral AS (
                SELECT
                    CASE
                        WHEN IFNULL(item.cidade, '') = '' THEN COALESCE(contract.cidade, '')
                        ELSE COALESCE(item.cidade, '')
                    END AS cidade,
                    item.name AS item
                FROM
                    `tabContract Item` item
                    INNER JOIN `tabContract` contract ON item.contrato = contract.name
                    INNER JOIN `tabContract Measurement` cm ON cm.contrato = contract.name
                    INNER JOIN `tabContract Measurement Item` cm_item ON item.name = cm_item.itemcontrato AND
                                                                        cm_item.parent = cm.name
                WHERE
                    cm.name = %(measurement)s
                    AND NOT cm_item.valorpago = 0
                    AND NOT (cm_item.itemcontrato IN (SELECT item FROM t_items))
                UNION ALL
                SELECT
                    cidade,
                    item
                FROM
                    t_items)
            SELECT
                cidade,
                item
            FROM
                t_geral
            WHERE 
                NOT cidade IS NULL""",
        {"measurement": self.name,}, as_dict=True)        

        if len(cities) == 0 and not self.medicaoatual == 0:
            cidades.append("Nenhuma cidade informada nos registros de medição para itens com valor pago diferente de R$ 0.00, verifique registros de apontamento, cidade base no contrato e cidade base nos itens contratuais.")

        return {
            "items_sem_pedido": items_sem_pedido, 
            "mao_de_obra_orfa": mao_de_obra_orfa,
            "ativo_orfao": ativo_orfao,
            "cidades": cidades
        }
    
    @frappe.whitelist()
    def vincular_municipios(self):
        # 1) só em medições vigentes
        if self.medicaovigente != 'Sim':
            throw(_('Só é possível vincular municípios em medições vigentes.'))

        # 2) limpa a tabela antes de povoar
        self.set('tablemunicipios', [])

        # 3) carrega todos os apontamentos (CMR) deste boletim
        cm_records = frappe.get_all(
            'Contract Measurement Record',
            filters={'boletimmedicao': self.name},
            pluck='name'
        )
        if not cm_records:
            throw(_('Nenhum apontamento encontrado para este boletim.'))

        # 4) coleta todos os logs e soma extensão total
        total_ext = 0.0
        logs = []
        for rec_name in cm_records:
            rec = frappe.get_doc('Contract Measurement Record', rec_name)
            for log in rec.get('tablog') or []:
                start = flt(log.kminicial)
                end   = flt(log.kmfinal)
                if end > start:
                    total_ext += (end - start)
                    logs.append({
                        'rec':      rec_name,
                        'rodovia':  log.rodovia,
                        'start':    start,
                        'end':      end,
                        'items':    (rec.item or '').split(',')
                    })
        if total_ext <= 0:
            throw(_('Não há extensão válida nos logs para cálculo.'))

        # 5) acumula extensão por cidade
        city_lengths = {}
        for entry in logs:
            rec_name = entry['rec']
            rod      = entry['rodovia']
            start    = entry['start']
            end      = entry['end']
            length   = end - start

            # função auxiliar para processar um rodovia + segmento
            def process_rodovia_segment(rodovia, seg_start, seg_end):
                # busca highways via de-para
                hw_names = frappe.get_all('Highway',
                    filters=[['tabconfigdepararodovia','rodovia','=', rodovia]],
                    pluck='name'
                )
                if not hw_names:
                    frappe.log(f'[vincular_municipios] Record {rec_name}: rodovia "{rodovia}" não encontrada em Highway')
                    return
                for hw_name in hw_names:
                    hw = frappe.get_doc('Highway', hw_name)
                    for hc in hw.get('cidades') or []:
                        c_start = flt(hc.kminicial)
                        c_end   = flt(hc.kmfinal)
                        ov_start = max(seg_start, c_start)
                        ov_end   = min(seg_end,   c_end)
                        overlap_len = max(0.0, ov_end - ov_start)
                        # log de prova real
                        frappe.log(
                            f'[vincular_municipios] Rec:{rec_name} | Rodovia:{rodovia} | '
                            f'Apont:{seg_start}-{seg_end} | Cidade:{hc.cidade} | '
                            f'Cidade km:{c_start}-{c_end} | Overlap km:{overlap_len}'
                        )
                        if overlap_len > 0:
                            city_lengths[hc.cidade] = city_lengths.get(hc.cidade, 0.0) + overlap_len

            if rod:
                # caso normal: rodovia informada
                process_rodovia_segment(rod, start, end)

            elif entry['items'] and entry['items'] != ['']:
                # fallback 1: sem rodovia, processar via itens contratuais
                # percorre os itens do apontamento
                for item_code in entry['items']:
                    item_code = item_code.strip()
                    if not item_code:
                        continue
                    # busca Contract Items deste contrato
                    itens = frappe.get_all('Contract Items',
                        filters={
                            'name': item_code,
                            'contrato': self.name
                        },
                        pluck='name'
                    )
                    for ci_name in itens:
                        ci = frappe.get_doc('Contract Items', ci_name)
                        # para cada rodovia configurada no item
                        for ir in ci.get('rodovias') or []:
                            process_rodovia_segment(ir.rodovia, ir.kminicial, ir.kmfinal)

            else:
                # fallback 2: sem rodovia e itens, usar cidade única do contrato
                city = self.cidade
                overlap_len = length
                frappe.log(
                    f'[vincular_municipios] Rec:{rec_name} | Sem rodovia/itens | '
                    f'Apont:{start}-{end} | Usando cidade contrato:{city} | '
                    f'Overlap km:{overlap_len}'
                )
                city_lengths[city] = city_lengths.get(city, 0.0) + overlap_len

        # 6) grava na child table sem duplicar
        existing = { d.municipio: d for d in self.get('tablemunicipios') }
        for city, length in city_lengths.items():
            pct = flt((length / total_ext) * 100.0, 2)
            if city in existing:
                existing[city].participacao = pct
            else:
                self.append('tablemunicipios', {
                    'municipio':    city,
                    'participacao': pct
                })

        # 7) salva tudo de uma vez
        self.save(ignore_permissions=True)
        return True

    def approve(self, doc):
        approve_measurement(doc)

    def send_to_sign(self, doc):
        send_measurement_to_adobesign(doc)

    def suspend_approvement(self, doc):
        suspend_measurement_approvement(doc)

    @frappe.whitelist()
    def check_contract(self):
        contract = frappe.db.get_value("Contract", self.contrato, "grupoformulas")
        if not contract:
            return _('Contrato sem grupo de fórmulas definido.')
        
@frappe.whitelist()
def reload(measurement):
    """
    Função para executar reload_measurement em background
    
    Args:
        measurement: Código da medição
    """

    if check_pending_process():
        return {"success": False, "error": "Já existe um processo de recarregamento ou recálculo em andamento. Aguarde a conclusão deste processo antes de iniciar outro."}

    try:
        measurement_support = measurement_data_support(measurement)
        result = measurement_support.reload_measurement()
        
        # Log do resultado
        frappe.logger().info(f"Reload measurement {measurement} concluído: {result}")
        
        return {"success": True}
    except Exception as e:
        frappe.log_error(f"Falha ao recarregar medição {measurement}: {e}" )
        return {"success": False, "measurement": measurement, "error": str(e)}

@frappe.whitelist()
def recalculate(measurement):
    """
    Função para executar recalculate_measurement em background
    """

    if check_pending_process():
        return {"success": False, "error": "Já existe um processo de recarregamento ou recálculo em andamento. Aguarde a conclusão deste processo antes de iniciar outro."}

    try:
        measurement_support = measurement_data_support(measurement)
        result = measurement_support.recalculate_measurement()
        
        frappe.logger().info(f"Recalculate measurement {measurement} concluído: {result}")

        return {"success": True}
    except Exception as e:
        frappe.log_error(f"Falha ao recalcular medição {measurement}: {e}")
        return {"success": False, "measurement": measurement, "error": str(e)}

@frappe.whitelist()
def delete(measurement):
    """
    Exclui os dados da medição
    """
    delete_measurement(measurement)
    frappe.delete_doc('Contract Measurement', measurement)


