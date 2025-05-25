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
LOGO_PATH = 'logo.png'

# Tema escuro personalizado
DARK_THEME = {
    'background': '#1a1a1a',
    'surface': '#2d2d2d',
    'primary': '#00d4aa',
    'secondary': '#ff6b6b',
    'accent': '#ffd43b',
    'text': '#ffffff',
    'text_secondary': '#b0b0b0',
    'success': '#51cf66',
    'warning': '#ffd43b',
    'danger': '#ff6b6b',
    'card_bg': '#2a2a2a'
}

# Define ordem dos dias e meses
dias_semana_ordem = ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"]
meses_ordem = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]

# --- Funções de Autenticação (CORRIGIDA) ---
def get_google_auth():
    """Autoriza o acesso ao Google Sheets usando variável de ambiente ou arquivo JSON."""
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets',
              'https://www.googleapis.com/auth/spreadsheets.readonly',
              'https://www.googleapis.com/auth/drive.readonly']
    
    # Tenta carregar da variável de ambiente primeiro
    credentials_json_str = os.environ.get('GOOGLE_CREDENTIALS')
    if credentials_json_str:
        try:
            credentials_info = json.loads(credentials_json_str)
            creds = Credentials.from_service_account_info(credentials_info, scopes=SCOPES)
            gc = gspread.authorize(creds)
            print("✅ Autenticação Google via variável de ambiente bem-sucedida.")
            return gc
        except Exception as e:
            print(f"❌ Erro na autenticação via variável: {e}")
    
    # Fallback para arquivo local
    if os.path.exists('credentials.json'):
        try:
            creds = Credentials.from_service_account_file('credentials.json', scopes=SCOPES)
            gc = gspread.authorize(creds)
            print("✅ Autenticação via arquivo local bem-sucedida.")
            return gc
        except Exception as e:
            print(f"❌ Erro na autenticação via arquivo: {e}")
    
    print("❌ Falha na autenticação com Google Sheets.")
    return None

def get_worksheet():
    """Retorna o objeto worksheet da planilha especificada."""
    gc = get_google_auth()
    if gc:
        try:
            spreadsheet = gc.open_by_key(SPREADSHEET_ID)
            worksheet = spreadsheet.worksheet(WORKSHEET_NAME)
            return worksheet
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
        df['DataFormatada'] = df['Data'].dt.strftime('%d/%m/%Y')
        
        # Categorias ordenadas
        df['DiaSemana'] = pd.Categorical(df['DiaSemana'], categories=dias_semana_ordem, ordered=True)
        df['MêsNome'] = pd.Categorical(df['MêsNome'], categories=meses_ordem, ordered=True)
    
    return df

def filter_by_rolling_days(df, dias_selecionados):
    """Filtra DataFrame para últimos N dias."""
    if df.empty or not dias_selecionados or 'Data' not in df.columns:
        return df
    
    data_mais_recente = df['Data'].max()
    max_dias = max(dias_selecionados)
    data_inicio = data_mais_recente - timedelta(days=max_dias - 1)
    
    return df[df['Data'] >= data_inicio].copy()

def calculate_financial_results(df, salario_minimo, custo_contadora, custo_fornecedores_percentual):
    """Calcula resultados financeiros."""
    results = {
        'faturamento_bruto': 0, 'faturamento_tributavel': 0, 'faturamento_nao_tributavel': 0,
        'imposto_simples': 0, 'custo_funcionario': 0, 'custo_contadora': custo_contadora,
        'custo_fornecedores_valor': 0, 'total_custos': 0,
        'lucro_bruto': 0, 'margem_lucro_bruto': 0, 'lucro_liquido': 0, 'margem_lucro_liquido': 0
    }

    if df.empty:
        return results

    # RECEITAS
    results['faturamento_bruto'] = df['Total'].sum()
    results['faturamento_tributavel'] = df['Cartão'].sum() + df['Pix'].sum()
    results['faturamento_nao_tributavel'] = df['Dinheiro'].sum()

    # CUSTOS
    results['imposto_simples'] = results['faturamento_tributavel'] * 0.06
    results['custo_funcionario'] = salario_minimo * 1.55
    results['custo_fornecedores_valor'] = results['faturamento_bruto'] * (custo_fornecedores_percentual / 100)
    results['total_custos'] = results['imposto_simples'] + results['custo_funcionario'] + results['custo_contadora'] + results['custo_fornecedores_valor']

    # RESULTADOS
    results['lucro_bruto'] = results['faturamento_bruto'] - results['total_custos']
    results['lucro_liquido'] = results['faturamento_bruto'] - results['faturamento_tributavel']

    # MARGENS
    if results['faturamento_bruto'] > 0:
        results['margem_lucro_bruto'] = (results['lucro_bruto'] / results['faturamento_bruto']) * 100
        results['margem_lucro_liquido'] = (results['lucro_liquido'] / results['faturamento_bruto']) * 100

    return results

