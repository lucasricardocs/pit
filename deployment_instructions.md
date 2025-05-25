# Instruções para Deploy Permanente do Aplicativo Dash

Este documento complementa as instruções de execução local e detalha como implantar o aplicativo Dash de forma permanente em plataformas de hospedagem comuns como Heroku ou Render.

## Arquivos Necessários

Certifique-se de que os seguintes arquivos estão no diretório raiz do seu projeto:

*   `app_dash.py`: O código principal do aplicativo Dash.
*   `requirements.txt`: Lista de dependências Python (incluindo `dash`, `gunicorn`, etc.).
*   `Procfile`: Define o comando para iniciar o servidor web (`web: gunicorn app_dash:server`).
*   `credentials.json`: Arquivo de credenciais do Google Service Account.
*   **(Opcional)** Pasta `assets/`: Contendo arquivos como `logo.png`.

## Preparação para Deploy

1.  **Modificar `app_dash.py` para Ler Credenciais do Ambiente (Recomendado)**:
    Para evitar expor seu arquivo `credentials.json` em repositórios Git, é mais seguro carregar as credenciais a partir de variáveis de ambiente na plataforma de hospedagem. Farei essa modificação no `app_dash.py`.

2.  **Inicializar Repositório Git**:
    Se ainda não o fez, inicialize um repositório Git no diretório do projeto:
    ```bash
    git init
    ```

3.  **Criar Arquivo `.gitignore`**:
    Crie um arquivo chamado `.gitignore` na raiz do projeto e adicione as seguintes linhas para evitar que arquivos desnecessários ou sensíveis (como o `credentials.json` local e ambientes virtuais) sejam enviados:
    ```
    venv/
    __pycache__/
    *.pyc
    .env
    credentials.json # Adicione esta linha se for usar variáveis de ambiente
    *.DS_Store
    ```

4.  **Adicionar e Commitar Arquivos**:
    Adicione todos os arquivos necessários ao Git e faça o commit inicial:
    ```bash
    git add .
    git commit -m "Initial commit for Dash app deployment"
    ```

## Deploy em Plataformas (Exemplos)

**Opção 1: Heroku**

1.  **Criar Conta e Instalar Heroku CLI**: Crie uma conta gratuita no [Heroku](https://www.heroku.com/) e instale o [Heroku CLI](https://devcenter.heroku.com/articles/heroku-cli).
2.  **Login no Heroku CLI**:
    ```bash
    heroku login
    ```
3.  **Criar App Heroku**:
    ```bash
    heroku create nome-do-seu-app-unico # Escolha um nome único
    ```
4.  **Configurar Variável de Ambiente para Credenciais**: 
    A maneira mais segura é armazenar o *conteúdo* do `credentials.json` em uma variável de ambiente no Heroku. Copie todo o conteúdo do seu `credentials.json`.
    No terminal, execute (substitua `conteudo_completo_do_json` pelo conteúdo copiado, geralmente entre aspas simples para evitar problemas com caracteres especiais no shell):
    ```bash
    heroku config:set GOOGLE_CREDENTIALS_JSON=\
    '{
      "type": "service_account",
      "project_id": "seu-project-id",
      "private_key_id": "sua-key-id",
      "private_key": "-----BEGIN PRIVATE KEY-----\nSUA\nCHAVE\nPRIVADA\nAQUI\n-----END PRIVATE KEY-----\n",
      "client_email": "seu-client-email@seu-project-id.iam.gserviceaccount.com",
      "client_id": "seu-client-id",
      "auth_uri": "https://accounts.google.com/o/oauth2/auth",
      "token_uri": "https://oauth2.googleapis.com/token",
      "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
      "client_x509_cert_url": "sua-cert-url"
    }'
    ```
    *Importante*: Cole o conteúdo JSON exatamente como está no arquivo, incluindo as quebras de linha representadas por `\n` dentro da chave privada.
5.  **Enviar Código para o Heroku**:
    ```bash
    git push heroku main # Ou master, dependendo do nome da sua branch principal
    ```
6.  **Abrir o App**:
    ```bash
    heroku open
    ```

**Opção 2: Render**

1.  **Criar Conta**: Crie uma conta gratuita no [Render](https://render.com/).
2.  **Conectar Repositório**: Conecte sua conta Render ao seu provedor Git (GitHub, GitLab, Bitbucket) onde você hospedou o repositório.
3.  **Criar Novo Serviço Web**: No dashboard do Render, clique em "New +" -> "Web Service".
4.  **Selecionar Repositório**: Escolha o repositório Git do seu projeto.
5.  **Configurar Serviço**:
    *   **Name**: Dê um nome ao seu serviço.
    *   **Region**: Escolha uma região.
    *   **Branch**: Selecione a branch principal (ex: `main`).
    *   **Build Command**: `pip install -r requirements.txt` (geralmente detectado automaticamente).
    *   **Start Command**: `gunicorn app_dash:server` (geralmente detectado automaticamente a partir do `Procfile`).
    *   **Plan**: Escolha o plano gratuito (Free).
6.  **Configurar Variáveis de Ambiente**: Vá para a seção "Environment" -> "Secret Files".
    *   Clique em "Add Secret File".
    *   **Filename**: Digite `credentials.json`.
    *   **Contents**: Cole todo o conteúdo do seu arquivo `credentials.json`.
7.  **Criar Serviço Web**: Clique em "Create Web Service". O Render fará o build e deploy automaticamente.
8.  **Acessar o App**: Após o deploy, o Render fornecerá uma URL pública para acessar seu aplicativo.

## Modificação Sugerida em `app_dash.py` para Credenciais

Vou ajustar a função `get_google_auth` em `app_dash.py` para tentar ler as credenciais primeiro da variável de ambiente `GOOGLE_CREDENTIALS_JSON` e, se não encontrar, tentar ler do arquivo `credentials.json`. Isso torna o código mais flexível para diferentes ambientes de deploy.

Se tiver dúvidas durante o processo, me informe!
