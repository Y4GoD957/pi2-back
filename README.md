# EduCenso Analytics API

Backend FastAPI pensado para substituir a logica hoje concentrada no frontend e expor contratos REST compativeis com os tipos existentes em `pi2-front`.

## Arquitetura

- `app/api/routes`: endpoints HTTP
- `app/core`: configuracao, seguranca e tratamento de erros
- `app/db`: sessao e engine SQLAlchemy assincromos
- `app/models`: mapeamento ORM das tabelas atuais
- `app/repositories`: acesso a dados
- `app/schemas`: contratos de entrada e saida
- `app/services`: regras de negocio
- `app/utils`: regras analiticas portadas do frontend

## Endpoints principais

- `GET /health`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/register`
- `GET /api/v1/auth/me`
- `GET /api/v1/users/me`
- `PUT /api/v1/users/me`
- `GET /api/v1/profiles`
- `GET /api/v1/educenso/dashboard`
- `GET /api/v1/educenso/reports`
- `GET /api/v1/educenso/reports/{report_id}`
- `GET /api/v1/educenso/report-form-options`
- `POST /api/v1/educenso/reports`
- `GET /api/v1/educenso/df/heatmap`

## Como rodar o backend

Requisitos:

- Python 3.13 ou superior
- acesso ao PostgreSQL configurado em `DATABASE_URL`
- arquivo `.env` preenchido

Passo a passo no Windows PowerShell:

1. Crie o ambiente virtual:
   `py -3.13 -m venv .venv`
2. Ative o ambiente virtual:
   `.\.venv\Scripts\Activate.ps1`
3. Instale as dependencias:
   `python -m pip install --upgrade pip`
   `pip install -e .`
4. Crie o arquivo de ambiente:
   `Copy-Item .env.example .env`
5. Ajuste as variaveis do `.env`, principalmente `DATABASE_URL`.
6. Inicie o servidor:
   `uvicorn app.main:app --reload`

Observacoes:

- O comando `.\.venv\Scripts\Activate.ps1` so funciona depois que a pasta `.venv` for criada.
- Se voce ja tiver as dependencias instaladas no Python global, tambem pode iniciar direto com `uvicorn app.main:app --reload`, sem ativar ambiente virtual.

Se tudo estiver correto, a API ficara disponivel em `http://127.0.0.1:8000`.

Teste rapido:

- `GET http://127.0.0.1:8000/health`

## Compatibilidade com o frontend

Contratos alinhados com:

- `src/types/auth.ts`
- `src/types/educenso.ts`
- `src/services/auth/authService.ts`
- `src/services/user/userService.ts`
- `src/services/educenso/analyticsService.ts`
- `src/services/educenso/reportService.ts`

## Observacao importante

A modelagem atual exposta pelo frontend indica que `fato_educacao` e `fato_socioeconomico` nao possuem chave territorial direta. Por isso, a API preserva a mesma leitura atual: o dashboard e os relatorios se apoiam nas relacoes presentes em `relatorio`.
