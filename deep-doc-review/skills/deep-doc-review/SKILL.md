---
name: deep-doc-review
description: >
  Revisao profunda de documentacao de projeto. Encontra erros, inconsistencias,
  gaps, dados faltantes e melhorias. Apresenta findings em tabela compacta e
  resolve um por vez com aprovacao do usuario. Nao faz alteracoes automaticas.
trigger: >
  - Quando o usuario pede revisao de documentacao do projeto
  - Antes de iniciar implementacao baseada em docs (validar qualidade dos docs)
  - Apos mudancas significativas em docs de referencia (PRD, TRD, API design, etc.)
skip_when: >
  - Revisao de codigo (usar code-reviewer ou post-task-validator)
  - Docs ainda nao existem (criar primeiro)
  - Revisao de um unico arquivo simples (fazer diretamente sem skill)
prerequisite: >
  - Projeto tem documentacao para revisar
  - Docs estao acessiveis no repositorio
NOT_skip_when: >
  - "Docs ja foram revisados" → Docs evoluem e acumulam inconsistencias.
  - "Sao poucos docs" → Poucos docs ainda podem ter contradicoes entre si.
  - "So mudou um doc" → Mudanca em um doc pode criar inconsistencia com outros.
examples:
  - name: Revisar todos os docs do projeto
    invocation: "Revise os docs do projeto"
    expected_flow: >
      1. Descobrir docs existentes
      2. Ler todos os docs
      3. Cruzar informacoes entre docs
      4. Gerar tabela de findings
      5. Apresentar um por vez, aplicar correcoes aprovadas
      6. Resumo final
  - name: Revisar docs especificos
    invocation: "Revise docs/pre-dev/api-design.md e docs/pre-dev/data-model.md"
    expected_flow: >
      1. Ler os docs especificados
      2. Cruzar informacoes entre eles
      3. Gerar tabela e resolver findings
related:
  complementary:
    - pre-task-validator
    - post-task-validator
  differentiation:
    - name: pre-task-validator
      difference: >
        pre-task-validator valida uma task spec contra docs de referencia.
        deep-doc-review revisa os proprios docs entre si, independente de tasks.
verification:
  manual:
    - Todos os findings apresentados ao usuario
    - Correcoes aprovadas aplicadas corretamente
    - Resumo final apresentado
---

# Deep Doc Review

Revisao profunda de documentacao de projeto. Encontra erros, inconsistencias, gaps, dados faltantes e melhorias.

---

## Phase 0: Descobrir e Carregar Docs

### Step 0.1: Identificar Docs para Revisar

Se o usuario especificou arquivos, usar esses. Caso contrario, descobrir automaticamente:

1. Procurar por docs de referencia do projeto: `docs/`, `docs/pre-dev/`, ou equivalente
2. Incluir: PRD, TRD, API design, data model, task specs, coding standards, dependency map, README, CHANGELOG
3. Excluir: arquivos gerados, node_modules, build artifacts, arquivos binarios

Apresentar a lista de docs encontrados ao usuario antes de prosseguir. Se forem muitos (>15), perguntar se quer revisar todos ou selecionar um subconjunto.

### Step 0.2: Ler Todos os Docs

Ler o conteudo completo de cada doc identificado. Construir um mapa mental de:
- Entidades e campos definidos em cada doc
- Endpoints e contratos de API
- Regras de negocio
- Decisoes tecnicas
- Dependencias entre docs

---

## Phase 1: Analise e Cruzamento

### Tipos de Problemas

| Tipo | Descricao |
|------|-----------|
| ERRO | Informacao factualmente incorreta |
| INCONSISTENCIA | Contradicao entre dois ou mais docs |
| GAP | Informacao esperada mas ausente |
| FALTANDO | Dado referenciado que nao existe em nenhum doc |
| MELHORIA | Oportunidade de clareza, organizacao ou completude |

### Severidade

| Severidade | Criterio |
|------------|----------|
| CRITICA | Bloqueia implementacao — dev nao consegue prosseguir sem resolver |
| ALTA | Causa bug ou confusao significativa durante implementacao |
| MEDIA | Afeta qualidade dos docs mas nao bloqueia implementacao |
| BAIXA | Cosmetico — formatacao, typos, organizacao |

