# -*- coding: utf-8 -*-
import dash
from dash import dcc, html, Input, Output, State, callback, dash_table
import dash_bootstrap_components as dbc
import gspread
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta, date
from google.oauth2.service_account import Credentials
from gspread.exceptions import SpreadsheetNotFound
import os
import json

# --- Configurações Globais e Constantes ---
SPREADSHEET_ID = '1NTScbiIna-iE7roQ9XBdjUOssRihTFFby4INAAQNXTg'
WORKSHEET_NAME = 'Vendas'
CREDENTIALS_FILE = 'credentials.json' # Caminho relativo para o arquivo JSON local
LOGO_PATH = 'logo.png' # Assumindo que logo.png está na pasta /assets

# Define a ordem correta dos dias da semana e meses (Português)
dias_semana_ordem = ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"]
meses_ordem = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]

# --- Funções de Autenticação e Acesso ao Google Sheets (Adaptada para Deploy) ---
def get_google_auth():
    """Autoriza o acesso ao Google Sheets usando variável de ambiente ou arquivo JSON."""
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets',
              'https://www.googleapis.com/auth/spreadsheets.readonly',
              'https://www.googleapis.com/auth/drive.readonly']
    creds = None
    gc = None

    # 1. Tenta carregar credenciais da variável de ambiente (preferencial para deploy)
    credentials_json_str = os.environ.get('GOOGLE_CREDENTIALS_JSON')
    if credentials_json_str:
        try:
            credentials_info = json.loads(credentials_json_str)
            creds = Credentials.from_service_account_info(credentials_info, scopes=SCOPES)
            gc = gspread.authorize(creds)
            print("Autenticação com Google via variável de ambiente bem-sucedida.")
            return gc
        except json.JSONDecodeError:
            print("Erro crítico: Conteúdo da variável de ambiente GOOGLE_CREDENTIALS_JSON não é um JSON válido.")
        except Exception as e:
            print(f"Erro de autenticação com Google via variável de ambiente: {e}")

    # 2. Se falhar ou não existir variável de ambiente, tenta carregar do arquivo local
    if not gc:
        print("Variável de ambiente GOOGLE_CREDENTIALS_JSON não encontrada ou inválida. Tentando arquivo local...")
        if os.path.exists(CREDENTIALS_FILE):
            try:
                creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
                gc = gspread.authorize(creds)
                print(f"Autenticação com Google via arquivo '{CREDENTIALS_FILE}' bem-sucedida.")
                return gc
            except FileNotFoundError:
                # Esta exceção não deveria ocorrer devido ao os.path.exists, mas por segurança
                print(f"Erro crítico: Arquivo de credenciais '{CREDENTIALS_FILE}' não encontrado (apesar de existir?).")
            except json.JSONDecodeError:
                print(f"Erro crítico: O arquivo de credenciais '{CREDENTIALS_FILE}' não é um JSON válido.")
            except Exception as e:
                print(f"Erro de autenticação com Google via arquivo: {e}")
        else:
            print(f"Erro crítico: Arquivo de credenciais '{CREDENTIALS_FILE}' não encontrado.")

    # Se ambas as tentativas falharem
    if not gc:
        print("Falha na autenticação com Google. Verifique as credenciais (variável de ambiente ou arquivo JSON).")
        return None
    
    return gc # Retorna gc se alguma tentativa funcionou (embora já retornado antes)


def get_worksheet():
    """Retorna o objeto worksheet da planilha especificada."""
    gc = get_google_auth() # Tenta autenticar
    if gc:
        try:
            spreadsheet = gc.open_by_key(SPREADSHEET_ID)
            worksheet = spreadsheet.worksheet(WORKSHEET_NAME)
            print(f"Acesso à planilha '{WORKSHEET_NAME}' bem-sucedido.")
            return worksheet
        except SpreadsheetNotFound:
            print(f"Erro: Planilha com ID '{SPREADSHEET_ID}' não encontrada.")
            return None
        except Exception as e:
            print(f"Erro ao acessar a planilha '{WORKSHEET_NAME}': {e}")
            return None
    print("Falha ao obter cliente gspread autenticado para acessar worksheet.")
    return None

# Tenta obter a worksheet na inicialização para verificar a conexão
# É importante que get_worksheet() chame get_google_auth() para que a lógica de autenticação seja executada.
worksheet = get_worksheet()

