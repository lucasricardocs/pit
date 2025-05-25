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

# Tema escuro elegante
DARK_THEME = {
    'background': '#0f1419',
    'surface': '#1a1f2e',
    'card_bg': '#252d3d',
    'primary': '#00d4aa',
    'secondary': '#ff6b6b',
    'accent': '#ffd43b',
    'text': '#ffffff',
    'text_secondary': '#8892b0',
    'success': '#51cf66',
    'warning': '#ffd43b',
    'danger': '#ff6b6b',
    'gradient': 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'
}

# Define ordem dos dias e meses
dias_semana_ordem = ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"]
meses_ordem = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]

# --- Funções de Autenticação ---
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
                if df['Data'].isnull().all():
                    df['Data'] = pd.to_datetime(df['Data'], dayfirst=True, errors='coerce')
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
        try:
            if not pd.api.types.is_datetime64_any_dtype(df['Data']):
                df['Data'] = pd.to_datetime(df['Data'], dayfirst=True, errors='coerce')
            
            df = df.dropna(subset=['Data']).copy()
            
            if not df.empty:
                df['Ano'] = df['Data'].dt.year
                df['Mês'] = df['Data'].dt.month
                df['MêsNome'] = df['Mês'].apply(lambda x: meses_ordem[int(x)-1] if pd.notna(x) and 1 <= int(x) <= 12 else 'Inválido')
                
                day_map = {0: "Segunda-feira", 1: "Terça-feira", 2: "Quarta-feira", 3: "Quinta-feira", 4: "Sexta-feira", 5: "Sábado", 6: "Domingo"}
                df['DiaSemana'] = df['Data'].dt.dayofweek.map(day_map)
                df['DataFormatada'] = df['Data'].dt.strftime('%d/%m/%Y')
                df['AnoMês'] = df['Data'].dt.strftime('%Y-%m')
                df['DiaDoMes'] = df['Data'].dt.day
                
                # Categorias ordenadas
                df['DiaSemana'] = pd.Categorical(df['DiaSemana'], categories=dias_semana_ordem, ordered=True)
                df['MêsNome'] = pd.Categorical(df['MêsNome'], categories=meses_ordem, ordered=True)
        except Exception as e:
            print(f"❌ Erro ao processar datas: {e}")
    
    return df

def filter_by_rolling_days(df, dias_selecionados):
    """Filtra DataFrame para últimos N dias."""
    if df.empty or not dias_selecionados or 'Data' not in df.columns:
        return df
    
    try:
        data_mais_recente = df['Data'].max()
        max_dias = max(dias_selecionados)
        data_inicio = data_mais_recente - timedelta(days=max_dias - 1)
        
        return df[df['Data'] >= data_inicio].copy()
    except Exception as e:
        print(f"❌ Erro no filtro de dias: {e}")
        return df

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

def analyze_sales_by_weekday(df):
    """Analisa vendas por dia da semana."""
    if df.empty or 'DiaSemana' not in df.columns or 'Total' not in df.columns:
        return None, None
    
    try:
        df_copy = df.copy()
        df_copy['Total'] = pd.to_numeric(df_copy['Total'], errors='coerce')
        df_copy.dropna(subset=['Total', 'DiaSemana'], inplace=True)
        
        if df_copy.empty:
            return None, None
        
        avg_sales_weekday = df_copy.groupby('DiaSemana', observed=False)['Total'].mean().reindex(dias_semana_ordem).dropna()
        
        if not avg_sales_weekday.empty:
            best_day = avg_sales_weekday.idxmax()
            return best_day, avg_sales_weekday
        else:
            return None, avg_sales_weekday
    except Exception as e:
        print(f"❌ Erro ao analisar vendas por dia da semana: {e}")
        return None, None

