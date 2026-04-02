# Post-Task Validator

## Descricao

System prompt para um agente AI que valida tarefas de desenvolvimento apos execucao. Verifica conformidade com a spec, aderencia ao coding standards, boas praticas de engenharia, cobertura de testes e prontidao para producao. Despacha agentes especialistas em paralelo e apresenta findings interativamente com analise de quatro lentes (UX, task focus, project focus, engineering). Stack-agnostico.

## Variaveis

- `{{task_id}}`: Identificador da tarefa a ser validada (ex: "T-012")

## Prompt

Veja a versao completa e instalavel como plugin em [`post-task-validator/skills/post-task-validator/SKILL.md`](../../post-task-validator/skills/post-task-validator/SKILL.md).

## Exemplo

```
Executar o prompt com {{task_id}} = "T-012" para validar a tarefa apos execucao pelo task-executor, despachando agentes de revisao em paralelo e resolvendo findings interativamente.
```
