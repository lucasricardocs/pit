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

# --- Configurações Globais ---
SPREADSHEET_ID = '1NTScbiIna-iE7roQ9XBdjUOssRihTFFby4INAAQNXTg'
WORKSHEET_NAME = 'Vendas'
CREDENTIALS_FILE = 'credentials.json'
LOGO_PATH = 'logo.png'

# Configuração de cores para modo escuro
DARK_THEME = {
    'background': '#1e1e1e',
    'surface': '#2d2d2d',
    'primary': '#00d4aa',
    'secondary': '#ff6b6b',
    'text': '#ffffff',
    'text_secondary': '#b0b0b0',
    'success': '#51cf66',
    'warning': '#ffd43b',
    'danger': '#ff6b6b'
}

# Define a ordem correta dos dias da semana e meses
dias_semana_ordem = ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"]
meses_ordem = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]

# --- Funções de Autenticação (CORRIGIDA) ---
def get_google_auth():
    """Autoriza o acesso ao Google Sheets usando variável de ambiente ou arquivo JSON."""
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets',
              'https://www.googleapis.com/auth/spreadsheets.readonly',
              'https://www.googleapis.com/auth/drive.readonly']
    
    # CORREÇÃO: Nome correto da variável de ambiente
    credentials_json_str = os.environ.get('GOOGLE_CREDENTIALS')
    if credentials_json_str:
        try:
            credentials_info = json.loads(credentials_json_str)
            creds = Credentials.from_service_account_info(credentials_info, scopes=SCOPES)
            gc = gspread.authorize(creds)
            print("✅ Autenticação com Google via variável de ambiente bem-sucedida.")
            return gc
        except json.JSONDecodeError:
            print("❌ Erro: Conteúdo da variável GOOGLE_CREDENTIALS não é um JSON válido.")
        except Exception as e:
            print(f"❌ Erro de autenticação via variável de ambiente: {e}")

    # Fallback para arquivo local
    if os.path.exists(CREDENTIALS_FILE):
        try:
            creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
            gc = gspread.authorize(creds)
            print(f"✅ Autenticação via arquivo '{CREDENTIALS_FILE}' bem-sucedida.")
            return gc
        except Exception as e:
            print(f"❌ Erro de autenticação via arquivo: {e}")
    
    print("❌ Falha na autenticação com Google Sheets.")
    return None

def get_worksheet():
    """Retorna o objeto worksheet da planilha especificada."""
    gc = get_google_auth()
    if gc:
        try:
            spreadsheet = gc.open_by_key(SPREADSHEET_ID)
            worksheet = spreadsheet.worksheet(WORKSHEET_NAME)
            print(f"✅ Acesso à planilha '{WORKSHEET_NAME}' bem-sucedido.")
            return worksheet
        except SpreadsheetNotFound:
            print(f"❌ Planilha com ID '{SPREADSHEET_ID}' não encontrada.")
        except Exception as e:
            print(f"❌ Erro ao acessar planilha: {e}")
    return None

def read_sales_data():
    """Lê todos os registros da planilha de vendas."""
    ws = get_worksheet()
    if ws:
        try:
            rows = ws.get_all_records()
            if not rows:
                return pd.DataFrame(columns=['Data', 'Cartão', 'Dinheiro', 'Pix'])

            df = pd.DataFrame(rows)
            
            # Converte valores monetários
            for col in ['Cartão', 'Dinheiro', 'Pix']:
                if col in df.columns:
                    df[col] = df[col].replace('', 0)
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                else:
                    df[col] = 0
            
            # Processa datas
            if 'Data' in df.columns:
                df['Data'] = pd.to_datetime(df['Data'], format='%d/%m/%Y', errors='coerce')
                df.dropna(subset=['Data'], inplace=True)
            
            return df
        except Exception as e:
            print(f"❌ Erro ao ler dados: {e}")
    
    return pd.DataFrame(columns=['Data', 'Cartão', 'Dinheiro', 'Pix'])

def add_data_to_sheet(date_str, cartao, dinheiro, pix):
    """Adiciona nova linha à planilha."""
    ws = get_worksheet()
    if ws is None:
        return False, "Erro de conexão com a planilha."
    
    try:
        cartao_val = float(cartao) if cartao else 0.0
        dinheiro_val = float(dinheiro) if dinheiro else 0.0
        pix_val = float(pix) if pix else 0.0
        
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        formatted_date = date_obj.strftime('%d/%m/%Y')
        
        new_row = [formatted_date, cartao_val, dinheiro_val, pix_val]
        ws.append_row(new_row, value_input_option='USER_ENTERED')
        return True, "Dados registrados com sucesso! ✅"
    except Exception as e:
        return False, f"Erro ao adicionar dados: {e}"