def read_sales_data():
    """Lê todos os registros da planilha de vendas e retorna como DataFrame."""
    # Re-tenta obter a worksheet se falhou na inicialização ou para garantir dados frescos
    ws = get_worksheet() # Chama get_worksheet que por sua vez chama get_google_auth
    if ws:
        try:
            rows = ws.get_all_records()
            if not rows:
                print("A planilha de vendas está vazia.")
                return pd.DataFrame(columns=['Data', 'Cartão', 'Dinheiro', 'Pix'])

            df = pd.DataFrame(rows)
            print(f"Dados lidos da planilha: {len(df)} linhas.")
            
            for col in ['Cartão', 'Dinheiro', 'Pix']:
                if col in df.columns:
                    df[col] = df[col].replace('', 0)
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                else:
                    df[col] = 0
            
            if 'Data' not in df.columns:
                print("Aviso: Coluna 'Data' não encontrada na planilha. Criando coluna vazia.")
                df['Data'] = pd.NaT
            else:
                try:
                    df['Data'] = pd.to_datetime(df['Data'], format='%d/%m/%Y', errors='coerce')
                except ValueError:
                    try:
                         df['Data'] = pd.to_datetime(df['Data'], format='%Y-%m-%d', errors='coerce')
                    except ValueError:
                         df['Data'] = pd.to_datetime(df['Data'], errors='coerce')
                
                original_len = len(df)
                df.dropna(subset=['Data'], inplace=True)
                if len(df) < original_len:
                    print(f"Aviso: {original_len - len(df)} linhas removidas devido a datas inválidas.")

            return df
        except Exception as e:
            print(f"Erro ao ler dados da planilha: {e}")
            return pd.DataFrame(columns=['Data', 'Cartão', 'Dinheiro', 'Pix'])
    print("Falha ao obter worksheet para leitura de dados.")
    return pd.DataFrame(columns=['Data', 'Cartão', 'Dinheiro', 'Pix'])

# --- Funções de Manipulação de Dados ---
def add_data_to_sheet(date_str, cartao, dinheiro, pix):
    """Adiciona uma nova linha de dados à planilha Google Sheets."""
    ws = get_worksheet() # Garante que temos uma conexão válida
    if ws is None:
        print("Erro: Não foi possível acessar a planilha para adicionar dados.")
        return False, "Erro de conexão com a planilha."
    try:
        cartao_val = float(cartao) if cartao else 0.0
        dinheiro_val = float(dinheiro) if dinheiro else 0.0
        pix_val = float(pix) if pix else 0.0
        
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            formatted_date = date_obj.strftime('%d/%m/%Y')
        except ValueError:
             return False, "Formato de data inválido. Use AAAA-MM-DD."

        new_row = [formatted_date, cartao_val, dinheiro_val, pix_val]
        ws.append_row(new_row, value_input_option='USER_ENTERED')
        print(f"Dados registrados com sucesso: {new_row}")
        return True, "Dados registrados com sucesso! ✅"
    except ValueError as ve:
        error_msg = f"Erro ao converter valores para número: {ve}. Verifique os dados de entrada."
        print(error_msg)
        return False, error_msg
    except Exception as e:
        error_msg = f"Erro ao adicionar dados na planilha: {e}"
        print(error_msg)
        return False, error_msg

