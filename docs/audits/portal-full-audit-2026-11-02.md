# Auditoria integral dos portais — 2026-11-02

## Veredito

Os portais estão executáveis e a base de integração está saudável, mas as specs ainda não estão todas fechadas. O Product Forge já tem um portal próprio PM/PA, composição automática com o Agent Bridge, sessão de chat e descoberta real de hosts. Ainda faltam fechar a experiência completa de boards/roadmaps, persistência PostgreSQL, notificações, o módulo Angular dedicado e a homologação real de todos os providers.

## Evidência executada

### Product Forge

- `TMPDIR=/tmp uv run pytest -q` → **121 passed**.
- `uv run ruff check src tests` → **All checks passed**.
- `productforge portal --no-open --port 8780 --bridge-port 18471` → portal e Bridge subiram juntos.
- API live com o token da URL:
  - `GET /api/v1/bootstrap` → 200;
  - `GET /api/v1/health` → 200, healthy;
  - `GET /api/v1/capabilities` → 200;
  - `GET /api/v1/workspaces` e `GET /api/v1/products` → 200;
  - `GET /api/v1/agent/health` → 200;
  - `GET /api/v1/agent/providers` → 200, Codex/Claude/Devin detectados e Test provider disponível;
  - criação real de workspace e produto → 200;
  - criação de sessão e prompt → 200;
  - provider fake → eventos `message.delta` e `message.completed` visíveis na UI.
- Navegador: status `Pronto · Forge Portal`, screenshot desktop validado, skip-link, landmarks, labels e live regions presentes.
- O catálogo visual agora traduz `claude-code` para Claude e informa quando a resposta está aguardando o host.

### Forge Agent Bridge

- `TMPDIR=/tmp uv run pytest tests/test_bridge.py tests/test_install.py -q` → **17 passed**.
- `uv run ruff check src tests` → **All checks passed**.

### Forge Portal Angular

- `npm run build -- --configuration production` → **build concluído**.
- `npm test -- --watch=false` → **53 arquivos, 579 testes passados**.
- Smoke navegável no bundle produzido: **21 rotas**, todas renderizaram `main`, heading esperado e nenhuma mensagem de erro de aplicação ou log de browser.
- A rota `/pf` renderiza o Product Forge Studio e as rotas de chat/detail existem no bundle.
- `npm test -- --watch=false --browsers=ChromeHeadless` não é suportado pela configuração atual: o Vitest pede um provider de browser Playwright/WebdriverIO/Preview não instalado. O comando válido do projeto é `npm test -- --watch=false`.

## Correções encontradas durante o pente-fino

1. Product Forge não registrava `default_operations`, então `/api/v1/bootstrap` e `/api/v1/health` não existiam de fato.
2. O adaptador consultava sempre a porta 8471, ignorando `--bridge-port`; agora o runtime propaga `FORGE_BRIDGE_URL` para o processo pai e para o filho.
3. O registry de operações podia compartilhar estado entre instâncias; agora é criado por instância.
4. O frontend não reconhecia o id real `claude-code` e não informava uma resposta assíncrona aceita sem conteúdo imediato.

## Specs ainda abertas

Status observado no Loop Factory:

| Spec | Estado | Implicação |
|---|---|---|
| live-provider-homologation | grill concluído | Ainda exige execução real autenticada de cada provider |
| notification-delivery | inbox | Sem entrega de notificações completa |
| portal-angular-module | inbox | Integração dedicada Product Forge no Angular ainda não fechada |
| postgres-backend | inbox | SQLite continua sendo o backend efetivo |
| real-authz-multi-tenant | grill concluído | Não equivale a multi-tenant de produção validado |
| real-provider-system-harness | inbox | Falta harness real para Codex, Claude, Devin e Copilot |
| unified-local-runtime | grill concluído | Composição local validada |
| unified-workspace-surface | inbox | Boards, roadmaps e navegação de workspace ainda são parciais |
| deep-regression-suite | active / grill concluído | A spec ainda não foi arquivada como encerrada |