def format_brl(value):
    """Formata valores em moeda brasileira."""
    return f"R$ {value:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")

# --- Funções para Gráficos ---
def create_daily_sales_chart(df):
    """Gráfico de vendas diárias."""
    if df.empty:
        return go.Figure().add_annotation(text="Sem dados disponíveis", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
    
    daily_sales = df.groupby('Data')['Total'].sum().reset_index()
    
    fig = px.line(daily_sales, x='Data', y='Total', 
                  title='📈 Evolução das Vendas Diárias',
                  color_discrete_sequence=[DARK_THEME['primary']])
    
    fig.update_layout(
        plot_bgcolor=DARK_THEME['background'],
        paper_bgcolor=DARK_THEME['surface'],
        font_color=DARK_THEME['text'],
        title_font_size=18,
        xaxis=dict(gridcolor='#404040'),
        yaxis=dict(gridcolor='#404040', tickformat=',.0f')
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
    
    # Remove valores zero
    payment_totals = {k: v for k, v in payment_totals.items() if v > 0}
    
    if not payment_totals:
        return go.Figure()
    
    fig = px.pie(values=list(payment_totals.values()), 
                 names=list(payment_totals.keys()),
                 title='💳 Distribuição por Método de Pagamento',
                 color_discrete_sequence=[DARK_THEME['primary'], DARK_THEME['secondary'], DARK_THEME['success']])
    
    fig.update_layout(
        plot_bgcolor=DARK_THEME['background'],
        paper_bgcolor=DARK_THEME['surface'],
        font_color=DARK_THEME['text'],
        title_font_size=18
    )
    
    return fig

def create_weekly_pattern_chart(df):
    """Gráfico de padrão semanal."""
    if df.empty or 'DiaSemana' not in df.columns:
        return go.Figure()
    
    weekly_sales = df.groupby('DiaSemana')['Total'].mean().reindex(dias_semana_ordem).fillna(0)
    
    fig = px.bar(x=weekly_sales.index, y=weekly_sales.values,
                 title='📊 Média de Vendas por Dia da Semana',
                 color=weekly_sales.values,
                 color_continuous_scale='viridis')
    
    fig.update_layout(
        plot_bgcolor=DARK_THEME['background'],
        paper_bgcolor=DARK_THEME['surface'],
        font_color=DARK_THEME['text'],
        title_font_size=18,
        xaxis=dict(gridcolor='#404040', title='Dia da Semana'),
        yaxis=dict(gridcolor='#404040', title='Média (R$)', tickformat=',.0f')
    )
    
    return fig

def create_monthly_trend_chart(df):
    """Gráfico de tendência mensal."""
    if df.empty or 'MêsNome' not in df.columns:
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
        title_font_size=18,
        xaxis=dict(gridcolor='#404040', title='Período'),
        yaxis=dict(gridcolor='#404040', title='Total (R$)', tickformat=',.0f')
    )
    
    return fig

def create_payment_evolution_chart(df):
    """Gráfico de evolução dos métodos de pagamento."""
    if df.empty or 'Data' not in df.columns:
        return go.Figure()
    
    df_monthly = df.groupby([df['Data'].dt.to_period('M'), 'Data'])[['Cartão', 'Dinheiro', 'Pix']].sum().reset_index()
    df_monthly['Mês'] = df_monthly['Data'].dt.strftime('%m/%Y')
    
    monthly_payments = df_monthly.groupby('Mês')[['Cartão', 'Dinheiro', 'Pix']].sum().reset_index()
    
    fig = go.Figure()
    
    for method in ['Cartão', 'Dinheiro', 'Pix']:
        fig.add_trace(go.Scatter(
            x=monthly_payments['Mês'],
            y=monthly_payments[method],
            mode='lines+markers',
            name=method,
            stackgroup='one'
        ))
    
    fig.update_layout(
        title='📈 Evolução dos Métodos de Pagamento',
        plot_bgcolor=DARK_THEME['background'],
        paper_bgcolor=DARK_THEME['surface'],
        font_color=DARK_THEME['text'],
        title_font_size=18,
        xaxis=dict(gridcolor='#404040', title='Período'),
        yaxis=dict(gridcolor='#404040', title='Valor (R$)', tickformat=',.0f')
    )
    
    return fig

def create_accumulation_chart(df):
    """Gráfico de acumulação estilo montanha."""
    if df.empty or 'Data' not in df.columns:
        return go.Figure()
    
    df_sorted = df.sort_values('Data').copy()
    df_sorted['Total_Acumulado'] = df_sorted['Total'].cumsum()
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=df_sorted['Data'],
        y=df_sorted['Total_Acumulado'],
        mode='lines',
        fill='tonexty',
        name='Capital Acumulado',
        line=dict(color=DARK_THEME['primary'], width=3),
        fillcolor=f"rgba(0, 212, 170, 0.3)"
    ))
    
    fig.update_layout(
        title='💰 Evolução do Capital Acumulado',
        plot_bgcolor=DARK_THEME['background'],
        paper_bgcolor=DARK_THEME['surface'],
        font_color=DARK_THEME['text'],
        title_font_size=18,
        xaxis=dict(gridcolor='#404040', title='Data'),
        yaxis=dict(gridcolor='#404040', title='Capital (R$)', tickformat=',.0f')
    )
    
    return fig