### O que Analisar

Para cada doc, verificar:
1. **Consistencia interna** — o doc contradiz a si mesmo?
2. **Consistencia cruzada** — o doc contradiz outros docs?
3. **Completude** — faltam secoes esperadas?
4. **Referencia valida** — entidades, campos, endpoints referenciados existem nos docs correspondentes?
5. **Clareza** — um dev consegue implementar sem precisar perguntar?
6. **Atualizacao** — informacoes estao desatualizadas vs o codigo existente?

---

## Phase 2: Apresentar Overview

Apresentar a tabela completa de findings para dar visao geral:

```markdown
## Deep Doc Review — X findings em Y docs

| # | Tipo | Severidade | Arquivo(s) | Problema | Correcao sugerida | Tradeoff | Recomendacao |
|---|------|------------|------------|----------|-------------------|----------|--------------|
| 1 | INCONSISTENCIA | CRITICA | api-design.md, data-model.md | Campo X definido como VARCHAR(50) no data-model mas string sem limite no API design | Alinhar para VARCHAR(100) em ambos | Mudar limite pode afetar validacao | Corrigir ambos os docs |
| 2 | GAP | ALTA | tasks.md | Task T-008 nao define Testing Strategy | Adicionar secao com unit + integration tests | Esfoco adicional de escrita | Adicionar antes de implementar |
| ... | ... | ... | ... | ... | ... | ... | ... |

### Resumo por Severidade
- CRITICA: X
- ALTA: X
- MEDIA: X
- BAIXA: X
```

---

## Phase 3: Resolucao Interativa (um por vez)

Apresentar cada finding individualmente, em ordem de severidade (CRITICA primeiro).

Para CADA finding:

### 1. Mostrar o Item

Exibir o numero, tipo, severidade, arquivo(s) afetado(s), descricao do problema, correcao sugerida e tradeoff.

### 2. Perguntar ao Usuario

Usar `AskUser` com opcoes contextuais:
- Corrigir conforme sugerido
- Corrigir com ajuste (usuario especifica)
- Pular este item

**BLOCKING**: NAO avancar para o proximo item ate o usuario decidir.

### 3. Aplicar (se aprovado)

Se o usuario escolheu corrigir:
1. Aplicar a correcao imediatamente
2. Confirmar que foi aplicada
3. Somente entao avancar para o proximo item

### Regras
- Nunca apresentar mais de um item por vez
- Nunca aplicar correcoes sem aprovacao explicita
- Registrar internamente cada decisao (corrigido, pulado, ajustado)

---

## Phase 4: Resumo Final

Apos processar todos os findings:

```markdown
## Deep Doc Review — Resumo

### Corrigidos (X findings)
| # | Tipo | Arquivo(s) | Correcao Aplicada |
|---|------|------------|-------------------|
| 1 | INCONSISTENCIA | api-design.md, data-model.md | Alinhado VARCHAR(100) |

### Pulados (X findings)
| # | Tipo | Arquivo(s) | Motivo |
|---|------|------------|--------|
| 5 | MELHORIA | trd.md | Usuario: cosmetico, nao prioritario |

### Estatisticas
- Total de findings: X
- Corrigidos: X
- Pulados: X
- Docs modificados: [lista]
```

**Do NOT commit automaticamente.** Apresentar o resumo e aguardar o usuario decidir se quer commitar.

---

## Rules

- NAO gerar codigo — esta skill e somente para documentacao
- NAO assumir — se algo e ambiguo, classificar como GAP ou FALTANDO
- SEMPRE cruzar informacoes entre docs — findings intra-doc sao uteis, mas inter-doc sao mais valiosos
- Priorizar: CRITICA > ALTA > MEDIA > BAIXA
- Referenciar localizacao exata (arquivo, secao, linha quando possivel)
- Tradeoffs devem ser honestos — nao minimizar o custo de uma correcao
- Se o doc referencia codigo existente, verificar se o codigo condiz com o doc
