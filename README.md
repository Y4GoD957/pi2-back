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

## Como rodar

1. Crie um ambiente virtual Python.
2. Instale dependencias com `pip install -e .`.
3. Copie `.env.example` para `.env` e preencha as variaveis.
4. Suba a API com `uvicorn app.main:app --reload`.

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