def create_sales_histogram(df):
    """Histograma de distribuição de vendas."""
    if df.empty or 'Total' not in df.columns:
        return go.Figure()
    
    df_filtered = df[df['Total'] > 0]
    
    if df_filtered.empty:
        return go.Figure()
    
    fig = px.histogram(df_filtered, x='Total', nbins=20,
                       title='📊 Distribuição dos Valores de Venda',
                       color_discrete_sequence=[DARK_THEME['accent']])
    
    fig.update_layout(
        plot_bgcolor=DARK_THEME['background'],
        paper_bgcolor=DARK_THEME['surface'],
        font_color=DARK_THEME['text'],
        title_font_size=18,
        xaxis=dict(gridcolor='#404040', title='Valor da Venda (R$)'),
        yaxis=dict(gridcolor='#404040', title='Frequência')
    )
    
    return fig

# --- Inicialização do App ---
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.CYBORG], suppress_callback_exceptions=True)
server = app.server

# CSS customizado para modo escuro
custom_css = {
    'backgroundColor': DARK_THEME['background'],
    'color': DARK_THEME['text'],
    'minHeight': '100vh'
}

# --- Layout Principal ---
app.layout = dbc.Container([
    dcc.Store(id='store-sales-data'),
    dcc.Store(id='store-filtered-data'),
    dcc.Interval(id='interval-component', interval=30*1000, n_intervals=0),  # Atualiza a cada 30s
    
    # Header
    dbc.Row([
        dbc.Col([
            html.Div([
                html.H1("🍔 SISTEMA FINANCEIRO - CLIP'S BURGER", 
                       className="text-center mb-2", 
                       style={'color': DARK_THEME['primary'], 'fontWeight': 'bold', 'fontSize': '2.5rem'}),
                html.P("Gestão inteligente de vendas com análise financeira em tempo real", 
                      className="text-center", 
                      style={'color': DARK_THEME['text_secondary'], 'fontSize': '1.2rem'})
            ])
        ], width=12)
    ], className="mb-4 mt-3"),
    
    # Tabs principais
    dbc.Tabs([
        # TAB 1: Registrar Venda
        dbc.Tab(label="📝 Registrar Venda", tab_id="tab-registro", active_tab_style={'backgroundColor': DARK_THEME['primary']}),
        dbc.Tab(label="📈 Análise Detalhada", tab_id="tab-analise", active_tab_style={'backgroundColor': DARK_THEME['primary']}),
        dbc.Tab(label="💡 Estatísticas", tab_id="tab-estatisticas", active_tab_style={'backgroundColor': DARK_THEME['primary']}),
        dbc.Tab(label="💰 Análise Contábil", tab_id="tab-contabil", active_tab_style={'backgroundColor': DARK_THEME['primary']})
    ], id="tabs", active_tab="tab-registro", style={'backgroundColor': DARK_THEME['surface']}),
    
    html.Div(id='tab-content', className="mt-4")
    
], fluid=True, style=custom_css)

# --- Callbacks ---

# Callback para gerenciar conteúdo das tabs
@app.callback(
    Output('tab-content', 'children'),
    Input('tabs', 'active_tab'),
    Input('store-filtered-data', 'data')
)
def render_tab_content(active_tab, filtered_data):
    if active_tab == "tab-registro":
        return render_registro_tab()
    elif active_tab == "tab-analise":
        return render_analise_tab(filtered_data)
    elif active_tab == "tab-estatisticas":
        return render_estatisticas_tab(filtered_data)
    elif active_tab == "tab-contabil":
        return render_contabil_tab(filtered_data)
    
    return html.Div("Selecione uma aba")

