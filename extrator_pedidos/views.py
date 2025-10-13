import requests
import pandas as pd
import re
import os
from io import BytesIO
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.http import HttpResponse
from django.shortcuts import render
from django.http import JsonResponse
# --- Configurações da API ---
API_URL = "https://seller.api.brandshub.com.br/"

# Credenciais de login (somente para testes)
EMAIL = "erick.silva@spiritosanto.com.br"
PASSWORD = "84256643"
ACCOUNT_ID = "kqSpBxUNyJQt"
USER_AGENT = "MeuSeller/1.0 (https://meuintegrador.com.br)"

def get_auth_token():
    """
    Realiza o login na API e retorna o token de acesso.
    """
    print("Tentando realizar o login para obter o token...")
    
    LOGIN_QUERY = f"""
    query {{
        login(
            email: "{EMAIL}",
            password: "{PASSWORD}",
            keepLogged: true,
            accountId: "{ACCOUNT_ID}"
        ) {{
            success
            message
            token
        }}
    }}
    """
    
    headers = {
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT
    }
    
    data = {"query": LOGIN_QUERY}
    
    try:
        response = requests.post(API_URL, headers=headers, json=data)
        response.raise_for_status()
        
        json_response = response.json()
        if "errors" in json_response:
            print("Erro(s) da API:")
            for error in json_response["errors"]:
                print(f"- {error.get('message', 'Erro desconhecido')}")
            return None

        login_data = json_response.get('data', {}).get('login', {})
        if login_data.get('success'):
            print("Login bem-sucedido.")
            return login_data.get('token')
        else:
            print(f"Falha no login: {login_data.get('message', 'Mensagem de erro não disponível')}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"Erro ao tentar se conectar ou fazer login: {e}")
        return None

def get_order_data(auth_token, cnpj, codigo_produto):
    """
    Faz a requisição à API GraphQL para obter os dados do pedido.
    """
    GRAPHQL_QUERY = f"""
    query {{
        orders(
            filter: {{
                code: {codigo_produto}
                buyer: {{
                    cnpj: "{cnpj}"
                }}
            }}
        ) {{
            items {{
                buyer {{
                    name
                }}
                basket {{
                    items {{
                        quantity
                        product {{
                            name
                        }}
                        sku {{
                            code
                            variant {{
                                type
                                name
                            }}
                        }}
                        values {{
                            total
                        }}
                    }}
                }}
            }}
        }}
    }}
    """
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": auth_token,
        "User-Agent": USER_AGENT
    }
    
    data = {"query": GRAPHQL_QUERY}
    
    try:
        response = requests.post(API_URL, headers=headers, json=data)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Erro na requisição: {e}")
        return None

def process_data_for_excel(api_data, cnpj):
    """
    Processa o JSON da API e o converte para uma lista de dicionários.
    """
    if not api_data or not api_data.get('data') or not api_data['data'].get('orders') or not api_data['data']['orders'].get('items'):
        print("Nenhum pedido encontrado ou a resposta da API está incompleta.")
        return [], None

    processed_data = []
    buyer_name = None
    
    for order in api_data['data']['orders']['items']:
        buyer_name = order.get('buyer', {}).get('name', 'N/A')
        basket_items = order.get('basket', {}).get('items', [])
        
        for item in basket_items:
            sku = item.get('sku', {}).get('code', 'N/A')
            quantity = item.get('quantity', 'N/A')
            
            description = item.get('product', {}).get('name', 'N/A')
            price = item.get('values', {}).get('total', 'N/A')

            unit_price = 'N/A'
            if isinstance(quantity, (int, float)) and isinstance(price, (int, float)) and quantity > 0:
                unit_price = price / quantity
            
            color = ""
            size = ""
            variants = item.get('sku', {}).get('variant', [])
            if isinstance(variants, list):
                for variant in variants:
                    if variant.get('type') == 'color':
                        color = variant.get('name', 'N/A')
                    elif variant.get('type') == 'size':
                        size = variant.get('name', 'N/A')
            
            processed_data.append({
                "CNPJ": cnpj,
                "Nome do CNPJ": buyer_name,
                "SKU": sku,
                "Descrição": description,
                "COR": color,
                "TAMANHO": size,
                "Quantidade": quantity,
                "Preço Unitário": unit_price,
                "Preço Total": price
            })
            
    return processed_data, buyer_name

def export_to_excel_in_memory(data):
    """
    Gera o arquivo Excel na memória e retorna um objeto BytesIO.
    """
    df = pd.DataFrame(data)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Pedidos')
    output.seek(0)
    return output

# View para renderizar o HTML
def index(request):
    return render(request, 'extrator_pedidos/index.html')

# View para processar a requisição da API
class ProcessarPedido(APIView):
    def post(self, request):
        cnpj = request.data.get('cnpj')
        codigo_produto = request.data.get('codigo_produto')

        if not cnpj or not codigo_produto:
            return Response({"erro": "CNPJ e código do produto são obrigatórios."}, status=status.HTTP_400_BAD_REQUEST)

        auth_token = get_auth_token()
        if not auth_token:
            return Response({"erro": "Falha na autenticação da API. Verifique suas variáveis de ambiente."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        api_response = get_order_data(auth_token, cnpj, codigo_produto)
        
        if api_response:
            excel_data, buyer_name = process_data_for_excel(api_response, cnpj)
            
            if excel_data:
                excel_file_in_memory = export_to_excel_in_memory(excel_data)
                sanitized_name = re.sub(r'[\\/*?:"<>|]', "", buyer_name or "Pedido").strip()
                filename = f"Pedido - {sanitized_name}.xlsx"
                
                response = HttpResponse(excel_file_in_memory.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                response['Content-Disposition'] = f'attachment; filename="{filename}"'
                return response


        return Response({"erro": "Nenhum dado encontrado para o pedido."}, status=status.HTTP_404_NOT_FOUND)




def health_check(request):
    return JsonResponse({"status": "ok"})
