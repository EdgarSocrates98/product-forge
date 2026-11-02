# UI/UX, frontend e Graph Studio — auditoria de acabamento

## Escopo

Revisão dos portais Product Forge standalone e Forge Portal Angular, incluindo
chat, hosts, boards/roadmaps, estados de dados, responsividade, acessibilidade,
rotas e Graph Studio.

## Melhorias aplicadas

- Product Forge standalone ganhou feedback de busy/error no setup do Claude,
  escolha explícita de assinatura ou Bedrock, board real com quatro lanes,
  iniciativa persistida e feedback de estado do roadmap.
- O shell standalone passou a respeitar `prefers-reduced-motion`, define a
  fonte mono usada pelos controles e mantém focus-visible consistente.
- O Angular Product Forge ganhou a rota dedicada `/pf/boards`, com produto,
  criação de iniciativa e roadmap conectado ao `PfApi` real.
- Graph Studio recebeu ajuste responsivo para canvas e toolbar em telas estreitas,
  mantendo a lista acessível como alternativa ao canvas.
- Runtime do portal passou a usar `PR_SET_PDEATHSIG` no Linux. O Bridge termina
  junto com o launcher mesmo quando o terminal interrompe o processo, e o
  manifest stale continua sendo reconciliado no próximo start.

## Validação funcional

- Product Forge: `122 passed`, Ruff limpo.
- Agent Bridge: 18 testes focados de provider/ACP, Ruff limpo.
- Forge Portal: 579 testes, build de produção concluído.
- Smoke de navegador: `/dashboard`, `/graph`, `/pf`, `/pf/boards`, `/pf/chat`,
  `/pf/products`, `/pf/onboarding`, `/knowledge` e `/settings` renderizaram
  `main`, heading esperado e nenhum erro de console.
- Portal standalone real: status `Pronto`, hosts carregados, board com iniciativa
  criada pela API e roadmap exibido visualmente.
- Lifecycle: após Ctrl-C do launcher, as portas do portal e do Bridge ficaram
  livres; não houve processo órfão.

## Auditoria WCAG/UX

- Skip link, landmarks, headings e labels de formulário presentes no standalone.
- Chat e hosts usam live regions para mudanças assíncronas.
- Canvas tem modo de lista acessível, controles com `aria-pressed`, toolbar e
  estados de layout; o canvas não é a única representação da informação.
- Estados de loading, empty, unavailable, failed e retry existem no Angular.

## Limites conhecidos

- A homologação visual usa Chromium real e smoke de rotas; um teste com leitor de
  tela físico ainda deve ser feito antes de declarar conformidade WCAG completa.
- O Graph Studio é robusto, mas continua dependente da qualidade dos descriptors
  federados; relações não observadas precisam continuar marcadas como unverified.
- O portal standalone ainda é uma página composta, enquanto o Angular concentra
  a experiência multipágina; a direção futura deve convergir os tokens e não criar
  duas linguagens visuais independentes.