def render_registro_tab():
    """Renderiza a tab de registro de vendas."""
    return dbc.Row([
        dbc.Col([
            # Sidebar com filtros
            dbc.Card([
                dbc.CardHeader([
                    html.H4("🔍 Filtros de Período", className="mb-0", style={'color': DARK_THEME['text']})
                ]),
                dbc.CardBody([
                    html.Label("📅 Filtrar por Ano:", style={'color': DARK_THEME['text']}),
                    dcc.Dropdown(
                        id='filter-anos',
                        multi=True,
                        placeholder="Selecione os anos...",
                        style={'backgroundColor': DARK_THEME['surface'], 'color': DARK_THEME['text']}
                    ),
                    html.Br(),
                    html.Label("📆 Filtrar por Mês:", style={'color': DARK_THEME['text']}),
                    dcc.Dropdown(
                        id='filter-meses',
                        multi=True,
                        placeholder="Selecione os meses...",
                        style={'backgroundColor': DARK_THEME['surface'], 'color': DARK_THEME['text']}
                    ),
                    html.Br(),
                    html.Label("🔄 Últimos N dias:", style={'color': DARK_THEME['text']}),
                    dcc.Dropdown(
                        id='filter-dias',
                        options=[
                            {'label': 'Último 1 dia', 'value': 1},
                            {'label': 'Últimos 3 dias', 'value': 3},
                            {'label': 'Últimos 7 dias', 'value': 7},
                            {'label': 'Últimos 15 dias', 'value': 15},
                            {'label': 'Últimos 30 dias', 'value': 30}
                        ],
                        multi=True,
                        value=[7],
                        style={'backgroundColor': DARK_THEME['surface'], 'color': DARK_THEME['text']}
                    ),
                    html.Hr(),
                    html.Div(id='filter-summary')
                ])
            ], style={'backgroundColor': DARK_THEME['card_bg']})
        ], width=3),
        
        dbc.Col([
            # Formulário de registro
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
                    
                    html.Div(id='total-preview', className="mb-3"),
                    
                    dbc.Button("✅ Registrar Venda", id='submit-button', color="success", size="lg", className="w-100"),
                    html.Div(id='output-message', className="mt-3")
                ])
            ], style={'backgroundColor': DARK_THEME['card_bg']})
        ], width=9)
    ])

def render_analise_tab(filtered_data):
    """Renderiza a tab de análise detalhada."""
    if not filtered_data:
        return html.Div("Carregando dados...", style={'color': DARK_THEME['text']})
    
    df = pd.read_json(filtered_data, orient='split')
    df['Data'] = pd.to_datetime(df['Data'])
    
    return [
        # Métricas principais
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H4("📊 Resumo Financeiro", className="text-center mb-3", style={'color': DARK_THEME['text']}),
                        html.Div(id='metrics-cards-analise')
                    ])
                ], style={'backgroundColor': DARK_THEME['card_bg']})
            ], width=12)
        ], className="mb-4"),
        
        # Gráficos principais
        dbc.Row([
            dbc.Col([
                dcc.Graph(id='daily-sales-chart-analise')
            ], width=12, lg=6),
            dbc.Col([
                dcc.Graph(id='payment-method-chart-analise')
            ], width=12, lg=6)
        ], className="mb-4"),
        
        dbc.Row([
            dbc.Col([
                dcc.Graph(id='weekly-pattern-chart-analise')
            ], width=12, lg=6),
            dbc.Col([
                dcc.Graph(id='accumulation-chart-analise')
            ], width=12, lg=6)
        ], className="mb-4"),
        
        # Tabela de dados
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.H4("📋 Histórico Detalhado", className="mb-0", style={'color': DARK_THEME['text']})
                    ]),
                    dbc.CardBody([
                        html.Div(id='sales-table-analise')
                    ])
                ], style={'backgroundColor': DARK_THEME['card_bg']})
            ], width=12)
        ])
    ]

def render_estatisticas_tab(filtered_data):
    """Renderiza a tab de estatísticas."""
    if not filtered_data:
        return html.Div("Carregando dados...", style={'color': DARK_THEME['text']})
    
    return [
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H4("💡 Estatísticas Avançadas", className="text-center mb-3", style={'color': DARK_THEME['text']}),
                        html.Div(id='advanced-stats')
                    ])
                ], style={'backgroundColor': DARK_THEME['card_bg']})
            ], width=12)
        ], className="mb-4"),
        
        dbc.Row([
            dbc.Col([
                dcc.Graph(id='payment-evolution-chart')
            ], width=12, lg=6),
            dbc.Col([
                dcc.Graph(id='sales-histogram-chart')
            ], width=12, lg=6)
        ], className="mb-4"),
        
        dbc.Row([
            dbc.Col([
                dcc.Graph(id='monthly-trend-chart-stats')
            ], width=12)
        ])
    ]