def process_data(df_input):
    """Processa dados para análise."""
    if df_input is None or df_input.empty:
        return pd.DataFrame(columns=['Data', 'Cartão', 'Dinheiro', 'Pix', 'Total', 'Ano', 'Mês', 'MêsNome', 'DiaSemana'])

    df = df_input.copy()
    
    # Garante colunas numéricas
    for col in ['Cartão', 'Dinheiro', 'Pix']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        else:
            df[col] = 0

    df['Total'] = df['Cartão'] + df['Dinheiro'] + df['Pix']

    # Processa informações de data
    if 'Data' in df.columns and not df['Data'].isnull().all():
        df['Ano'] = df['Data'].dt.year
        df['Mês'] = df['Data'].dt.month
        df['MêsNome'] = df['Mês'].apply(lambda x: meses_ordem[x-1] if pd.notna(x) and 1 <= x <= 12 else 'Inválido')
        
        day_map = {0: "Segunda-feira", 1: "Terça-feira", 2: "Quarta-feira", 3: "Quinta-feira", 4: "Sexta-feira", 5: "Sábado", 6: "Domingo"}
        df['DiaSemana'] = df['Data'].dt.dayofweek.map(day_map)
        
        # Categorias ordenadas
        df['DiaSemana'] = pd.Categorical(df['DiaSemana'], categories=dias_semana_ordem, ordered=True)
        df['MêsNome'] = pd.Categorical(df['MêsNome'], categories=meses_ordem, ordered=True)
    
    return df

# --- Funções para Gráficos ---
def create_daily_sales_chart(df):
    """Gráfico de vendas diárias."""
    if df.empty:
        return go.Figure().add_annotation(text="Sem dados disponíveis", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
    
    daily_sales = df.groupby('Data')['Total'].sum().reset_index()
    
    fig = px.line(daily_sales, x='Data', y='Total', 
                  title='📈 Vendas Diárias',
                  color_discrete_sequence=[DARK_THEME['primary']])
    
    fig.update_layout(
        plot_bgcolor=DARK_THEME['background'],
        paper_bgcolor=DARK_THEME['surface'],
        font_color=DARK_THEME['text'],
        title_font_size=20,
        xaxis=dict(gridcolor='#404040'),
        yaxis=dict(gridcolor='#404040')
    )
    
    return fig

def create_payment_method_chart(df):
    """Gráfico de métodos de pagamento."""
    if df.empty:
        return go.Figure()
    
    payment_totals = {
        'Cartão': df['Cartão'].sum(),
        'Dinheiro': df['Dinheiro'].sum(),
        'Pix': df['Pix'].sum()
    }
    
    fig = px.pie(values=list(payment_totals.values()), 
                 names=list(payment_totals.keys()),
                 title='💳 Distribuição por Método de Pagamento',
                 color_discrete_sequence=[DARK_THEME['primary'], DARK_THEME['secondary'], DARK_THEME['success']])
    
    fig.update_layout(
        plot_bgcolor=DARK_THEME['background'],
        paper_bgcolor=DARK_THEME['surface'],
        font_color=DARK_THEME['text'],
        title_font_size=20
    )
    
    return fig

def create_weekly_pattern_chart(df):
    """Gráfico de padrão semanal."""
    if df.empty:
        return go.Figure()
    
    weekly_sales = df.groupby('DiaSemana')['Total'].mean().reset_index()
    
    fig = px.bar(weekly_sales, x='DiaSemana', y='Total',
                 title='📊 Padrão de Vendas por Dia da Semana',
                 color='Total',
                 color_continuous_scale='viridis')
    
    fig.update_layout(
        plot_bgcolor=DARK_THEME['background'],
        paper_bgcolor=DARK_THEME['surface'],
        font_color=DARK_THEME['text'],
        title_font_size=20,
        xaxis=dict(gridcolor='#404040'),
        yaxis=dict(gridcolor='#404040')
    )
    
    return fig

def create_monthly_trend_chart(df):
    """Gráfico de tendência mensal."""
    if df.empty:
        return go.Figure()
    
    monthly_sales = df.groupby(['Ano', 'MêsNome'])['Total'].sum().reset_index()
    monthly_sales['Período'] = monthly_sales['MêsNome'].astype(str) + '/' + monthly_sales['Ano'].astype(str)
    
    fig = px.bar(monthly_sales, x='Período', y='Total',
                 title='📅 Vendas Mensais',
                 color='Total',
                 color_continuous_scale='plasma')
    
    fig.update_layout(
        plot_bgcolor=DARK_THEME['background'],
        paper_bgcolor=DARK_THEME['surface'],
        font_color=DARK_THEME['text'],
        title_font_size=20,
        xaxis=dict(gridcolor='#404040'),
        yaxis=dict(gridcolor='#404040')
    )
    
    return fig

# --- Inicialização do App ---
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.CYBORG], suppress_callback_exceptions=True)
server = app.server