# --- Funções para Gráficos ---
def create_daily_sales_chart(df):
    """Gráfico de vendas diárias."""
    if df.empty or 'Data' not in df.columns:
        fig = go.Figure()
        fig.add_annotation(text="Sem dados disponíveis", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        return fig
    
    daily_sales = df.groupby('Data')['Total'].sum().reset_index()
    
    if daily_sales.empty:
        fig = go.Figure()
        fig.add_annotation(text="Sem dados para o período selecionado", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        return fig
    
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
        fig = go.Figure()
        fig.add_annotation(text="Sem dados de pagamento", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        return fig
    
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
    
    df_valid = df[df['DiaSemana'].notna() & (df['Total'] > 0)].copy()
    
    if df_valid.empty:
        fig = go.Figure()
        fig.add_annotation(text="Sem dados válidos para análise semanal", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        return fig
    
    weekly_sales = df_valid.groupby('DiaSemana')['Total'].mean().reindex(dias_semana_ordem).fillna(0)
    
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

def create_payment_evolution_chart(df):
    """Gráfico de evolução dos métodos de pagamento."""
    if df.empty or 'AnoMês' not in df.columns:
        return go.Figure()
    
    df_chart = df.sort_values('AnoMês')
    monthly_payments = df_chart.groupby('AnoMês')[['Cartão', 'Dinheiro', 'Pix']].sum().reset_index()
    
    fig = go.Figure()
    
    for method in ['Cartão', 'Dinheiro', 'Pix']:
        fig.add_trace(go.Scatter(
            x=monthly_payments['AnoMês'],
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

# CSS customizado
custom_css = {
    'backgroundColor': DARK_THEME['background'],
    'color': DARK_THEME['text'],
    'minHeight': '100vh',
    'fontFamily': "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif"
}

# --- Layout Principal ---
app.layout = dbc.Container([
    dcc.Store(id='store-sales-data'),
    dcc.Store(id='store-filtered-data'),
    dcc.Interval(id='interval-component', interval=60*1000, n_intervals=0),
    
    # Header com logo
    dbc.Row([
        dbc.Col([
            html.Div([
                dbc.Row([
                    dbc.Col([
                        html.Img(
                            src=app.get_asset_url('logo.png'),
                            height="80px",
                            style={
                                'marginRight': '20px',
                                'filter': 'drop-shadow(0 4px 8px rgba(0, 212, 170, 0.3))'
                            }
                        ) if os.path.exists('assets/logo.png') else html.Div("🍔", style={'fontSize': '60px', 'marginRight': '20px'})
                    ], width="auto", className="d-flex align-items-center"),
                    dbc.Col([
                        html.H1("SISTEMA FINANCEIRO", 
                               style={
                                   'color': DARK_THEME['text'], 
                                   'fontWeight': 'bold', 
                                   'fontSize': '2.5rem',
                                   'marginBottom': '0',
                                   'textShadow': '2px 2px 4px rgba(0,0,0,0.5)'
                               }),
                        html.H2("CLIP'S BURGER", 
                               style={
                                   'color': DARK_THEME['primary'], 
                                   'fontWeight': 'bold', 
                                   'fontSize': '2rem',
                                   'marginBottom': '5px',
                                   'textShadow': '2px 2px 4px rgba(0,0,0,0.5)'
                               }),
                        html.P("Gestão inteligente de vendas com análise financeira em tempo real", 
                              style={
                                  'color': DARK_THEME['text_secondary'], 
                                  'fontSize': '1.1rem',
                                  'marginBottom': '0'
                              })
                    ], className="d-flex flex-column justify-content-center")
                ], className="align-items-center")
            ], style={
                'background': DARK_THEME['gradient'],
                'padding': '20px',
                'borderRadius': '15px',
                'boxShadow': '0 8px 32px rgba(0, 212, 170, 0.2)',
                'border': f'1px solid {DARK_THEME["primary"]}40'
            })
        ], width=12)
    ], className="mb-4 mt-3"),
    
    # Tabs principais
    dbc.Tabs([
        dbc.Tab(
            label="📝 Registrar Venda", 
            tab_id="tab-registro",
            active_tab_style={'backgroundColor': DARK_THEME['primary'], 'color': 'white', 'fontWeight': 'bold'},
            tab_style={'backgroundColor': DARK_THEME['surface'], 'color': DARK_THEME['text']}
        ),
        dbc.Tab(
            label="📈 Análise Detalhada", 
            tab_id="tab-analise",
            active_tab_style={'backgroundColor': DARK_THEME['primary'], 'color': 'white', 'fontWeight': 'bold'},
            tab_style={'backgroundColor': DARK_THEME['surface'], 'color': DARK_THEME['text']}
        ),
        dbc.Tab(
            label="💡 Estatísticas", 
            tab_id="tab-estatisticas",
            active_tab_style={'backgroundColor': DARK_THEME['primary'], 'color': 'white', 'fontWeight': 'bold'},
            tab_style={'backgroundColor': DARK_THEME['surface'], 'color': DARK_THEME['text']}
        ),
        dbc.Tab(
            label="💰 Análise Contábil", 
            tab_id="tab-contabil",
            active_tab_style={'backgroundColor': DARK_THEME['primary'], 'color': 'white', 'fontWeight': 'bold'},
            tab_style={'backgroundColor': DARK_THEME['surface'], 'color': DARK_THEME['text']}
        )
    ], id="tabs", active_tab="tab-registro", style={'backgroundColor': DARK_THEME['surface']}),
    
    html.Div(id='tab-content', className="mt-4")
    
], fluid=True, style=custom_css)

# --- Callbacks ---

@app.callback(
    Output('store-sales-data', 'data'),
    Input('interval-component', 'n_intervals')
)
def load_sales_data(n_intervals):
    try:
        df = read_sales_data()
        df_processed = process_data(df)
        print(f"✅ Dados carregados: {len(df_processed)} registros")
        return df_processed.to_json(date_format='iso', orient='split')
    except Exception as e:
        print(f"❌ Erro ao carregar dados: {e}")
        return pd.DataFrame().to_json(date_format='iso', orient='split')

@app.callback(
    Output('tab-content', 'children'),
    [Input('tabs', 'active_tab'),
     Input('store-sales-data', 'data')]
)
def render_tab_content(active_tab, sales_data):
    if active_tab == "tab-registro":
        return render_registro_tab(sales_data)
    elif active_tab == "tab-analise":
        return render_analise_tab()
    elif active_tab == "tab-estatisticas":
        return render_estatisticas_tab()
    elif active_tab == "tab-contabil":
        return render_contabil_tab()
    
    return html.Div("Selecione uma aba")

def render_registro_tab(sales_data):
    """Renderiza a tab de registro de vendas."""
    # Processa dados para filtros
    if sales_data:
        try:
            df = pd.read_json(sales_data, orient='split')
            df['Data'] = pd.to_datetime(df['Data'])
        except:
            df = pd.DataFrame()
    else:
        df = pd.DataFrame()
    
    # Opções para filtros
    anos_options = []
    meses_options = []
    
    if not df.empty and 'Ano' in df.columns:
        anos_disponiveis = sorted(df['Ano'].dropna().unique().astype(int), reverse=True)
        anos_options = [{'label': str(ano), 'value': ano} for ano in anos_disponiveis]
        
        meses_disponiveis = sorted(df['Mês'].dropna().unique().astype(int))
        meses_options = [{'label': f"{mes} - {meses_ordem[mes-1]}", 'value': mes} 
                        for mes in meses_disponiveis if 1 <= mes <= 12]
    
    return dbc.Row([
        dbc.Col([
            # Sidebar com filtros
            dbc.Card([
                dbc.CardHeader([
                    html.H4("🔍 Filtros de Período", className="mb-0", style={'color': DARK_THEME['text']})
                ], style={'backgroundColor': DARK_THEME['primary']}),
                dbc.CardBody([
                    html.Label("📅 Filtrar por Ano:", style={'color': DARK_THEME['text'], 'fontWeight': 'bold'}),
                    dcc.Dropdown(
                        id='filter-anos',
                        options=anos_options,
                        multi=True,
                        placeholder="Selecione os anos...",
                        value=[datetime.now().year] if anos_options else [],
                        style={'backgroundColor': DARK_THEME['surface'], 'color': DARK_THEME['text']}
                    ),
                    html.Br(),
                    html.Label("📆 Filtrar por Mês:", style={'color': DARK_THEME['text'], 'fontWeight': 'bold'}),
                    dcc.Dropdown(
                        id='filter-meses',
                        options=meses_options,
                        multi=True,
                        placeholder="Selecione os meses...",
                        value=[datetime.now().month] if meses_options else [],
                        style={'backgroundColor': DARK_THEME['surface'], 'color': DARK_THEME['text']}
                    ),
                    html.Br(),
                    html.Label("🔄 Últimos N dias:", style={'color': DARK_THEME['text'], 'fontWeight': 'bold'}),
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
                ], style={'backgroundColor': DARK_THEME['card_bg']})
            ], style={'backgroundColor': DARK_THEME['card_bg']})
        ], width=3),
        
        dbc.Col([
            # Formulário de registro
            dbc.Card([
                dbc.CardHeader([
                    html.H4("💰 Registrar Nova Venda", className="mb-0", style={'color': 'white'})
                ], style={'backgroundColor': DARK_THEME['primary']}),
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col([
                            html.Label("📅 Data:", style={'color': DARK_THEME['text'], 'fontWeight': 'bold'}),
                            dcc.DatePickerSingle(
                                id='input-date',
                                date=date.today(),
                                display_format='DD/MM/YYYY',
                                style={'width': '100%'}
                            )
                        ], width=12, md=3),
                        dbc.Col([
                            html.Label("💳 Cartão (R$):", style={'color': DARK_THEME['text'], 'fontWeight': 'bold'}),
                            dbc.Input(
                                id='input-cartao', 
                                type='number', 
                                placeholder='0.00', 
                                min=0, 
                                step=0.01,
                                style={'backgroundColor': DARK_THEME['surface'], 'color': DARK_THEME['text']}
                            )
                        ], width=12, md=3),
                        dbc.Col([
                            html.Label("💵 Dinheiro (R$):", style={'color': DARK_THEME['text'], 'fontWeight': 'bold'}),
                            dbc.Input(
                                id='input-dinheiro', 
                                type='number', 
                                placeholder='0.00', 
                                min=0, 
                                step=0.01,
                                style={'backgroundColor': DARK_THEME['surface'], 'color': DARK_THEME['text']}
                            )
                        ], width=12, md=3),
                        dbc.Col([
                            html.Label("📱 Pix (R$):", style={'color': DARK_THEME['text'], 'fontWeight': 'bold'}),
                            dbc.Input(
                                id='input-pix', 
                                type='number', 
                                placeholder='0.00', 
                                min=0, 
                                step=0.01,
                                style={'backgroundColor': DARK_THEME['surface'], 'color': DARK_THEME['text']}
                            )
                        ], width=12, md=3)
                    ], className="mb-3"),
                    
                    html.Div(id='total-preview', className="mb-3"),
                    
                    dbc.Button(
                        "✅ Registrar Venda", 
                        id='submit-button', 
                        color="success", 
                        size="lg", 
                        className="w-100",
                        style={'fontWeight': 'bold'}
                    ),
                    html.Div(id='output-message', className="mt-3")
                ], style={'backgroundColor': DARK_THEME['card_bg']})
            ], style={'backgroundColor': DARK_THEME['card_bg']})
        ], width=9)
    ])

def render_analise_tab():
    """Renderiza a tab de análise detalhada."""
    return [
        html.Div(id='analise-content'),
        dcc.Store(id='store-filtered-analise')
    ]

def render_estatisticas_tab():
    """Renderiza a tab de estatísticas."""
    return [
        html.Div(id='estatisticas-content')
    ]

def render_contabil_tab():
    """Renderiza a tab de análise contábil."""
    return [
        html.Div(id='contabil-content')
    ]

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
    
    try:
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
            html.H6("📈 Resumo dos Filtros", style={'color': DARK_THEME['primary'], 'fontWeight': 'bold'}),
            html.P(f"📊 Registros: {total_registros}", style={'color': DARK_THEME['text']}),
            html.P(f"💰 Faturamento: {format_brl(total_faturamento)}", style={'color': DARK_THEME['success'], 'fontWeight': 'bold'})
        ]
        
        return df_filtered.to_json(date_format='iso', orient='split'), summary
        
    except Exception as e:
        print(f"❌ Erro ao aplicar filtros: {e}")
        return None, f"Erro ao aplicar filtros: {e}"

# Callback para preview do total da venda
@app.callback(
    Output('total-preview', 'children'),
    [Input('input-cartao', 'value'),
     Input('input-dinheiro', 'value'),
     Input('input-pix', 'value')]
)
def update_total_preview(cartao, dinheiro, pix):
    total = (cartao or 0) + (dinheiro or 0) + (pix or 0)
    return html.H5(
        f"💰 Total: {format_brl(total)}", 
        style={
            'color': DARK_THEME['success'] if total > 0 else DARK_THEME['text_secondary'],
            'textAlign': 'center',
            'padding': '10px',
            'backgroundColor': DARK_THEME['surface'],
            'borderRadius': '10px',
            'fontWeight': 'bold'
        }
    )

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
        return alert_message, None, None, None
    else:
        return alert_message, dash.no_update, dash.no_update, dash.no_update

# Callback para análise detalhada
@app.callback(
    Output('analise-content', 'children'),
    Input('store-filtered-data', 'data')
)
def update_analise_content(filtered_data):
    if not filtered_data:
        return html.Div("Carregando dados...", style={'color': DARK_THEME['text']})
    
    try:
        df = pd.read_json(filtered_data, orient='split')
        df['Data'] = pd.to_datetime(df['Data'])
        
        if df.empty:
            return html.Div("Nenhum dado corresponde aos filtros selecionados.", style={'color': DARK_THEME['text']})
        
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
                ], style={'backgroundColor': DARK_THEME['card_bg']})
            ], width=3),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H3(f"{format_brl(vendas_hoje)}", style={'color': DARK_THEME['primary']}),
                        html.P("Vendas Hoje", className="text-muted")
                    ])
                ], style={'backgroundColor': DARK_THEME['card_bg']})
            ], width=3),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H3(f"{format_brl(media_diaria)}", style={'color': DARK_THEME['warning']}),
                        html.P("Média Diária", className="text-muted")
                    ])
                ], style={'backgroundColor': DARK_THEME['card_bg']})
            ], width=3),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H3(f"{num_dias}", style={'color': DARK_THEME['secondary']}),
                        html.P("Dias com Vendas", className="text-muted")
                    ])
                ], style={'backgroundColor': DARK_THEME['card_bg']})
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
        
        return [
            # Métricas principais
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader([
                            html.H4("📊 Resumo Financeiro", className="text-center mb-0", style={'color': 'white'})
                        ], style={'backgroundColor': DARK_THEME['primary']}),
                        dbc.CardBody([
                            metrics
                        ], style={'backgroundColor': DARK_THEME['card_bg']})
                    ])
                ], width=12)
            ], className="mb-4"),
            
            # Gráficos
            dbc.Row([
                dbc.Col([
                    dcc.Graph(figure=daily_chart)
                ], width=12, lg=6),
                dbc.Col([
                    dcc.Graph(figure=payment_chart)
                ], width=12, lg=6)
            ], className="mb-4"),
            
            dbc.Row([
                dbc.Col([
                    dcc.Graph(figure=weekly_chart)
                ], width=12, lg=6),
                dbc.Col([
                    dcc.Graph(figure=accumulation_chart)
                ], width=12, lg=6)
            ], className="mb-4"),
            
            # Tabela
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader([
                            html.H4("📋 Histórico Detalhado", className="mb-0", style={'color': 'white'})
                        ], style={'backgroundColor': DARK_THEME['primary']}),
                        dbc.CardBody([
                            table
                        ], style={'backgroundColor': DARK_THEME['card_bg']})
                    ])
                ], width=12)
            ])
        ]
        
    except Exception as e:
        print(f"❌ Erro na análise: {e}")
        return html.Div(f"Erro ao processar dados: {e}", style={'color': DARK_THEME['danger']})