def render_contabil_tab(filtered_data):
    """Renderiza a tab de análise contábil."""
    return [
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.H4("📊 Análise Contábil Completa", className="mb-0", style={'color': DARK_THEME['text']})
                    ]),
                    dbc.CardBody([
                        html.P("Configure os parâmetros para simulação contábil:", style={'color': DARK_THEME['text_secondary']}),
                        
                        dbc.Row([
                            dbc.Col([
                                html.Label("💼 Salário Base (R$):", style={'color': DARK_THEME['text']}),
                                dbc.Input(id='salario-input', type='number', value=1550, min=0, step=0.01)
                            ], width=4),
                            dbc.Col([
                                html.Label("📋 Honorários Contábeis (R$):", style={'color': DARK_THEME['text']}),
                                dbc.Input(id='contadora-input', type='number', value=316, min=0, step=0.01)
                            ], width=4),
                            dbc.Col([
                                html.Label("📦 Custo Produtos (%):", style={'color': DARK_THEME['text']}),
                                dbc.Input(id='fornecedores-input', type='number', value=30, min=0, max=100, step=0.1)
                            ], width=4)
                        ], className="mb-3"),
                        
                        html.Div(id='contabil-results')
                    ])
                ], style={'backgroundColor': DARK_THEME['card_bg']})
            ], width=12)
        ])
    ]

# Callback para carregar dados iniciais
@app.callback(
    Output('store-sales-data', 'data'),
    Input('interval-component', 'n_intervals')
)
def load_sales_data(n_intervals):
    df = read_sales_data()
    df_processed = process_data(df)
    return df_processed.to_json(date_format='iso', orient='split')

# Callback para atualizar filtros
@app.callback(
    [Output('filter-anos', 'options'),
     Output('filter-anos', 'value'),
     Output('filter-meses', 'options'),
     Output('filter-meses', 'value')],
    Input('store-sales-data', 'data')
)
def update_filter_options(data_json):
    if not data_json:
        return [], [], [], []
    
    df = pd.read_json(data_json, orient='split')
    df['Data'] = pd.to_datetime(df['Data'])
    
    if df.empty:
        return [], [], [], []
    
    # Opções de anos
    anos_disponiveis = sorted(df['Ano'].dropna().unique().astype(int), reverse=True)
    anos_options = [{'label': str(ano), 'value': ano} for ano in anos_disponiveis]
    ano_atual = datetime.now().year
    anos_default = [ano_atual] if ano_atual in anos_disponiveis else [anos_disponiveis[0]] if anos_disponiveis else []
    
    # Opções de meses
    meses_disponiveis = sorted(df['Mês'].dropna().unique().astype(int))
    meses_options = [{'label': f"{mes} - {meses_ordem[mes-1]}", 'value': mes} for mes in meses_disponiveis if 1 <= mes <= 12]
    mes_atual = datetime.now().month
    meses_default = [mes_atual] if mes_atual in meses_disponiveis else meses_disponiveis
    
    return anos_options, anos_default, meses_options, meses_default

# Callback para aplicar filtros
@app.callback(
    [Output('store-filtered-data', 'data'),
     Output('filter-summary', 'children')],
    [Input('store-sales-data', 'data'),
     Input('filter-anos', 'value'),
     Input('filter-meses', 'value'),
     Input('filter-dias', 'value')]
)
def apply_filters(data_json, selected_anos, selected_meses, selected_dias):
    if not data_json:
        return None, "Sem dados disponíveis"
    
    df = pd.read_json(data_json, orient='split')
    df['Data'] = pd.to_datetime(df['Data'])
    
    df_filtered = df.copy()
    
    # Aplicar filtros
    if selected_anos and 'Ano' in df_filtered.columns:
        df_filtered = df_filtered[df_filtered['Ano'].isin(selected_anos)]
    
    if selected_meses and 'Mês' in df_filtered.columns:
        df_filtered = df_filtered[df_filtered['Mês'].isin(selected_meses)]
    
    if selected_dias:
        df_filtered = filter_by_rolling_days(df_filtered, selected_dias)
    
    # Resumo dos filtros
    total_registros = len(df_filtered)
    total_faturamento = df_filtered['Total'].sum() if not df_filtered.empty else 0
    
    summary = [
        html.H6("📈 Resumo dos Filtros", style={'color': DARK_THEME['primary']}),
        html.P(f"Registros: {total_registros}", style={'color': DARK_THEME['text']}),
        html.P(f"Faturamento: {format_brl(total_faturamento)}", style={'color': DARK_THEME['text']})
    ]
    
    return df_filtered.to_json(date_format='iso', orient='split'), summary

# Callback para preview do total da venda
@app.callback(
    Output('total-preview', 'children'),
    [Input('input-cartao', 'value'),
     Input('input-dinheiro', 'value'),
     Input('input-pix', 'value')]
)
def update_total_preview(cartao, dinheiro, pix):
    total = (cartao or 0) + (dinheiro or 0) + (pix or 0)
    return html.H5(f"💰 Total: {format_brl(total)}", 
                   style={'color': DARK_THEME['success'] if total > 0 else DARK_THEME['text_secondary']})