def process_data(df_input):
    """Processa e prepara os dados de vendas para análise."""
    if df_input is None or df_input.empty:
        print("DataFrame de entrada vazio ou None em process_data.")
        cols = ['Data', 'Cartão', 'Dinheiro', 'Pix', 'Total', 'Ano', 'Mês', 'MêsNome', 'AnoMês', 'DataFormatada', 'DiaSemana', 'DiaDoMes']
        empty_df = pd.DataFrame(columns=cols)
        empty_df['Data'] = pd.to_datetime(empty_df['Data'])
        for col in ['Cartão', 'Dinheiro', 'Pix', 'Total']: empty_df[col] = pd.to_numeric(empty_df[col])
        return empty_df

    df = df_input.copy()
    
    for col in ['Cartão', 'Dinheiro', 'Pix']:
        if col in df.columns:
            df[col] = df[col].replace('', 0)
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        else:
            df[col] = 0

    df['Total'] = df['Cartão'] + df['Dinheiro'] + df['Pix']

    if 'Data' in df.columns and pd.api.types.is_datetime64_any_dtype(df['Data']) and not df['Data'].isnull().all():
        df.dropna(subset=['Data'], inplace=True)
        if not df.empty:
            df['Ano'] = df['Data'].dt.year
            df['Mês'] = df['Data'].dt.month
            df['MêsNome'] = df['Mês'].apply(lambda x: meses_ordem[x-1] if pd.notna(x) and 1 <= x <= 12 else 'Inválido')
            df['AnoMês'] = df['Data'].dt.strftime('%Y-%m')
            df['DataFormatada'] = df['Data'].dt.strftime('%d/%m/%Y')
            day_map = {0: "Segunda-feira", 1: "Terça-feira", 2: "Quarta-feira", 3: "Quinta-feira", 4: "Sexta-feira", 5: "Sábado", 6: "Domingo"}
            df['DiaSemana'] = df['Data'].dt.dayofweek.map(day_map)
            df['DiaDoMes'] = df['Data'].dt.day
            df['DiaSemana'] = pd.Categorical(df['DiaSemana'], categories=dias_semana_ordem, ordered=True)
            df['MêsNome'] = pd.Categorical(df['MêsNome'], categories=meses_ordem, ordered=True)
            print("Colunas de data processadas.")
        else:
            print("DataFrame vazio após remover datas nulas.")
            for col in ['Ano', 'Mês', 'MêsNome', 'AnoMês', 'DataFormatada', 'DiaSemana', 'DiaDoMes']:
                 df[col] = pd.NA
    else:
        print("Aviso: Coluna 'Data' ausente, inválida ou vazia. Análises temporais podem ser afetadas.")
        for col in ['Ano', 'Mês', 'MêsNome', 'AnoMês', 'DataFormatada', 'DiaSemana', 'DiaDoMes']:
             df[col] = pd.NA
             
    expected_cols = ['Data', 'Cartão', 'Dinheiro', 'Pix', 'Total', 'Ano', 'Mês', 'MêsNome', 'AnoMês', 'DataFormatada', 'DiaSemana', 'DiaDoMes']
    for col in expected_cols:
        if col not in df.columns:
            df[col] = pd.NA
            if col in ['Cartão', 'Dinheiro', 'Pix', 'Total']: df[col] = 0
            if col == 'Data': df[col] = pd.to_datetime(pd.NA)
            
    return df

# --- Inicialização do App Dash ---
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP], suppress_callback_exceptions=True, assets_folder='assets')
server = app.server # Para deploy (ex: Gunicorn)

# --- Layout do App Dash ---
app.layout = dbc.Container(
    [
        dcc.Store(id='store-sales-data'),
        dbc.Row(
            [
                dbc.Col(html.Img(src=app.get_asset_url(LOGO_PATH), height="100px") if os.path.exists(f'assets/{LOGO_PATH}') else html.H1("🍔"), width="auto"),
                dbc.Col([
                    html.H1("SISTEMA FINANCEIRO - CLIP'S BURGER", className="text-primary"),
                    html.P("Gestão inteligente de vendas com análise financeira", className="text-secondary")
                ], width=True)
            ],
            align="center",
            className="mb-4 mt-4"
        ),
        dbc.Row(
            dbc.Col([
                html.H4("Registrar Nova Venda"),
                dbc.Card([
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col([
                                html.Label("Data:"),
                                dcc.DatePickerSingle(
                                    id='input-date',
                                    min_date_allowed=date(2020, 1, 1),
                                    max_date_allowed=date.today() + timedelta(days=1),
                                    initial_visible_month=date.today(),
                                    date=date.today(),
                                    display_format='DD/MM/YYYY',
                                    className="mb-2"
                                )
                            ], width=12, md=3),
                            dbc.Col([
                                html.Label("Cartão (R$):", htmlFor='input-cartao'),
                                dbc.Input(id='input-cartao', type='number', placeholder='0.00', min=0, step=0.01, className="mb-2")
                            ], width=12, md=3),
                            dbc.Col([
                                html.Label("Dinheiro (R$):", htmlFor='input-dinheiro'),
                                dbc.Input(id='input-dinheiro', type='number', placeholder='0.00', min=0, step=0.01, className="mb-2")
                            ], width=12, md=3),
                            dbc.Col([
                                html.Label("Pix (R$):", htmlFor='input-pix'),
                                dbc.Input(id='input-pix', type='number', placeholder='0.00', min=0, step=0.01, className="mb-2")
                            ], width=12, md=3)
                        ]),
                        dbc.Button("Registrar Venda", id='submit-button', color="primary", n_clicks=0, className="mt-2"),
                        html.Div(id='output-message', className="mt-2")
                    ])
                ], className="shadow-sm")
            ], width=12)
        , className="mb-4"),
        dbc.Row(
            dbc.Col([
                html.H4("Análise Financeira"),
                dbc.Card([
                    dbc.CardBody([
                        html.P("Filtros e gráficos aparecerão aqui."),
                        html.Div(id='filters-placeholder', className="mb-3"),
                        html.Div(id='charts-placeholder'),
                        html.Div(id='metrics-placeholder'),
                        html.Div(id='table-placeholder')
                    ])
                ], className="shadow-sm")
            ], width=12)
        )
    ],
    fluid=True
)

