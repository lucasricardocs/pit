# Instruções para Executar o Aplicativo Dash

Este documento fornece as instruções para configurar e executar o aplicativo Dash de gestão financeira.

## Pré-requisitos

1.  **Python 3.10+**: Certifique-se de ter o Python instalado em sua máquina.
2.  **Arquivo de Credenciais do Google**: Você precisará do arquivo `credentials.json` que contém as credenciais da conta de serviço do Google Cloud com acesso à API do Google Sheets e Google Drive. Coloque este arquivo no mesmo diretório do `app_dash.py`.
3.  **(Opcional) Logo**: Se desejar exibir um logo, crie uma pasta chamada `assets` no mesmo diretório do `app_dash.py` e coloque o arquivo `logo.png` dentro dela.

## Configuração do Ambiente

1.  **Crie um Ambiente Virtual (Recomendado)**:
    ```bash
    python -m venv venv
    source venv/bin/activate  # No Windows use `venv\Scripts\activate`
    ```

2.  **Instale as Dependências**:
    Navegue até o diretório onde você salvou os arquivos (`app_dash.py`, `requirements.txt`, `credentials.json`) e execute:
    ```bash
    pip install -r requirements.txt
    ```

## Executando o Aplicativo

1.  **Inicie o Servidor Dash**:
    No mesmo diretório, execute o script Python:
    ```bash
    python app_dash.py
    ```

2.  **Acesse o Aplicativo**:
    Abra seu navegador e acesse o endereço fornecido no terminal (geralmente `http://127.0.0.1:8050/` ou `http://0.0.0.0:8050/`).

## Funcionalidades Atuais

*   Leitura de dados da planilha Google Sheets configurada.
*   Registro de novas vendas diretamente na planilha através do formulário.
*   Layout básico da aplicação.

## Próximos Passos (Implementações Futuras)

Conforme detalhado no arquivo `todo.md` (também anexado), as seguintes funcionalidades do aplicativo original ainda precisam ser implementadas na versão Dash:

*   Filtros interativos (por período, dias corridos).
*   Conversão e exibição dos gráficos (evolução de pagamento, histograma de vendas, capital acumulado) usando Plotly.
*   Análise de vendas por dia da semana.
*   Cálculos financeiros e exibição de métricas.
*   Exibição da tabela de dados completa.
*   Melhorias de estilo e usabilidade.

Se precisar de ajuda com essas implementações futuras ou tiver alguma dúvida, me diga!
