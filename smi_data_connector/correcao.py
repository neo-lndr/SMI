import subprocess  # Corrigido: import correto
import requests
import json
import urllib3
import click
import sys
import os
from datetime import datetime
from kartado import create_kartado_measurement_records
from osiris import create_osiris_measurement_records
from typing import Literal

def custom_url(
        api_base_url: str, 
        api_token: str,
        params: dict = {},
        body: dict | str | None = None, 
        method: Literal["GET", "POST", "PUT", "DELETE"] = "GET", 
        timeout: int = 30):
    """
    Realiza uma requisição HTTP personalizada para a API do SMI Arteris.
    """
    try:
        resource_url = f"{api_base_url}"
        headers = {
            "Authorization": api_token,
            "Content-Type": "application/json",
        }

        # Configuração SSL
        verify_ssl = False
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        if body and not isinstance(body, dict):
            body = json.loads(body)

        # Executar requisição
        if method == "GET":
            response = requests.get(resource_url, headers=headers, params=params, 
                                  timeout=timeout, verify=verify_ssl)
        elif method == "POST":
            response = requests.post(resource_url, headers=headers, params=params,
                                   json=body, timeout=timeout, verify=verify_ssl)
        elif method == "PUT":
            response = requests.put(resource_url, headers=headers, params=params,
                                  json=body, timeout=timeout, verify=verify_ssl)
        elif method == "DELETE":
            response = requests.delete(resource_url, headers=headers, params=params,
                                     timeout=timeout, verify=verify_ssl)

        response.raise_for_status()
        return response.json()
    
    except requests.exceptions.RequestException as e:
        click.echo(f"❌ Erro na requisição HTTP: {e}", err=True)
        return None
    except Exception as e:
        click.echo(f"❌ Erro inesperado: {e}", err=True)
        return None

def get_measurement_data(measurement: str):
    url = f"https://smi.arteris.com.br/api/resource/Contract Measurement/{measurement}"
    params = {"limit_page_length": 0}

    dados_medicao = custom_url(
        api_base_url=url,
        api_token="token be2ff702de81b65:032e6f9ddc52aad",
        params=params,
        method="GET"
    )

    if not dados_medicao or 'data' not in dados_medicao:
        return None

    if dados_medicao['data'].get("workflow_state") != "Aberto":
        click.echo("⚠️  A medição não está no estado 'Aberto'. Operação cancelada.", fg='yellow')
        return None

    contrato = dados_medicao['data'].get("contrato")

    if not contrato:
        click.echo("❌ Contrato não encontrado na medição.", err=True)
        return None

    url = f"https://smi.arteris.com.br/api/resource/Contract/{contrato}"
    params = {"limit_page_length": 0}

    dados_contrato = custom_url(
        api_base_url=url,
        api_token="token be2ff702de81b65:032e6f9ddc52aad",
        params=params,
        method="GET"
    )

    if dados_medicao and 'data' in dados_medicao and dados_contrato and 'data' in dados_contrato:
        return {
            "contrato": dados_contrato['data'].get("contrato"),
            "datainicialmedicao": dados_medicao['data'].get("datainicialmedicao"),
            "datafinalmedicao": dados_medicao['data'].get("datafinalmedicao"),
            "workflow_state": dados_medicao['data'].get("workflow_state"),
            "uuidkartado": dados_contrato['data'].get("uuidkartado"),
            "uuidosiris": dados_contrato['data'].get("uuidosiris"),
        }
    return None

def delete_measurement(measurement: str):
    """Exclui uma medição"""
    url = f"https://smi.arteris.com.br/api/method/arteris_app.api.measurement.delete_measurement?measurement={measurement}"
    # url = f"http://development.localhost:8000/api/method/arteris_app.api.measurement.delete_measurement?measurement={measurement}"
    
    result = custom_url(
        api_base_url=url,
        api_token="token be2ff702de81b65:032e6f9ddc52aad",
        method="DELETE"
    )
    
    if result is not None:
        click.echo("✅ Medição excluída com sucesso!")
        return True
    else:
        click.echo("❌ Erro ao excluir medição.", err=True)
        return False

def create_measurement_records(data, sistema):
    """Cria registros de medição no sistema especificado"""
    try:
        if sistema == 'kartado':
            create_kartado_measurement_records(
                start_date=datetime.strptime(data['datainicialmedicao'], '%Y-%m-%d'),
                end_date=datetime.strptime(data['datafinalmedicao'], '%Y-%m-%d'),
                contract_code=data['contrato'],
                ignore_check=True,
                only_images=False
            )
        else:  # osiris
            create_osiris_measurement_records(
                start_date=datetime.strptime(data['datainicialmedicao'], '%Y-%m-%d'),
                end_date=datetime.strptime(data['datafinalmedicao'], '%Y-%m-%d'),
                contract_code=data['contrato'],
                ignore_check=True,
                only_images=False
            )
        
        click.echo(f"✅ Registros criados no {sistema.upper()}!")
        return True
        
    except Exception as e:
        click.echo(f"❌ Erro ao criar registros no {sistema}: {e}", err=True)
        return False

