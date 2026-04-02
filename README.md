# Prompts

Colecao de prompts organizados por categoria.

## Categorias

- `prompts/coding/` - Prompts para desenvolvimento e code review
- `prompts/writing/` - Prompts para escrita e documentacao
- `prompts/analysis/` - Prompts para analise de dados e pesquisa
- `prompts/system/` - System prompts para assistentes

## Plugins

- `pre-task-validator/` - Validacao de specs antes da implementacao (contradicoes, gaps, ambiguidades)
- `task-executor/` - Execucao end-to-end de tarefas com gates de verificacao
- `post-task-validator/` - Validacao pos-execucao com agentes especialistas em paralelo
- `deep-doc-review/` - Revisao profunda de docs com cruzamento e resolucao interativa

## Como usar

Cada prompt esta em um arquivo `.md` com a seguinte estrutura:

- **Descricao**: O que o prompt faz
- **Variaveis**: Parametros que devem ser substituidos (entre `{{chaves}}`)
- **Prompt**: O texto do prompt
- **Exemplo**: Exemplo de uso