# --- Layout com Modo Escuro ---
app.layout = dbc.Container([
    dcc.Store(id='store-sales-data'),
    
    # Header
    dbc.Row([
        dbc.Col([
            html.Div([
                html.H1("🍔 CLIP'S BURGER", className="text-center mb-0", 
                       style={'color': DARK_THEME['primary'], 'font-weight': 'bold'}),
                html.P("Sistema Financeiro Inteligente", className="text-center text-muted")
            ])
        ], width=12)
    ], className="mb-4 mt-3"),
    
    # Formulário de Registro
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader([
                    html.H4("💰 Registrar Nova Venda", className="mb-0", style={'color': DARK_THEME['text']})
                ]),
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col([
                            html.Label("📅 Data:", style={'color': DARK_THEME['text']}),
                            dcc.DatePickerSingle(
                                id='input-date',
                                date=date.today(),
                                display_format='DD/MM/YYYY',
                                style={'width': '100%'}
                            )
                        ], width=12, md=3),
                        dbc.Col([
                            html.Label("💳 Cartão (R$):", style={'color': DARK_THEME['text']}),
                            dbc.Input(id='input-cartao', type='number', placeholder='0.00', min=0, step=0.01)
                        ], width=12, md=3),
                        dbc.Col([
                            html.Label("💵 Dinheiro (R$):", style={'color': DARK_THEME['text']}),
                            dbc.Input(id='input-dinheiro', type='number', placeholder='0.00', min=0, step=0.01)
                        ], width=12, md=3),
                        dbc.Col([
                            html.Label("📱 Pix (R$):", style={'color': DARK_THEME['text']}),
                            dbc.Input(id='input-pix', type='number', placeholder='0.00', min=0, step=0.01)
                        ], width=12, md=3)
                    ], className="mb-3"),
                    dbc.Button("✅ Registrar Venda", id='submit-button', color="success", size="lg", className="w-100"),
                    html.Div(id='output-message', className="mt-3")
                ])
            ], style={'background-color': DARK_THEME['surface']})
        ], width=12)
    ], className="mb-4"),
    
    # Métricas Principais
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H4("📊 Resumo Financeiro", className="text-center mb-3"),
                    html.Div(id='metrics-cards')
                ])
            ], style={'background-color': DARK_THEME['surface']})
        ], width=12)
    ], className="mb-4"),
    
    # Gráficos
    dbc.Row([
        dbc.Col([
            dcc.Graph(id='daily-sales-chart')
        ], width=12, lg=6),
        dbc.Col([
            dcc.Graph(id='payment-method-chart')
        ], width=12, lg=6)
    ], className="mb-4"),
    
    dbc.Row([
        dbc.Col([
            dcc.Graph(id='weekly-pattern-chart')
        ], width=12, lg=6),
        dbc.Col([
            dcc.Graph(id='monthly-trend-chart')
        ], width=12, lg=6)
    ], className="mb-4"),
    
    # Tabela de Dados
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader([
                    html.H4("📋 Histórico de Vendas", className="mb-0")
                ]),
                dbc.CardBody([
                    html.Div(id='sales-table')
                ])
            ], style={'background-color': DARK_THEME['surface']})
        ], width=12)
    ])
], fluid=True, style={'background-color': DARK_THEME['background'], 'min-height': '100vh'})