## Achados de produto e UX

- **Major:** o portal Product Forge atual é uma superfície de overview + chat; “Produtos”, “Boards & roadmaps” e “Conhecimento” ainda são âncoras na mesma página, não módulos completos com CRUD, detalhe, board e roadmap.
- **Major:** Codex, Claude e Devin são detectados, mas sua autenticação real e retorno de resposta dependem do primeiro uso; Copilot não foi detectado nesta máquina. Portanto, não há evidência para liberar “todos os providers”.
- **Major:** o teste completo encontrou uma fragilidade operacional: um Bridge órfão em 18471 pode interferir em testes MCP paralelos. O runtime precisa de teardown robusto e/ou escolha automática de porta para evitar colisões.
- **Minor:** o fluxo de chat deveria persistir/reatar a sessão na inicialização; hoje a UI começa com `sessionId` nulo e cria uma nova sessão por carregamento.
- **Enhancement:** instalar um provider de browser para Vitest permitiria rodar a variante explícita `--browsers=ChromeHeadless`; não é necessário para a suíte atual, mas fecha melhor a cobertura visual.

## Conclusão de release

**Não recomendo declarar todas as specs fechadas ainda.** Recomendo considerar a composição local e o portal navegável como fechados para uma próxima iteração, mantendo o release geral bloqueado até: (1) boards/roadmaps reais, (2) harness autenticado para os quatro hosts, (3) teardown/port allocation sem processos órfãos, e (4) decisão/implementação do backend PostgreSQL.

## Follow-up de desbloqueio — 2026-11-02

Implementado após a auditoria:

- Product Forge standalone agora expõe `GET/POST /products/{pid}/initiatives`, `GET /products/{pid}/boards`, priorização e board persistido; a UI mostra as quatro colunas e permite criar iniciativa.
- Forge Portal Angular ganhou `/pf/boards`, ligado ao `PfApi` real para carregar roadmap e criar iniciativas.
- Agent Bridge catalogua `github-copilot` e possui adapter real sobre `copilot -p`; a autenticação continua pertencendo ao CLI e falha honestamente se faltar login.
- Notification registry suporta webhook HTTPS e SMTP com referência de segredo por variável de ambiente, disabled-by-default, aprovação explícita, retries e receipts de falha/sucesso.
- PostgreSQL recebeu `PostgresConnector`, extra `productforge[postgres]` e `docker-compose.postgres.yml`; o smoke test Docker executou `SELECT 1` com sucesso.
- Runtime reconcilia Bridge stale pelo manifest antes de iniciar e o teardown final não deixou a porta do Bridge ocupada após interrupção.

Nova evidência: Product Forge live criou workspace, produto e iniciativa, retornou board com 1 item e roadmap com a iniciativa na lane `later`; provider matrix retornou `claude-code`, `codex`, `devin`, `github-copilot` e `fake`. Product Forge: **122 passed**; Angular: **579 passed + production build**; Bridge smoke: **15 passed + Ruff clean**.

Continua externo ao código: Claude reportou `Not logged in`, portanto a homologação autenticada não pode ser marcada como passada sem login do usuário; Codex exige trusted workdir no CLI direto, embora o adapter crie um workdir Git próprio. Devin foi posteriormente validado: `devin auth status` retornou `Logged in (via Devin)`, o adapter passou a refletir `authenticated` e um handshake ACP real criou a sessão `alder-frog`, recebeu eventos e concluiu o turno. Isso confirma que o ACP reutiliza a autenticação local do Devin CLI/Desktop.

## Reavaliação final — após o pente-fino visual e tratamento de warnings