def run_engine_calculation(measurement: str):
    """Executa o cálculo do engine"""
    try:
        engine_path = "../msi_h_engine/run_h_engine.sh"
        
        # Verificar se o script existe
        if not os.path.exists(engine_path):
            click.echo(f"❌ Script do engine não encontrado: {engine_path}", err=True)
            return False
        
        # Executar o script
        click.echo("🔄 Iniciando cálculo do engine...")
        
        # Executar com output em tempo real
        process = subprocess.Popen(
            [engine_path, "measurement", measurement],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # Combinar stderr com stdout
            text=True,
            bufsize=1,  # Line buffered
            universal_newlines=True
        )
        
        # Exibir output em tempo real
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                click.echo(output.strip())
        
        # Aguardar conclusão
        return_code = process.wait(timeout=600)

        if return_code == 0:
            click.echo("✅ Cálculo concluído com sucesso!")
            return True
        else:
            click.echo(f"❌ Erro no cálculo (código {return_code})", err=True)
            return False
            
    except subprocess.TimeoutExpired:
        click.echo("⏱️  Timeout: Cálculo demorou mais que 5 minutos", err=True)
        return False
    except Exception as e:
        click.echo(f"❌ Erro ao executar engine: {e}", err=True)
        return False

@click.command()
@click.option('--measurement', '-m', 
              help='Código da medição')
def main(measurement):
    """
    Ferramenta de gerenciamento de medições SMI Arteris.
    
    Permite excluir, recarregar e recalcular medições.
    """
    
    if not measurement:
        measurement = click.prompt("Digite o código da medição", type=str)

    click.echo(f"\n📏 Medição: {click.style(measurement, fg='cyan', bold=True)}")
    
    with click.progressbar(length=1, label='🔍 Buscando dados da medição') as bar:
        data = get_measurement_data(measurement)
        bar.update(1)
    
    if not data:
        click.echo(f"\n❌ {click.style('Medição não encontrada ou não está no estado correto.', fg='red')}")
        click.echo("Verifique se o código está correto e se a medição está no estado 'Aberto'.")
        sys.exit(1)

    # Mostrar informações da medição
    click.echo(f"\n📋 {click.style('Informações da Medição:', fg='blue', bold=True)}")
    click.echo(f"   Contrato: {data['contrato']}")
    click.echo(f"   Período: {data['datainicialmedicao']} a {data['datafinalmedicao']}")
    click.echo(f"   Status: {data['workflow_state']}")
    
    sistema = "KARTADO" if data['uuidkartado'] else "OSIRIS"
    click.echo(f"   Sistema: {click.style(sistema, fg='magenta')}")

    # Seleção de ações
    opcoes = ['Excluir e recarregar', 'Recarregar', 'Recalcular']
    selecionadas = []

    click.echo(f"\n🎯 {click.style('Selecione as ações desejadas:', fg='yellow', bold=True)}")

    for opcao in opcoes:
        if click.confirm(f"   {opcao}?", default=False):
            selecionadas.append(opcao)

    if not selecionadas:
        click.echo("\n⚠️  Nenhuma ação selecionada. Finalizando...")
        sys.exit(0)

    click.echo(f"\n🚀 Ações selecionadas: {click.style(', '.join(selecionadas), fg='green', bold=True)}")

    # Confirmação final
    if not click.confirm(f"\n❓ Confirma a execução das ações selecionadas?", default=False):
        click.echo("❌ Operação cancelada pelo usuário.")
        sys.exit(0)

    # Executar ações
    sucesso_total = True
    
    for acao in selecionadas:
        click.echo(f"\n{'='*50}")
        click.echo(f"🔄 Executando: {click.style(acao, fg='cyan', bold=True)}")
        click.echo(f"{'='*50}")
        
        if acao == 'Excluir e recarregar':
            # Excluir
            if delete_measurement(measurement):
                # Recarregar
                click.echo("🔄 Recarregando medição...")
                sistema_tipo = 'kartado' if data['uuidkartado'] else 'osiris'
                
                if not create_measurement_records(data, sistema_tipo):
                    sucesso_total = False
            else:
                sucesso_total = False

        elif acao == 'Recarregar':
            click.echo("🔄 Recarregando medição...")
            sistema_tipo = 'kartado' if data['uuidkartado'] else 'osiris'
            
            if not create_measurement_records(data, sistema_tipo):
                sucesso_total = False

        elif acao == 'Recalcular':
            if not run_engine_calculation(measurement):
                sucesso_total = False

    # Resultado final
    click.echo(f"\n{'='*50}")
    if sucesso_total:
        click.echo(f"🎉 {click.style('Todas as operações foram concluídas com sucesso!', fg='green', bold=True)}")
    else:
        click.echo(f"⚠️  {click.style('Algumas operações falharam. Verifique os logs acima.', fg='yellow', bold=True)}")
    click.echo(f"{'='*50}")

if __name__ == "__main__":
    main()