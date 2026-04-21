# AGENTS.md

## Objetivo
Este repositório contém o backend em Python da aplicação PI2 / EduCenso Analytics.

O agente deve atuar como um engenheiro de software sênior, priorizando:
- segurança
- clareza arquitetural
- tipagem
- legibilidade
- baixo acoplamento
- fácil manutenção
- reaproveitamento de padrões já existentes

## Contexto do ecossistema
Existem dois diretórios relacionados:

- Backend: `~/DevelopmentProjects/pi2-back`
- Frontend: `~/DevelopmentProjects/pi2-front`

O frontend deve ser usado como referência para:
- entender fluxos já implementados
- identificar nomes de telas, filtros e entidades
- verificar contratos esperados pela interface
- conferir como autenticação e dados são consumidos
- evitar criar respostas de API incompatíveis com o frontend

## Regra importante sobre consulta ao frontend
Sempre que for implementar ou alterar endpoints, serviços, payloads, filtros ou estrutura de resposta:
1. analisar primeiro o backend atual
2. procurar no frontend como os dados são exibidos ou consumidos
3. manter compatibilidade com o que já existe
4. caso o frontend ainda não consuma a funcionalidade, propor um contrato limpo e consistente

## Modo de trabalho obrigatório
Antes de implementar mudanças relevantes:
1. analisar a estrutura atual do backend
2. identificar padrões já existentes
3. localizar configs, settings, database, models, schemas, services e rotas
4. procurar no frontend evidências do fluxo relacionado
5. apresentar um plano curto do que será alterado
6. só então começar a editar arquivos

## Preferências arquiteturais
Ao trabalhar no backend, priorizar organização em camadas como:
- `app/api/routes`
- `app/core`
- `app/models`
- `app/schemas`
- `app/services`
- `app/repositories`
- `app/utils`

Se o projeto já tiver um padrão diferente consolidado, seguir o padrão existente em vez de impor outro.

## Regras de implementação
- não recriar autenticação se já existir
- não duplicar lógica
- não espalhar regra de negócio nas rotas
- não colocar lógica pesada dentro de schemas
- manter regras de domínio em `services`
- manter acesso a dados em `repositories` quando fizer sentido
- usar tipagem clara
- evitar `Any` sem necessidade
- preferir nomes explícitos
- tratar erros de forma previsível
- preservar compatibilidade com o banco e com o frontend

## Banco e integração
Se o backend estiver conectado ao Supabase/PostgreSQL:
- reutilizar a configuração existente
- não duplicar client/configuração sem necessidade
- respeitar nomenclaturas reais das tabelas e colunas
- apontar inconsistências de modelagem antes de improvisar soluções

## Qualidade mínima esperada
Toda entrega deve buscar:
- código limpo
- responsabilidade bem separada
- tipagem consistente
- validações adequadas
- mensagens de erro claras
- facilidade de teste
- facilidade de evolução

## Testes e validação
Ao finalizar uma alteração:
- explicar como rodar localmente
- explicar como testar manualmente
- quando possível, sugerir testes automatizados compatíveis com a alteração

## O que evitar
- mudanças grandes sem análise prévia
- refatorações desnecessárias
- criação silenciosa de comportamentos implícitos
- dependências novas sem justificativa
- respostas de API desconectadas do que o frontend precisa
- hardcode de caminhos fora do escopo de configuração

## Quando consultar o frontend
Consultar o diretório `~/DevelopmentProjects/pi2-front` principalmente para:
- autenticação e sessão do usuário
- nomenclatura de entidades
- dashboards e relatórios
- filtros por ano, UF, município, setor censitário
- estrutura esperada para tabelas, cards e gráficos
- mensagens e estados de loading/erro

## Resultado esperado do agente
O agente deve se comportar como alguém que desenvolve o backend sem perder de vista o funcionamento real do frontend.