# Callback para estatísticas
@app.callback(
    Output('estatisticas-content', 'children'),
    Input('store-filtered-data', 'data')
)
def update_estatisticas_content(filtered_data):
    if not filtered_data:
        return html.Div("Carregando dados...", style={'color': DARK_THEME['text']})
    
    try:
        df = pd.read_json(filtered_data, orient='split')
        df['Data'] = pd.to_datetime(df['Data'])
        
        if df.empty:
            return html.Div("Nenhum dado corresponde aos filtros selecionados.", style={'color': DARK_THEME['text']})
        
        # Estatísticas avançadas
        total_vendas = df['Total'].sum()
        cartao_pct = (df['Cartão'].sum() / total_vendas * 100) if total_vendas > 0 else 0
        dinheiro_pct = (df['Dinheiro'].sum() / total_vendas * 100) if total_vendas > 0 else 0
        pix_pct = (df['Pix'].sum() / total_vendas * 100) if total_vendas > 0 else 0
        
        # Melhor dia da semana
        best_weekday, avg_sales_weekday = analyze_sales_by_weekday(df)
        
        # Resumo financeiro
        total_registros = len(df)
        media_por_registro = df['Total'].mean() if total_registros > 0 else 0
        maior_venda_diaria = df['Total'].max() if total_registros > 0 else 0
        menor_venda_diaria = df[df['Total'] > 0]['Total'].min() if not df[df['Total'] > 0].empty else 0
        
        stats_content = [
            # Resumo Financeiro
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader([
                            html.H4("💰 Resumo Financeiro Agregado", style={'color': 'white', 'marginBottom': '0'})
                        ], style={'backgroundColor': DARK_THEME['primary']}),
                        dbc.CardBody([
                            dbc.Row([
                                dbc.Col([
                                    html.H5("🔢 Total de Registros", style={'color': DARK_THEME['text']}),
                                    html.H3(f"{total_registros}", style={'color': DARK_THEME['success']})
                                ], width=6),
                                dbc.Col([
                                    html.H5("💵 Faturamento Total", style={'color': DARK_THEME['text']}),
                                    html.H3(format_brl(total_vendas), style={'color': DARK_THEME['success']})
                                ], width=6)
                            ]),
                            dbc.Row([
                                dbc.Col([
                                    html.H5("📈 Média por Registro", style={'color': DARK_THEME['text']}),
                                    html.H3(format_brl(media_por_registro), style={'color': DARK_THEME['primary']})
                                ], width=6),
                                dbc.Col([
                                    html.H5("⬆️ Maior Venda Diária", style={'color': DARK_THEME['text']}),
                                    html.H3(format_brl(maior_venda_diaria), style={'color': DARK_THEME['warning']})
                                ], width=6)
                            ]),
                            dbc.Row([
                                dbc.Col([
                                    html.H5("⬇️ Menor Venda Diária (>0)", style={'color': DARK_THEME['text']}),
                                    html.H3(format_brl(menor_venda_diaria), style={'color': DARK_THEME['secondary']})
                                ], width=12)
                            ])
                        ], style={'backgroundColor': DARK_THEME['card_bg']})
                    ])
                ], width=12)
            ], className="mb-4"),
            
            # Métodos de Pagamento
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader([
                            html.H4("💳 Métodos de Pagamento (Visão Geral)", style={'color': 'white', 'marginBottom': '0'})
                        ], style={'backgroundColor': DARK_THEME['primary']}),
                        dbc.CardBody([
                            dbc.Row([
                                dbc.Col([
                                    html.H5("💳 Cartão", style={'color': DARK_THEME['text']}),
                                    html.H3(format_brl(df['Cartão'].sum()), style={'color': DARK_THEME['primary']}),
                                    html.P(f"{cartao_pct:.1f}% do total", style={'color': DARK_THEME['text_secondary']})
                                ], width=4),
                                dbc.Col([
                                    html.H5("💵 Dinheiro", style={'color': DARK_THEME['text']}),
                                    html.H3(format_brl(df['Dinheiro'].sum()), style={'color': DARK_THEME['success']}),
                                    html.P(f"{dinheiro_pct:.1f}% do total", style={'color': DARK_THEME['text_secondary']})
                                ], width=4),
                                dbc.Col([
                                    html.H5("📱 PIX", style={'color': DARK_THEME['text']}),
                                    html.H3(format_brl(df['Pix'].sum()), style={'color': DARK_THEME['warning']}),
                                    html.P(f"{pix_pct:.1f}% do total", style={'color': DARK_THEME['text_secondary']})
                                ], width=4)
                            ])
                        ], style={'backgroundColor': DARK_THEME['card_bg']})
                    ])
                ], width=12)
            ], className="mb-4"),
            
            # Análise Temporal
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader([
                            html.H4("📅 Análise Temporal e Desempenho Semanal", style={'color': 'white', 'marginBottom': '0'})
                        ], style={'backgroundColor': DARK_THEME['primary']}),
                        dbc.CardBody([
                            html.H5(f"🏆 Melhor Dia da Semana: {best_weekday or 'N/A'}", 
                                   style={'color': DARK_THEME['success'], 'marginBottom': '20px'}) if best_weekday else 
                            html.P("📊 Dados insuficientes para determinar o melhor dia", style={'color': DARK_THEME['text_secondary']})
                        ], style={'backgroundColor': DARK_THEME['card_bg']})
                    ])
                ], width=12)
            ], className="mb-4")
        ]
        
        # Gráficos
        if avg_sales_weekday is not None and not avg_sales_weekday.empty:
            weekly_chart = create_weekly_pattern_chart(df)
            stats_content.append(
                dbc.Row([
                    dbc.Col([
                        dcc.Graph(figure=weekly_chart)
                    ], width=12)
                ], className="mb-4")
            )
        
        evolution_chart = create_payment_evolution_chart(df)
        histogram_chart = create_sales_histogram(df)
        
        stats_content.extend([
            dbc.Row([
                dbc.Col([
                    dcc.Graph(figure=evolution_chart)
                ], width=12, lg=6),
                dbc.Col([
                    dcc.Graph(figure=histogram_chart)
                ], width=12, lg=6)
            ])
        ])
        
        return stats_content
        
    except Exception as e:
        print(f"❌ Erro nas estatísticas: {e}")
        return html.Div(f"Erro ao processar dados: {e}", style={'color': DARK_THEME['danger']})

