# Optimus

Marketplace de skills para Droid (Factory) e Claude Code.

## Skills

| Skill | Descricao | Comando |
|-------|-----------|---------|
| `pre-task-validator` | Validacao de specs antes da implementacao | `/optimus-pre-task-validator` |
| `task-executor` | Execucao end-to-end de tarefas com gates de verificacao | `/optimus-task-executor` |
| `post-task-validator` | Validacao pos-execucao com agentes especialistas em paralelo | `/optimus-post-task-validator` |
| `deep-doc-review` | Revisao profunda de docs com cruzamento e resolucao interativa | `/optimus-deep-doc-review` |
| `verify` | Verificacao em duas fases para Go (analise estatica + testes) | `/optimus-verify-code` |

## Instalar

```bash
droid plugin marketplace add https://github.com/alexgarzao/optimus
droid plugin install <plugin-name>@optimus
```

## Catalogo

Fichas de referencia das skills organizadas por categoria:

- `catalog/system/` - Skills de orquestracao e execucao de tarefas
- `catalog/analysis/` - Skills de analise e revisao

## Como funciona

Cada skill e um plugin instalavel com:
- `<plugin>/.factory-plugin/plugin.json` — manifesto do plugin
- `<plugin>/skills/optimus-<skill>/SKILL.md` — instrucoes completas com frontmatter (trigger, prerequisite, etc.)