# Callback para registrar venda
@app.callback(
    [Output('output-message', 'children'),
     Output('input-cartao', 'value'),
     Output('input-dinheiro', 'value'),
     Output('input-pix', 'value')],
    Input('submit-button', 'n_clicks'),
    [State('input-date', 'date'),
     State('input-cartao', 'value'),
     State('input-dinheiro', 'value'),
     State('input-pix', 'value')],
    prevent_initial_call=True
)
def submit_new_sale(n_clicks, date_val, cartao_val, dinheiro_val, pix_val):
    if not date_val:
        return dbc.Alert("Por favor, selecione uma data.", color="warning"), dash.no_update, dash.no_update, dash.no_update
    
    cartao = float(cartao_val) if cartao_val else 0.0
    dinheiro = float(dinheiro_val) if dinheiro_val else 0.0
    pix = float(pix_val) if pix_val else 0.0
    
    if cartao == 0.0 and dinheiro == 0.0 and pix == 0.0:
        return dbc.Alert("Insira pelo menos um valor.", color="warning"), dash.no_update, dash.no_update, dash.no_update

    success, message = add_data_to_sheet(date_val, cartao, dinheiro, pix)
    
    alert_color = "success" if success else "danger"
    alert_message = dbc.Alert(message, color=alert_color, dismissable=True)
    
    if success:
        return alert_message, None, None, None  # Limpa os campos
    else:
        return alert_message, dash.no_update, dash.no_update, dash.no_update

# Callbacks para gráficos da análise
@app.callback(
    [Output('metrics-cards-analise', 'children'),
     Output('daily-sales-chart-analise', 'figure'),
     Output('payment-method-chart-analise', 'figure'),
     Output('weekly-pattern-chart-analise', 'figure'),
     Output('accumulation-chart-analise', 'figure'),
     Output('sales-table-analise', 'children')],
    Input('store-filtered-data', 'data')
)
def update_analise_charts(data_json):
    if not data_json:
        empty_fig = go.Figure()
        return [], empty_fig, empty_fig, empty_fig, empty_fig, "Sem dados disponíveis"
    
    df = pd.read_json(data_json, orient='split')
    df['Data'] = pd.to_datetime(df['Data'])
    
    # Métricas
    total_vendas = df['Total'].sum()
    vendas_hoje = df[df['Data'].dt.date == date.today()]['Total'].sum()
    media_diaria = df.groupby(df['Data'].dt.date)['Total'].sum().mean() if not df.empty else 0
    num_dias = df['Data'].dt.date.nunique()
    
    metrics = dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H3(f"{format_brl(total_vendas)}", className="text-success"),
                    html.P("Total Vendas", className="text-muted")
                ])
            ], style={'backgroundColor': DARK_THEME['background']})
        ], width=3),
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H3(f"{format_brl(vendas_hoje)}", className="text-info"),
                    html.P("Vendas Hoje", className="text-muted")
                ])
            ], style={'backgroundColor': DARK_THEME['background']})
        ], width=3),
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H3(f"{format_brl(media_diaria)}", className="text-warning"),
                    html.P("Média Diária", className="text-muted")
                ])
            ], style={'backgroundColor': DARK_THEME['background']})
        ], width=3),
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H3(f"{num_dias}", style={'color': DARK_THEME['primary']}),
                    html.P("Dias com Vendas", className="text-muted")
                ])
            ], style={'backgroundColor': DARK_THEME['background']})
        ], width=3)
    ])
    
    # Gráficos
    daily_chart = create_daily_sales_chart(df)
    payment_chart = create_payment_method_chart(df)
    weekly_chart = create_weekly_pattern_chart(df)
    accumulation_chart = create_accumulation_chart(df)
    
    # Tabela
    table_data = df[['DataFormatada', 'DiaSemana', 'Cartão', 'Dinheiro', 'Pix', 'Total']].tail(15)
    
    table = dash_table.DataTable(
        data=table_data.to_dict('records'),
        columns=[
            {'name': 'Data', 'id': 'DataFormatada'},
            {'name': 'Dia', 'id': 'DiaSemana'},
            {'name': 'Cartão (R$)', 'id': 'Cartão', 'type': 'numeric', 'format': {'specifier': ',.2f'}},
            {'name': 'Dinheiro (R$)', 'id': 'Dinheiro', 'type': 'numeric', 'format': {'specifier': ',.2f'}},
            {'name': 'Pix (R$)', 'id': 'Pix', 'type': 'numeric', 'format': {'specifier': ',.2f'}},
            {'name': 'Total (R$)', 'id': 'Total', 'type': 'numeric', 'format': {'specifier': ',.2f'}}
        ],
        style_cell={
            'textAlign': 'center', 
            'backgroundColor': DARK_THEME['surface'], 
            'color': DARK_THEME['text'],
            'border': '1px solid #404040'
        },
        style_header={
            'backgroundColor': DARK_THEME['primary'], 
            'color': 'white', 
            'fontWeight': 'bold'
        },
        style_data_conditional=[
            {
                'if': {'row_index': 'odd'},
                'backgroundColor': DARK_THEME['background']
            }
        ],
        page_size=10
    )
    
    return metrics, daily_chart, payment_chart, weekly_chart, accumulation_chart, table

