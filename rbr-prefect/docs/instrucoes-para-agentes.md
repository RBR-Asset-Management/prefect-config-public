# Deploy autônomo com `rbr-prefect` — instruções para agentes

> Bloco pronto para colar no `CLAUDE.md` / `AGENTS.md` de um repositório de flow.
> Copie da linha abaixo até o fim do arquivo.

---

## Deploy de flows Prefect (rbr-prefect ≥ 1.1.0)

O `rbr-prefect` pergunta antes de aceitar uma configuração incomum ou um estado de
repositório arriscado. Você não tem terminal para responder — então **declare a
intenção** em vez de contornar a pergunta.

A regra do pacote: *intenção declarada roda; não declarada pergunta; impossível de
perguntar falha dizendo o que declarar.*

### Procedimento

1. **Execute como módulo**, a partir da raiz do repositório, com a flag de modo:

   ```bash
   uv run python -m deploy.<modulo_de_deploy> --rbr-non-interactive
   ```

   Rodar como arquivo (`python deploy/x.py`) quebra os imports absolutos: só a
   pasta `deploy/` entra no `sys.path`. Use `-m`.

2. **Exit 0** → deploy concluído. Confira os painéis de auditoria no output.

3. **Exit 2** → falta uma declaração. O painel `Confirmações pendentes` traz, em
   cada linha, **o texto literal** a acrescentar. Trate conforme o tipo:

   | Pendência | O que fazer |
   |---|---|
   | `work_pool_override`, `concurrency_limit`, `advanced_schedule` | Acrescente `acknowledge=["<id>"]` no construtor do deploy, no arquivo de deploy. É permanente e fica no diff. |
   | `issues de git não aceitas` | **Primeiro tente corrigir**: `git add`, `git commit`, `git push`. Ver aviso abaixo. |
   | `modo não-interativo` | Você esqueceu `--rbr-non-interactive`. |

4. **Execute de novo.** Uma execução resolve todas as pendências que o relatório
   listou de uma vez.

### Exemplo — ack de configuração

```python
deploy = DefaultDeploy(
    flow_func=meu_flow,
    name="meu-flow-prod",
    tags=["dados-externos"],
    concurrency_limit=1,
    acknowledge=["concurrency_limit"],   # autoriza o parâmetro acima
)
```

Ids válidos: `work_pool_override`, `concurrency_limit`, `advanced_schedule`.
Um id inválido levanta `ValueError` — não é ignorado.

### Issues de git — leia antes de aceitar

**Repositório sujo ou sem push quase sempre significa que você deve commitar e
fazer push, não aceitar a issue.**

O modo de falha é silencioso e sério: o Prefect busca o código do commit que está
no remote. Se suas alterações não estiverem lá, o deploy sobe apontando para
código velho, o flow roda a versão antiga em produção, e **nada no output indica
isso**. O deploy "funciona" e está errado.

Aceite uma issue só quando tiver certeza de que ela é intencional (ex.: arquivo
não versionado irrelevante ao flow). Nesse caso, nomeie cada id:

```bash
uv run python -m deploy.<modulo> \
  --rbr-non-interactive \
  --rbr-accept-git-issues=dirty_main,unpushed_main
```

Aceitar `dirty_main` **não** autoriza um `unpushed_main` que apareça na mesma
execução — a cobertura é por id. Ids possíveis: `dirty_main`, `dirty_submodules`,
`unpushed_main`, `unpushed_submodules`, `submodule_pins`, `subprocess_error`.

### Códigos de saída

| Código | Significado | Ação |
|---|---|---|
| `0` | deploy concluído, ou uma pessoa respondeu "não" a um prompt | nada a corrigir |
| `2` | falta uma declaração | leia o relatório e declare |
| outro | erro real (validação, rede, Prefect) | leia o traceback |

### Proibido

- **Nunca use `RBR_SKIP_GIT_CHECK`.** Está depreciada: não roda verificação
  nenhuma. Use o ack escopado, que roda os cinco checks e exige nomear o
  resultado.
- **Nunca defina as env vars `RBR_PREFECT_*` no PowerShell.** `$env:VAR = "..."`
  persiste pelo resto da sessão do shell e vaza para todos os deploys seguintes.
  Use as flags `--rbr-*`, que são efêmeras por invocação.
- **Nunca acrescente um `acknowledge` que você não entende** só para o deploy
  passar. Cada id autoriza uma configuração incomum específica; se você não sabe
  por que aquele parâmetro está ali, pergunte ao usuário.
- **Nunca commite `--rbr-accept-git-issues` como parâmetro do código.** Ele não
  existe como parâmetro justamente para não desligar a verificação de forma
  permanente.

### Referência completa

`docs/deploy-nao-interativo.md` no repositório `rbr-prefect`.