- Product Forge: **122 passed**, `ruff check` limpo e nenhuma warning de pytest; foi adicionada a compatibilidade `httpx2` exigida pelo Starlette atual, mantendo `httpx` para os testes HTTP diretos.
- Forge Portal Angular: **579 passed**, build de produção concluído e smoke navegável das rotas principais sem erros de console.
- Forge Agent Bridge: **19 passed** no recorte de Bridge/instalação; adapters de Copilot, Claude e Devin permanecem honestos quanto ao estado de autenticação.
- Onboarding, navegação dos cards, board/roadmap, iniciativa e chat foram validados em navegador Chromium.
- Runtime: portas do Portal e Bridge ficaram livres após teardown; não foi observado processo órfão.

O fechamento total ainda **não** deve ser declarado: continuam dependentes de estado externo a homologação autenticada dos quatro providers, entrega real de notificações em canais configurados, uso efetivo do PostgreSQL como backend default, conclusão integral do módulo Angular dedicado e arquivamento formal das specs no Loop Factory. A implementação e os smoke tests desses caminhos existem, mas não substituem a homologação externa nem a decisão de release.

## Atualização de fechamento — 2026-11-02 (segunda rodada)

- O warning de `starlette.testclient` foi eliminado adicionando `httpx2` ao
  ambiente de desenvolvimento; `122 passed` agora termina sem warnings.
- O store PostgreSQL compatível foi implementado em `store/postgres.py`, com
  JSONB, índices, busca `tsvector`, seleção por DSN/env e o comando
  `productforge store migrate --to postgres --dry-run|--yes`. O smoke Docker
  criou, gravou, listou e leu uma entidade com sucesso.
- A home Angular agora expõe Boards & Roadmaps como superfície de primeiro
  nível; testes continuam em `579 passed` e o build de produção permanece verde.
- A matriz real de providers foi registrada em
  `forge-agent-bridge/docs/providers/HOMOLOGATION_EVIDENCE.md`: Devin,
  Copilot e Codex passaram prompts sintéticos; Claude continua bloqueado por
  ausência de plano/API key e sessão AWS expirada.

Por isso, o release final continua bloqueado somente por homologação externa
de Claude, entrega contra um canal externo real, decisão de ativação do DSN
PostgreSQL no ambiente de produção e arquivamento formal das specs que ainda
possuem critérios não exercitados. Nenhum desses estados é convertido em
sucesso artificial.

## Atualização operacional — webhook e PostgreSQL

- Webhook externo homologado em `webhook.site` com payload sintético:
  registro de canal real, aprovação explícita, entrega `2xx`, confirmação de
  uma requisição capturada e remoção do token descartável após o teste.
- PostgreSQL homologado como backend efetivo do API: Docker/PostgreSQL 16,
  `PRODUCT_FORGE_DB_BACKEND=postgres` e
  `PRODUCT_FORGE_DATABASE_URL=postgresql://...` permitiram healthcheck, criação
  de workspace, criação de produto e leitura posterior pelo Portal API.
- O DSN não é gravado em código, logs ou documentos; produção deve fornecê-lo
  por secret/env. Sem DSN, o modo local continua usando SQLite por segurança.

Assim, o bloqueio de notificações webhook foi fechado e o SMTP foi homologado
contra um sandbox externo Ethereal com STARTTLS e alerta sintético. Isso prova o
caminho SMTP sem transformar uma caixa descartável em relay de produção; a
implantação ainda deve fornecer credenciais SMTP próprias por ambiente.

O harness real dos quatro providers foi formalizado no Forge Agent Bridge e tem
execução manual e nightly, com artefato redigido. Devin, Codex e Copilot têm
smokes autenticados; Claude continua honestamente bloqueado por credencial
externa: a conta não tem plano/API key e a sessão AWS estava expirada.

As specs concluídas foram arquivadas formalmente em
`factory/specs/archive/2026-11-02/`; live-provider-homologation permanece em
inbox até o login Claude ser concluído. O PostgreSQL permanece disponível como
backend gerenciado no perfil recomendado/full e SQLite continua sendo o modo
local sem DSN.