# Callbacks para estatísticas
@app.callback(
    [Output('advanced-stats', 'children'),
     Output('payment-evolution-chart', 'figure'),
     Output('sales-histogram-chart', 'figure'),
     Output('monthly-trend-chart-stats', 'figure')],
    Input('store-filtered-data', 'data')
)
def update_statistics_charts(data_json):
    if not data_json:
        empty_fig = go.Figure()
        return "Sem dados disponíveis", empty_fig, empty_fig, empty_fig
    
    df = pd.read_json(data_json, orient='split')
    df['Data'] = pd.to_datetime(df['Data'])
    
    # Estatísticas avançadas
    if not df.empty:
        # Análise por dia da semana
        best_weekday = None
        if 'DiaSemana' in df.columns:
            avg_by_weekday = df.groupby('DiaSemana')['Total'].mean()
            if not avg_by_weekday.empty:
                best_weekday = avg_by_weekday.idxmax()
        
        # Tendências
        total_vendas = df['Total'].sum()
        cartao_pct = (df['Cartão'].sum() / total_vendas * 100) if total_vendas > 0 else 0
        dinheiro_pct = (df['Dinheiro'].sum() / total_vendas * 100) if total_vendas > 0 else 0
        pix_pct = (df['Pix'].sum() / total_vendas * 100) if total_vendas > 0 else 0
        
        stats_content = [
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H5("🏆 Melhor Dia da Semana", style={'color': DARK_THEME['primary']}),
                            html.H4(best_weekday or "N/A", style={'color': DARK_THEME['success']})
                        ])
                    ], style={'backgroundColor': DARK_THEME['background']})
                ], width=4),
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H5("💳 Preferência de Pagamento", style={'color': DARK_THEME['primary']}),
                            html.P(f"Cartão: {cartao_pct:.1f}%", style={'color': DARK_THEME['text']}),
                            html.P(f"Dinheiro: {dinheiro_pct:.1f}%", style={'color': DARK_THEME['text']}),
                            html.P(f"Pix: {pix_pct:.1f}%", style={'color': DARK_THEME['text']})
                        ])
                    ], style={'backgroundColor': DARK_THEME['background']})
                ], width=4),
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H5("📊 Variação de Vendas", style={'color': DARK_THEME['primary']}),
                            html.P(f"Maior: {format_brl(df['Total'].max())}", style={'color': DARK_THEME['success']}),
                            html.P(f"Menor: {format_brl(df['Total'].min())}", style={'color': DARK_THEME['danger']}),
                            html.P(f"Desvio: {format_brl(df['Total'].std())}", style={'color': DARK_THEME['text']})
                        ])
                    ], style={'backgroundColor': DARK_THEME['background']})
                ], width=4)
            ])
        ]
    else:
        stats_content = [html.P("Sem dados para análise", style={'color': DARK_THEME['text']})]
    
    # Gráficos
    evolution_chart = create_payment_evolution_chart(df)
    histogram_chart = create_sales_histogram(df)
    monthly_chart = create_monthly_trend_chart(df)
    
    return stats_content, evolution_chart, histogram_chart, monthly_chart

