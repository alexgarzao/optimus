# Task Executor

## Descricao

System prompt para um agente AI que executa tarefas de desenvolvimento end-to-end. Orquestra fases sequenciais (backend, frontend, testes), despacha agentes paralelos, executa gates de verificacao entre fases, conduz code review interativo com o usuario, e so faz commit apos aprovacao explicita. Stack-agnostico: descobre automaticamente os comandos do projeto (lint, test, etc.) antes de executar.

## Variaveis

- `{{task_id}}`: Identificador da tarefa a ser executada (ex: "T-012")

## Prompt

Veja a versao completa e instalavel como plugin em [`task-executor/skills/task-executor/SKILL.md`](../../task-executor/skills/task-executor/SKILL.md).

## Exemplo

```
Executar o prompt com {{task_id}} = "T-012" para implementar a tarefa, passando por todas as fases de execucao, verificacao, code review e commit.
```