# --- Callbacks ---
@app.callback(
    [Output('output-message', 'children'),
     Output('store-sales-data', 'data')],
    Input('submit-button', 'n_clicks'),
    [State('input-date', 'date'),
     State('input-cartao', 'value'),
     State('input-dinheiro', 'value'),
     State('input-pix', 'value')],
    prevent_initial_call=True
)
def submit_new_sale(n_clicks, date_val, cartao_val, dinheiro_val, pix_val):
    if not date_val:
        return dbc.Alert("Por favor, selecione uma data.", color="warning"), dash.no_update
    
    cartao = float(cartao_val) if cartao_val else 0.0
    dinheiro = float(dinheiro_val) if dinheiro_val else 0.0
    pix = float(pix_val) if pix_val else 0.0
    
    if cartao == 0.0 and dinheiro == 0.0 and pix == 0.0:
        return dbc.Alert("Insira pelo menos um valor.", color="warning"), dash.no_update

    success, message = add_data_to_sheet(date_val, cartao, dinheiro, pix)
    
    alert_color = "success" if success else "danger"
    alert_message = dbc.Alert(message, color=alert_color, dismissable=True)
    
    if success:
        df_new = read_sales_data()
        df_processed = process_data(df_new)
        return alert_message, df_processed.to_json(date_format='iso', orient='split')
    else:
        return alert_message, dash.no_update

@app.callback(
    Output('store-sales-data', 'data'),
    Input('submit-button', 'id'),
    prevent_initial_call=False
)
def load_initial_data(_):
    df = read_sales_data()
    df_processed = process_data(df)
    return df_processed.to_json(date_format='iso', orient='split')

@app.callback(
    [Output('metrics-cards', 'children'),
     Output('daily-sales-chart', 'figure'),
     Output('payment-method-chart', 'figure'),
     Output('weekly-pattern-chart', 'figure'),
     Output('monthly-trend-chart', 'figure'),
     Output('sales-table', 'children')],
    Input('store-sales-data', 'data')
)
def update_dashboard(data_json):
    if not data_json:
        empty_fig = go.Figure()
        return [], empty_fig, empty_fig, empty_fig, empty_fig, "Sem dados disponíveis"
    
    df = pd.read_json(data_json, orient='split')
    df['Data'] = pd.to_datetime(df['Data'])
    
    # Métricas
    total_vendas = df['Total'].sum()
    vendas_hoje = df[df['Data'].dt.date == date.today()]['Total'].sum()
    media_diaria = df.groupby(df['Data'].dt.date)['Total'].sum().mean()
    
    metrics = dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H3(f"R$ {total_vendas:,.2f}", className="text-success"),
                    html.P("Total Vendas", className="text-muted")
                ])
            ], style={'background-color': DARK_THEME['background']})
        ], width=4),
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H3(f"R$ {vendas_hoje:,.2f}", className="text-info"),
                    html.P("Vendas Hoje", className="text-muted")
                ])
            ], style={'background-color': DARK_THEME['background']})
        ], width=4),
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H3(f"R$ {media_diaria:,.2f}", className="text-warning"),
                    html.P("Média Diária", className="text-muted")
                ])
            ], style={'background-color': DARK_THEME['background']})
        ], width=4)
    ])
    
    # Gráficos
    daily_chart = create_daily_sales_chart(df)
    payment_chart = create_payment_method_chart(df)
    weekly_chart = create_weekly_pattern_chart(df)
    monthly_chart = create_monthly_trend_chart(df)
    
    # Tabela
    table_data = df[['Data', 'Cartão', 'Dinheiro', 'Pix', 'Total']].tail(10)
    table_data['Data'] = table_data['Data'].dt.strftime('%d/%m/%Y')
    
    table = dash_table.DataTable(
        data=table_data.to_dict('records'),
        columns=[{'name': col, 'id': col, 'type': 'numeric', 'format': {'specifier': ',.2f'}} if col != 'Data' 
                else {'name': col, 'id': col} for col in table_data.columns],
        style_cell={'textAlign': 'center', 'backgroundColor': DARK_THEME['surface'], 'color': DARK_THEME['text']},
        style_header={'backgroundColor': DARK_THEME['primary'], 'color': 'white', 'fontWeight': 'bold'},
        style_data_conditional=[
            {
                'if': {'row_index': 'odd'},
                'backgroundColor': DARK_THEME['background']
            }
        ]
    )
    
    return metrics, daily_chart, payment_chart, weekly_chart, monthly_chart, table

if __name__ == '__main__':
    print("🚀 Iniciando Clip's Burger Dashboard...")
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 8050)))
