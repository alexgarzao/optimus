# Verify

## Descricao

Verificacao de codigo em duas fases para projetos Go. Fase 1 roda analise estatica e unit tests em paralelo. Fase 2 roda integration e E2E tests sequencialmente. Apresenta sumario executivo com veredicto MERGE_READY ou NEEDS_FIX.

## Variaveis

Nenhuma — detecta automaticamente os targets do Makefile.

## Skill

Veja a versao completa e instalavel como plugin em [`verify/skills/optimus-verify-code/SKILL.md`](../../verify/skills/optimus-verify-code/SKILL.md).

## Exemplo

```
/optimus-verify-code — roda todas as verificacoes e apresenta sumario com veredicto.
```
