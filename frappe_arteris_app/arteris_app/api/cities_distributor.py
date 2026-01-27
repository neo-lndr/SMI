import ast
from collections import defaultdict
from typing import List, Dict, Any, Tuple
import json

def carregar_dados(arquivo: str) -> List[Dict[str, Any]]:
    """Carrega os dados do arquivo (formato Python literal)."""
    with open(arquivo, 'r') as f:
        content = f.read()
        return ast.literal_eval(content)

def distribuir_valor_proporcional(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Distribui o valor pago do item proporcionalmente entre suas cidades
    baseado no measured_value de cada cidade.
    """
    paid_value = item['paid_value']
    cities = item['cities']

    # Calcula a soma total dos measured_values
    total_measured = sum(abs(city['measured_value']) for city in cities)

    # Se não há valor medido ou é zero, distribui igualmente
    if total_measured == 0:
        distributed_value = paid_value / len(cities) if len(cities) > 0 else 0
        for city in cities:
            city['distributed_value'] = distributed_value
    else:
        # Distribui proporcionalmente baseado no valor absoluto
        for city in cities:
            proportion = abs(city['measured_value']) / total_measured
            city['distributed_value'] = paid_value * proportion

    return item

def consolidar_valores_por_cidade(items: List[Dict[str, Any]]) -> Dict[str, float]:
    """
    Consolida todos os valores distribuídos por cidade.
    """
    cidade_valores = defaultdict(float)

    for item in items:
        for city in item['cities']:
            city_name = city['city']
            cidade_valores[city_name] += city.get('distributed_value', 0)

    return dict(cidade_valores)

def redistribuir_valores_negativos(items: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], bool]:
    """
    Redistribui valores de cidades negativas entre as positivas.
    Retorna os itens ajustados e um booleano indicando se houve redistribuição.
    """
    # Primeiro consolida os valores por cidade
    cidade_valores = consolidar_valores_por_cidade(items)

    # Separa cidades positivas e negativas
    cidades_positivas = {c: v for c, v in cidade_valores.items() if v > 0}
    cidades_negativas = {c: v for c, v in cidade_valores.items() if v < 0}

    if not cidades_negativas:
        return items, False

    # Se todas as cidades têm valor negativo, zera todos os valores
    if not cidades_positivas:
        print("\nAVISO: Todas as cidades têm valores negativos. Zerando todos os valores distribuídos.")
        for item in items:
            for city in item['cities']:
                city['distributed_value'] = 0
        return items, True

    # Calcula o total negativo para redistribuir
    total_negativo = sum(cidades_negativas.values())
    total_positivo = sum(cidades_positivas.values())

    print(f"\nRedistribuindo R$ {abs(total_negativo):,.2f} das cidades negativas para as positivas")
    print(f"Cidades negativas ({len(cidades_negativas)}): {', '.join(cidades_negativas.keys())}")
    print(f"Cidades positivas ({len(cidades_positivas)}): {', '.join(cidades_positivas.keys())}")

    # Calcula o fator de redistribuição para cada cidade
    # Cada cidade receberá uma parte proporcional do valor negativo total
    fatores_redistribuicao = {}

    # Para cidades positivas: adiciona proporcionalmente o valor negativo
    for cidade in cidades_positivas:
        proporcao = cidades_positivas[cidade] / total_positivo
        valor_adicional = abs(total_negativo) * proporcao
        fatores_redistribuicao[cidade] = (cidades_positivas[cidade] + valor_adicional) / cidades_positivas[cidade]

    # Para cidades negativas: zera o valor
    for cidade in cidades_negativas:
        fatores_redistribuicao[cidade] = 0

    # Aplica os fatores de redistribuição
    for item in items:
        for city in item['cities']:
            city_name = city['city']
            if city_name in fatores_redistribuicao:
                city['distributed_value'] = city.get('distributed_value', 0) * fatores_redistribuicao[city_name]

    return items, True

def validar_distribuicao(items: List[Dict[str, Any]]) -> bool:
    """
    Valida que a soma dos valores distribuídos é igual à soma dos valores pagos.
    Retorna True se a validação passou.
    """
    soma_paid = sum(item['paid_value'] for item in items)
    soma_distributed = sum(
        city.get('distributed_value', 0)
        for item in items
        for city in item['cities']
    )

    print("VALIDAÇÃO FINAL:")
    print(f"Soma total dos valores pagos (paid_value): R$ {soma_paid:,.2f}")
    print(f"Soma total dos valores distribuídos: R$ {soma_distributed:,.2f}")
    print(f"Diferença: R$ {abs(soma_paid - soma_distributed):,.2f}")

    validacao_ok = abs(soma_paid - soma_distributed) < 0.01
    print(f"Valores conferem? {'✓ SIM' if validacao_ok else '✗ NÃO'}")

    return (abs(soma_paid - soma_distributed) < 0.01)

def gerar_relatorio_detalhado(items: List[Dict[str, Any]], arquivo_saida: str = "relatorio_detalhado.txt"):
    """
    Gera um relatório detalhado da distribuição.
    """
    with open(arquivo_saida, 'w', encoding='utf-8') as f:
        f.write("="*80 + "\n")
        f.write("RELATÓRIO DETALHADO DA DISTRIBUIÇÃO DE VALORES\n")
        f.write("="*80 + "\n\n")

        # Resumo geral
        soma_paid = sum(item['paid_value'] for item in items)
        f.write(f"Total de itens: {len(items)}\n")
        f.write(f"Soma total dos valores pagos: R$ {soma_paid:,.2f}\n\n")

        # Detalhamento por item
        f.write("DETALHAMENTO POR ITEM:\n")
        f.write("-"*80 + "\n")

        for i, item in enumerate(items, 1):
            f.write(f"\n{i}. Item: {item['item']}\n")
            f.write(f"   Valor pago: R$ {item['paid_value']:,.2f}\n")
            f.write(f"   Cidades ({len(item['cities'])}):\n")

            for city in item['cities']:
                f.write(f"      - {city['city']:30s} ")
                f.write(f"Medido: R$ {city['measured_value']:12,.2f} ")
                f.write(f"Distribuído: R$ {city.get('distributed_value', 0):12,.2f}\n")

            # Verifica se a distribuição está correta para este item
            soma_dist = sum(c.get('distributed_value', 0) for c in item['cities'])
            if abs(soma_dist - item['paid_value']) > 0.01:
                f.write(f"AVISO: Diferença na distribuição: R$ {abs(soma_dist - item['paid_value']):,.2f}\n")

        # Resumo por cidade
        f.write("RESUMO POR CIDADE:\n")

        cidade_totais = consolidar_valores_por_cidade(items)
        for cidade, valor in sorted(cidade_totais.items(), key=lambda x: x[1], reverse=True):
            f.write(f"{cidade:35s} R$ {valor:15,.2f}\n")

        f.write("-"*80 + "\n")
        f.write(f"{'TOTAL':35s} R$ {sum(cidade_totais.values()):15,.2f}\n")

    print(f"\nRelatório detalhado salvo em: {arquivo_saida}")

def processar_distribuicao(items: dict) -> List[Dict[str, Any]]:
    """
    Processa toda a distribuição de valores.
    """
    print("INICIANDO PROCESSAMENTO DE DISTRIBUIÇÃO DE VALORES")

    # Análise inicial
    soma_inicial = sum(item['paid_value'] for item in items)
    print(f"Soma inicial dos paid_values: R$ {soma_inicial:,.2f}")

    print("\nDistribuindo valores proporcionalmente...")
    for item in items:
        distribuir_valor_proporcional(item)
    print("Distribuição proporcional concluída")

    print("\nConsolidando valores por cidade...")
    cidade_valores = consolidar_valores_por_cidade(items)
    print(f"{len(cidade_valores)} cidades únicas encontradas")

    # Mostra resumo das cidades
    print("\nResumo por cidade (ANTES do ajuste):")
    cidades_negativas = []
    for cidade, valor in sorted(cidade_valores.items(), key=lambda x: x[1], reverse=True):
        status = "OK" if valor >= 0 else "NEGATIVO"
        print(f"{cidade:30s}: R$ {valor:15,.2f} {status}")
        if valor < 0:
            cidades_negativas.append(cidade)

    print("\nVerificando cidades com valores negativos...")
    if cidades_negativas:
        print(f"Encontradas {len(cidades_negativas)} cidades com valores negativos")
        items, houve_redistribuicao = redistribuir_valores_negativos(items)

        if houve_redistribuicao:
            # Recalcula para validação
            cidade_valores = consolidar_valores_por_cidade(items)
            print("\nResumo APÓS redistribuição:")
            for cidade, valor in sorted(cidade_valores.items(), key=lambda x: x[1], reverse=True):
                print(f"{cidade:30s}: R$ {valor:15,.2f}")
    else:
        print("Nenhuma cidade com valor negativo encontrada")

    print("\nValidando distribuição...")
    validacao_ok = validar_distribuicao(items)

    if not validacao_ok:
        print("\nAVISO: A validação falhou, mas o processamento continuará.")

    return items

# def salvar_resultado(items: List[Dict[str, Any]], arquivo_saida: str) -> None:
#     """
#     Salva o resultado processado em um arquivo JSON.
#     """
#     with open(arquivo_saida, 'w', encoding='utf-8') as f:
#         json.dump(items, f, indent=2, ensure_ascii=False)
#     print(f"\n💾 Resultado salvo em: {arquivo_saida}")

# def main():
#     """
#     Função principal que executa todo o processamento.
#     """
#     # Processa a distribuição
#     items_processados = processar_distribuicao("dados.json")

#     # Salva o resultado em JSON
#     salvar_resultado(items_processados, "resultado_distribuicao.json")

#     # Gera relatório detalhado
#     gerar_relatorio_detalhado(items_processados, "relatorio_distribuicao.txt")

#     # Cria um resumo por cidade
#     print("\n" + "="*70)
#     print("📊 RESUMO FINAL POR CIDADE")
#     print("="*70)

#     cidade_totais = consolidar_valores_por_cidade(items_processados)
#     total_geral = 0

#     for cidade, valor in sorted(cidade_totais.items(), key=lambda x: x[1], reverse=True):
#         print(f"{cidade:35s} R$ {valor:15,.2f}")
#         total_geral += valor

#     print("-"*70)
#     print(f"{'TOTAL GERAL':35s} R$ {total_geral:15,.2f}")
#     print("="*70)

#     # Verifica se o total está correto
#     if abs(total_geral - 3687418.15) < 0.01:
#         print("\n✅ SUCESSO: Distribuição concluída com o valor correto!")
#     else:
#         print(f"\n⚠️ AVISO: Valor total ({total_geral:,.2f}) difere do esperado (3,687,418.15)")


# """
# Módulo FINAL para distribuição proporcional de valores entre cidades
# Versão de produção com OOP e correção do bug de duplicação
# Garante que a soma total distribuída seja EXATAMENTE igual à soma dos paid_values
# """

# from typing import List, Dict
# import copy


# class GlobalValueDistributor:
#     """
#     Distribuidor de valores com restrições globais CORRIGIDO.

#     Regras:
#     1. Se soma global dos paid_values ≤ 0: todas as cidades recebem 0
#     2. Se soma global > 0: distribui proporcionalmente
#     3. A SOMA TOTAL distribuída deve ser EXATAMENTE igual à soma dos paid_values
#     """

#     def __init__(self, max_iterations: int = 10, debug: bool = True):
#         self.max_iterations = max_iterations
#         self.debug = debug

#     def distribute(self, data: List[Dict]) -> List[Dict]:
#         """
#         Distribui valores garantindo que a soma total seja exata.
#         """
#         result = copy.deepcopy(data)

#         # Calcula soma global dos paid_values
#         global_sum = sum(item["paid_value"] for item in result)

#         if self.debug:
#             print(f"\n{'='*60}")
#             print(f"Global sum of paid values: ${global_sum:,.2f}")
#             print(f"{'='*60}")

#         if global_sum <= 0:
#             return self._apply_zero_distribution(result, global_sum)

#         # Distribui proporcionalmente SEM ajustes que alterem a soma total
#         return self._apply_simple_distribution(result)

#     def _apply_zero_distribution(self, data: List[Dict], global_sum: float) -> List[Dict]:
#         """Aplica distribuição zero quando soma global ≤ 0"""
#         if self.debug:
#             print("\n⚠️  Global sum ≤ 0: All cities receive ZERO")

#         for item in data:
#             for city in item["cities"]:
#                 city["distributed_value"] = 0
#                 city["final_value"] = city["measured_value"]

#             item["distributed_sum"] = 0
#             item["difference"] = item["paid_value"]

#         return data

#     def _apply_simple_distribution(self, data: List[Dict]) -> List[Dict]:
#         """
#         Aplica distribuição proporcional simples SEM alterar a soma total.
#         Cada item distribui seu paid_value proporcionalmente entre suas cidades.
#         """
#         if self.debug:
#             print("\n✅ Applying proportional distribution...")

#         total_distributed_check = 0

#         for item in data:
#             paid_value = item["paid_value"]
#             cities = item["cities"]

#             # Calcula soma absoluta dos measured_values para proporção
#             total_absolute = sum(abs(c["measured_value"]) for c in cities)

#             if total_absolute == 0:
#                 # Distribui igualmente se não há valores medidos
#                 value_per_city = paid_value / len(cities) if cities else 0
#                 for city in cities:
#                     city["distributed_value"] = value_per_city
#             else:
#                 # Distribui proporcionalmente baseado no valor absoluto
#                 accumulated = 0
#                 for i, city in enumerate(cities):
#                     if i == len(cities) - 1:
#                         # Última cidade recebe o restante (evita erro de arredondamento)
#                         city["distributed_value"] = paid_value - accumulated
#                     else:
#                         proportion = abs(city["measured_value"]) / total_absolute
#                         city["distributed_value"] = round(paid_value * proportion, 2)
#                         accumulated += city["distributed_value"]

#             # Calcula valores finais e metadados
#             item_sum = 0
#             for city in cities:
#                 city["final_value"] = city["measured_value"] + city["distributed_value"]
#                 item_sum += city["distributed_value"]

#             item["distributed_sum"] = round(item_sum, 2)
#             item["difference"] = round(paid_value - item_sum, 2)

#             total_distributed_check += item_sum

#         # Verifica se há cidades com soma total negativa
#         if self.debug:
#             city_totals = self._calculate_city_totals(data)
#             print("\nCity totals after distribution:")
#             for city_name, total in sorted(city_totals.items()):
#                 status = "⚠️ NEGATIVE" if total < 0 else "✓"
#                 print(f"  {city_name}: ${total:,.2f} {status}")

#             print(f"\nTotal distributed: ${total_distributed_check:,.2f}")
#             print(f"Expected (sum of paid_values): ${sum(item['paid_value'] for item in data):,.2f}")

#         return data

#     def _calculate_city_totals(self, data: List[Dict]) -> Dict[str, float]:
#         """Calcula totais por cidade através de todos os itens"""
#         totals = {}
#         for item in data:
#             for city in item["cities"]:
#                 city_name = city.get("city", "Unknown")
#                 if city_name not in totals:
#                     totals[city_name] = 0
#                 totals[city_name] += city.get("distributed_value", 0)
#         return totals


# def process_data_with_validation(raw_data: List[Dict]) -> List[Dict]:
#     """
#     Processa dados e valida que a soma está correta.
#     """
#     # Calcula soma esperada
#     expected_sum = sum(item["paid_value"] for item in raw_data)

#     print(f"\nProcessing {len(raw_data)} items...")
#     print(f"Expected total: ${expected_sum:,.2f}")

#     # Processa distribuição
#     distributor = GlobalValueDistributor(debug=False)
#     result = distributor.distribute(raw_data)

#     # Valida resultado
#     total_distributed = 0
#     city_totals = {}

#     for item in result:
#         for city in item["cities"]:
#             distributed = city.get("distributed_value", 0)
#             total_distributed += distributed

#             city_name = city.get("city", "Unknown")
#             if city_name not in city_totals:
#                 city_totals[city_name] = 0
#             city_totals[city_name] += distributed

#     print(f"\nValidation:")
#     print(f"  Expected sum: ${expected_sum:,.2f}")
#     print(f"  Actual sum: ${total_distributed:,.2f}")
#     print(f"  Difference: ${abs(expected_sum - total_distributed):,.2f}")

#     if abs(expected_sum - total_distributed) < 0.01:
#         print("  ✅ CORRECT: Sum matches exactly!")
#     else:
#         print("  ❌ ERROR: Sum does not match!")

#     print(f"\nCity totals:")
#     for city_name, total in sorted(city_totals.items()):
#         print(f"  {city_name}: ${total:,.2f}")

#     return result