# Callback para análise contábil
@app.callback(
    Output('contabil-content', 'children'),
    Input('store-filtered-data', 'data')
)
def update_contabil_content(filtered_data):
    if not filtered_data:
        return html.Div("Carregando dados...", style={'color': DARK_THEME['text']})
    
    try:
        df = pd.read_json(filtered_data, orient='split')
        
        if df.empty:
            return html.Div("Nenhum dado corresponde aos filtros selecionados.", style={'color': DARK_THEME['text']})
        
        return [
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader([
                            html.H4("📊 Análise Contábil e Financeira Detalhada", className="mb-0", style={'color': 'white'})
                        ], style={'backgroundColor': DARK_THEME['primary']}),
                        dbc.CardBody([
                            html.P("Configure os parâmetros para simulação contábil:", style={'color': DARK_THEME['text_secondary']}),
                            
                            dbc.Row([
                                dbc.Col([
                                    html.Label("💼 Salário Base (R$):", style={'color': DARK_THEME['text'], 'fontWeight': 'bold'}),
                                    dbc.Input(id='salario-input', type='number', value=1550, min=0, step=0.01,
                                             style={'backgroundColor': DARK_THEME['surface'], 'color': DARK_THEME['text']})
                                ], width=4),
                                dbc.Col([
                                    html.Label("📋 Honorários Contábeis (R$):", style={'color': DARK_THEME['text'], 'fontWeight': 'bold'}),
                                    dbc.Input(id='contadora-input', type='number', value=316, min=0, step=0.01,
                                             style={'backgroundColor': DARK_THEME['surface'], 'color': DARK_THEME['text']})
                                ], width=4),
                                dbc.Col([
                                    html.Label("📦 Custo Produtos (%):", style={'color': DARK_THEME['text'], 'fontWeight': 'bold'}),
                                    dbc.Input(id='fornecedores-input', type='number', value=30, min=0, max=100, step=0.1,
                                             style={'backgroundColor': DARK_THEME['surface'], 'color': DARK_THEME['text']})
                                ], width=4)
                            ], className="mb-3"),
                            
                            html.Div(id='contabil-results')
                        ], style={'backgroundColor': DARK_THEME['card_bg']})
                    ])
                ], width=12)
            ])
        ]
        
    except Exception as e:
        print(f"❌ Erro na análise contábil: {e}")
        return html.Div(f"Erro ao processar dados: {e}", style={'color': DARK_THEME['danger']})

