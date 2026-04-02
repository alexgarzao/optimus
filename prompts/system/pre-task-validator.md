# Pre-Task Validator

## Descricao

System prompt para um agente AI que valida especificacoes de tarefas ANTES da implementacao comecar. Cruza a spec com docs de referencia (API, data model, TRD, PRD), detecta contradicoes, gaps de cobertura de testes, problemas de observabilidade, e ambiguidades. Apresenta findings interativamente com opcoes de resolucao. Somente analise — nao gera codigo. Stack-agnostico.

## Variaveis

- `{{task_id}}`: Identificador da tarefa a ser validada (ex: "T-006")

## Prompt

Veja a versao completa e instalavel como plugin em [`pre-task-validator/skills/pre-task-validator/SKILL.md`](../../pre-task-validator/skills/pre-task-validator/SKILL.md).

## Exemplo

```
Executar o prompt com {{task_id}} = "T-006" para validar a especificacao da tarefa antes de iniciar a implementacao, cruzando com api-design, data-model, trd e prd.
```