# Callback para análise contábil
@app.callback(
    Output('contabil-results', 'children'),
    [Input('store-filtered-data', 'data'),
     Input('salario-input', 'value'),
     Input('contadora-input', 'value'),
     Input('fornecedores-input', 'value')]
)
def update_contabil_analysis(data_json, salario, contadora, fornecedores):
    if not data_json:
        return "Carregando dados..."
    
    df = pd.read_json(data_json, orient='split')
    
    if df.empty:
        return "Sem dados para análise contábil"
    
    # Calcular resultados
    results = calculate_financial_results(df, salario or 1550, contadora or 316, fornecedores or 30)
    
    return [
        # DRE Simplificado
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.H5("💰 Demonstrativo de Resultados", style={'color': DARK_THEME['text']})
                    ]),
                    dbc.CardBody([
                        html.Table([
                            html.Tr([html.Td("(+) Faturamento Bruto", style={'color': DARK_THEME['text']}), 
                                   html.Td(format_brl(results['faturamento_bruto']), style={'color': DARK_THEME['success'], 'textAlign': 'right'})]),
                            html.Tr([html.Td("(-) Impostos Simples Nacional", style={'color': DARK_THEME['text']}), 
                                   html.Td(format_brl(-results['imposto_simples']), style={'color': DARK_THEME['danger'], 'textAlign': 'right'})]),
                            html.Tr([html.Td("(-) Custo dos Produtos", style={'color': DARK_THEME['text']}), 
                                   html.Td(format_brl(-results['custo_fornecedores_valor']), style={'color': DARK_THEME['danger'], 'textAlign': 'right'})]),
                            html.Tr([html.Td("(-) Folha de Pagamento", style={'color': DARK_THEME['text']}), 
                                   html.Td(format_brl(-results['custo_funcionario']), style={'color': DARK_THEME['danger'], 'textAlign': 'right'})]),
                            html.Tr([html.Td("(-) Honorários Contábeis", style={'color': DARK_THEME['text']}), 
                                   html.Td(format_brl(-results['custo_contadora']), style={'color': DARK_THEME['danger'], 'textAlign': 'right'})]),
                            html.Tr([html.Td(html.B("(=) Lucro Operacional"), style={'color': DARK_THEME['primary']}), 
                                   html.Td(html.B(format_brl(results['lucro_bruto'])), 
                                          style={'color': DARK_THEME['success'] if results['lucro_bruto'] >= 0 else DARK_THEME['danger'], 
                                                'textAlign': 'right'})])
                        ], style={'width': '100%'})
                    ])
                ], style={'backgroundColor': DARK_THEME['card_bg']})
            ], width=6),
            
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.H5("📊 Indicadores Financeiros", style={'color': DARK_THEME['text']})
                    ]),
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col([
                                html.H6("Margem Operacional", style={'color': DARK_THEME['text']}),
                                html.H4(f"{results['margem_lucro_bruto']:.1f}%", 
                                        style={'color': DARK_THEME['success'] if results['margem_lucro_bruto'] >= 0 else DARK_THEME['danger']})
                            ], width=6),
                            dbc.Col([
                                html.H6("Carga Tributária", style={'color': DARK_THEME['text']}),
                                html.H4(f"{(results['imposto_simples'] / results['faturamento_bruto'] * 100) if results['faturamento_bruto'] > 0 else 0:.1f}%", 
                                        style={'color': DARK_THEME['warning']})
                            ], width=6)
                        ]),
                        dbc.Row([
                            dbc.Col([
                                html.H6("Custo Pessoal", style={'color': DARK_THEME['text']}),
                                html.H4(f"{(results['custo_funcionario'] / results['faturamento_bruto'] * 100) if results['faturamento_bruto'] > 0 else 0:.1f}%", 
                                        style={'color': DARK_THEME['secondary']})
                            ], width=6),
                            dbc.Col([
                                html.H6("Custo Produtos", style={'color': DARK_THEME['text']}),
                                html.H4(f"{fornecedores or 30:.1f}%", 
                                        style={'color': DARK_THEME['accent']})
                            ], width=6)
                        ])
                    ])
                ], style={'backgroundColor': DARK_THEME['card_bg']})
            ], width=6)
        ], className="mb-4"),
        
        # Gráfico de composição de custos
        dbc.Row([
            dbc.Col([
                dcc.Graph(
                    figure=create_cost_breakdown_chart(results),
                    style={'height': '400px'}
                )
            ], width=12)
        ])
    ]

def create_cost_breakdown_chart(results):
    """Cria gráfico de composição de custos."""
    custos = {
        'Impostos': results['imposto_simples'],
        'Pessoal': results['custo_funcionario'],
        'Contabilidade': results['custo_contadora'],
        'Produtos': results['custo_fornecedores_valor']
    }
    
    # Remove custos zero
    custos = {k: v for k, v in custos.items() if v > 0}
    
    if not custos:
        return go.Figure()
    
    fig = px.pie(values=list(custos.values()), 
                 names=list(custos.keys()),
                 title='💸 Composição dos Custos Operacionais',
                 color_discrete_sequence=[DARK_THEME['danger'], DARK_THEME['secondary'], DARK_THEME['warning'], DARK_THEME['accent']])
    
    fig.update_layout(
        plot_bgcolor=DARK_THEME['background'],
        paper_bgcolor=DARK_THEME['surface'],
        font_color=DARK_THEME['text'],
        title_font_size=18
    )
    
    return fig

if __name__ == '__main__':
    print("🚀 Iniciando Clip's Burger Dashboard em Dash...")
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 8050)))