# --- Callbacks ---
@app.callback(
    Output('output-message', 'children'),
    Output('store-sales-data', 'data', allow_duplicate=True),
    Input('submit-button', 'n_clicks'),
    State('input-date', 'date'),
    State('input-cartao', 'value'),
    State('input-dinheiro', 'value'),
    State('input-pix', 'value'),
    State('store-sales-data', 'data'),
    prevent_initial_call=True
)
def submit_new_sale(n_clicks, date_val, cartao_val, dinheiro_val, pix_val, current_data_json):
    if not date_val:
        return dbc.Alert("Por favor, selecione uma data.", color="warning"), dash.no_update
    
    cartao = float(cartao_val) if cartao_val is not None else 0.0
    dinheiro = float(dinheiro_val) if dinheiro_val is not None else 0.0
    pix = float(pix_val) if pix_val is not None else 0.0
    
    if cartao == 0.0 and dinheiro == 0.0 and pix == 0.0:
         return dbc.Alert("Insira pelo menos um valor (Cartão, Dinheiro ou Pix).", color="warning"), dash.no_update

    success, message = add_data_to_sheet(date_val, cartao, dinheiro, pix)
    
    alert_color = "success" if success else "danger"
    alert_message = dbc.Alert(message, color=alert_color, dismissable=True)
    
    if success:
        df_new = read_sales_data()
        df_processed = process_data(df_new)
        return alert_message, df_processed.to_json(date_format='iso', orient='split')
    else:
        return alert_message, dash.no_update

# Callback para carregar dados iniciais no Store (melhorado)
# Usamos um Input "fictício" que dispara na carga inicial e um dcc.Interval para atualizações periódicas (opcional)
# Ou podemos simplesmente carregar quando o app inicia e depois de cada submit bem-sucedido.
# Vamos simplificar: carregar na inicialização (fora de callback) e após submit.

# Carrega dados iniciais fora de um callback para simplificar
df_initial = read_sales_data()
df_processed_initial = process_data(df_initial)
initial_store_data = df_processed_initial.to_json(date_format='iso', orient='split')

# Atualiza o Store com os dados iniciais
@app.callback(
    Output('store-sales-data', 'data'),
    Input('output-message', 'children') # Dispara quando uma mensagem (sucesso/erro) é exibida
)
def update_store_on_load(message):
    # Este callback agora serve mais para garantir que o store tenha os dados iniciais
    # A atualização principal acontece no callback submit_new_sale
    if initial_store_data:
        return initial_store_data
    else:
        # Se a carga inicial falhou, tenta de novo (pode não ser ideal)
        df = read_sales_data()
        df_processed = process_data(df)
        return df_processed.to_json(date_format='iso', orient='split')


# --- Execução do App ---
if __name__ == '__main__':
    # Cria a pasta assets se não existir (necessário para Dash servir arquivos estáticos)
    if not os.path.exists('assets'):
        os.makedirs('assets')
        print("Pasta 'assets' criada.")
    # Tenta copiar o logo para a pasta assets se ele existir na raiz e não em assets
    if os.path.exists(LOGO_PATH) and not os.path.exists(f'assets/{LOGO_PATH}'):
        try:
            import shutil
            shutil.copy(LOGO_PATH, f'assets/{LOGO_PATH}')
            print(f"Logo '{LOGO_PATH}' copiado para a pasta 'assets'.")
        except Exception as e:
            print(f"Não foi possível copiar o logo para 'assets': {e}")
    elif not os.path.exists(f'assets/{LOGO_PATH}'):
         print(f"Aviso: Arquivo de logo '{LOGO_PATH}' não encontrado na raiz ou em 'assets'. O logo não será exibido.")

    # Verifica se as credenciais estão acessíveis (variável de ambiente ou arquivo)
    # A função get_google_auth() já faz essa verificação e imprime mensagens
    print("Verificando acesso às credenciais do Google...")
    test_auth = get_google_auth()
    if not test_auth:
         print("\n*** ALERTA CRÍTICO ***")
         print("Não foi possível autenticar com o Google Sheets.")
         print("Verifique a variável de ambiente GOOGLE_CREDENTIALS_JSON ou o arquivo credentials.json.")
         # Considerar parar a execução se a autenticação for essencial
         # exit(1)
    else:
        print("Verificação de credenciais concluída.")

    print("Iniciando servidor Dash...")
    # Para deploy, debug=False é recomendado
    # O host 0.0.0.0 é necessário para Gunicorn/Docker
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 8050)))