# Callback para cálculos contábeis
@app.callback(
    Output('contabil-results', 'children'),
    [Input('store-filtered-data', 'data'),
     Input('salario-input', 'value'),
     Input('contadora-input', 'value'),
     Input('fornecedores-input', 'value')]
)
def update_contabil_results(filtered_data, salario, contadora, fornecedores):
    if not filtered_data:
        return "Carregando dados..."
    
    try:
        df = pd.read_json(filtered_data, orient='split')
        
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
                            html.H5("💰 Demonstrativo de Resultados", style={'color': 'white', 'marginBottom': '0'})
                        ], style={'backgroundColor': DARK_THEME['primary']}),
                        dbc.CardBody([
                            html.Table([
                                html.Tr([html.Td("(+) Faturamento Bruto", style={'color': DARK_THEME['text']}), 
                                       html.Td(format_brl(results['faturamento_bruto']), style={'color': DARK_THEME['success'], 'textAlign': 'right'})]),
                                html.Tr([html.Td("(-) Impostos Simples Nacional", style={'color': DARK_THEME['text']}), 
                                       html.Td(format_brl(-results['imposto_simples']), style={'color': DARK_THEME['danger'], 'textAlign': 'right'})]),
                                html.Tr([html.Td("(-) Custo dos Produtos", style={'color': DARK_THEME['text']}), 
                                       html.Td(format_brl(-results['custo_fornecedores_valor']), style={'color': DARK_THEME['danger'], 'textAlign': 'right'})]),
                                html.Tr([html.Td("(-) Folha de Pagamento", style={'color': DARK_THEME['text']}), 
                                       html.Td(format_
