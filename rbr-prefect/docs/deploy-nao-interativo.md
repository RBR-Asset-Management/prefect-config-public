# Deploy não-interativo (agentes de IA e automação)

O `rbr-prefect` acompanha o deploy passo a passo e pergunta antes de aceitar uma
configuração incomum ou um estado de repositório arriscado. Esse acompanhamento é
um recurso, não um obstáculo — mas um prompt só pode ser respondido por quem está
em um terminal, o que impedia o uso do pacote por agentes de IA e por qualquer
automação.

A partir da versão que introduziu este documento, o deploy roda de forma autônoma
sem perder nenhuma dessas proteções. O mecanismo não é uma flag que aprova tudo.

## A regra

> **Se a intenção está declarada, roda. Se não está, pergunta. Se não pode
> perguntar, falha dizendo exatamente o que declarar.**

O prompt é o *fallback* para quando a intenção não foi declarada. Declarar a
intenção é o que dispensa a pergunta.

**Nada muda para quem roda no terminal e não declara nada.** Os mesmos prompts, na
mesma ordem, com o mesmo texto.

## O que precisa ser declarado

| Confirmação | Quando é acionada | Onde se declara |
|---|---|---|
| `work_pool_override` | `work_pool_name` fora dos pools RBR conhecidos | `acknowledge=[...]` no construtor |
| `concurrency_limit` | `concurrency_limit` fornecido | `acknowledge=[...]` no construtor |
| `advanced_schedule` | `.schedule(interval=...)` ou `.schedule(rrule=...)` | `acknowledge=[...]` no construtor |
| issues de git | repositório sujo, commits sem push, submódulo despinado | `--rbr-accept-git-issues=<ids>` na invocação |
| revisão final | sempre | `--rbr-non-interactive` na invocação |

São dois lugares diferentes porque são duas naturezas diferentes de decisão.

**Intenção de configuração mora no código.** Se o flow precisa de
`concurrency_limit=1`, precisa em toda execução do script. A declaração é
permanente, fica ao lado do parâmetro que justifica, aparece no diff e é revisável
em code review.

**Estado do repositório mora na invocação.** Não é uma decisão sobre o deploy: é
um fato sobre o repositório naquele instante, e muda a cada execução. Se virasse
um parâmetro commitado no script, a verificação estaria desligada
permanentemente para todos os deploys futuros daquele flow — o oposto do que ela
existe para fazer.

## Uso

### 1. Declare a intenção de configuração no código

```python
deploy = DefaultDeploy(
    flow_func=meu_flow,
    name="meu-flow-prod",
    tags=["dados-externos"],
    concurrency_limit=1,
    acknowledge=["concurrency_limit"],   # sim, eu quis isso de propósito
)
```

Um id desconhecido levanta `ValueError` em vez de ser ignorado — é o que faz o
parâmetro pegar erro de digitação. Os ids válidos estão em
`rbr_prefect.constants.RBRAcknowledgements`:

```python
from rbr_prefect.constants import RBRAcknowledgements

acknowledge=[RBRAcknowledgements.CONCURRENCY_LIMIT]
```

### 2. Declare o modo autônomo na invocação

```bash
uv run python -m deploy.deploy_meu_flow --rbr-non-interactive
```

A flag convive com o `argparse` do seu próprio script: o pacote só lê argumentos
com o prefixo `--rbr-` e ignora todo o resto, sem validar nem consumir.

### 3. Aceite as issues de git nomeando cada uma

Se o repositório não estiver limpo, o deploy falha e o relatório traz os ids
exatos. Aceite-os por nome:

```bash
uv run python -m deploy.deploy_meu_flow \
  --rbr-non-interactive \
  --rbr-accept-git-issues=dirty_main,unpushed_main
```

Aceitar `dirty_main` **não** autoriza um `unpushed_main` que apareça na mesma
execução. A cobertura é por id, e é isso que distingue este ack de um bypass:
quem aceita precisa ter visto e nomeado cada classe de problema.

Ids possíveis (`rbr_prefect.constants.RBRGitChecks`): `dirty_main`,
`dirty_submodules`, `unpushed_main`, `unpushed_submodules`, `submodule_pins`,
`subprocess_error`.

> **Na maioria dos casos, aceitar uma issue de git é a resposta errada.** O modo
> de falha que essa verificação previne é silencioso e sério: o Prefect busca o
> código de um commit que não contém suas mudanças, o flow roda código velho em
> produção e nada no output indica isso. Antes de aceitar, considere se o certo
> não é commitar e fazer o push.

## O fluxo de um agente, em duas execuções

Primeira execução — o agente descobre o que falta:

```
$ uv run python -m deploy.deploy_meu_flow

┌─ Git Pre-Flight Check ──────────────────────────────────────┐
│   id            Verificação                    Detalhe      │
│   dirty_main    Alterações não commitadas      M flows/…     │
└─────────────────────────────────────────────────────────────┘

Este deploy exige confirmações que não foram declaradas, e não há terminal
interativo para pedi-las. Declare cada item abaixo e execute novamente.
┌─ Confirmações pendentes ────────────────────────────────────┐
│   Pendência                    Como declarar                │
│   modo não-interativo          --rbr-non-interactive        │
│   concurrency_limit            acknowledge=["concurrency_…  │
│   issues de git não aceitas    --rbr-accept-git-issues=dir… │
└─────────────────────────────────────────────────────────────┘

exit 2
```

Segunda execução — tudo declarado, nada perguntado:

```
$ uv run python -m deploy.deploy_meu_flow \
    --rbr-non-interactive --rbr-accept-git-issues=dirty_main

exit 0
```

Todos os painéis (auditoria, requirements, env) continuam sendo impressos em modo
não-interativo. O output é o relatório que o agente consome.

## Códigos de saída

| Código | Significado |
|---|---|
| `0` | deploy concluído, **ou** o usuário respondeu "não" a um prompt |
| `2` | o pacote se recusou a prosseguir: falta uma declaração |

A distinção importa para automação. `0` por negação significa que uma pessoa viu
a pergunta e decidiu — não há nada a corrigir. `2` significa que há uma ação
concreta a tomar, descrita no relatório.

## Variáveis de ambiente como fallback

Onde o `argv` não é controlável, existem equivalentes:

| Flag | Env var |
|---|---|
| `--rbr-non-interactive` | `RBR_PREFECT_NON_INTERACTIVE=1` |
| `--rbr-accept-git-issues=<ids>` | `RBR_PREFECT_ACCEPT_GIT_ISSUES=<ids>` |

Quando a flag está presente, a env var correspondente é ignorada por completo —
não há união entre as fontes.

**Prefira as flags.** Em PowerShell não existe prefixo inline de variável de
ambiente, então `$env:RBR_PREFECT_ACCEPT_GIT_ISSUES = "dirty_main"` **persiste
pelo resto da sessão do shell** e vaza silenciosamente para todos os deploys
seguintes. A flag é efêmera por construção, que é exatamente o requisito de um
ack de estado.

## `RBR_SKIP_GIT_CHECK` está depreciado

Essa variável continua funcionando, mas o ack escopado a substitui e é
estritamente superior: roda as cinco verificações e exige que o resultado seja
nomeado, em vez de não rodar nenhuma.

O comportamento de exibir o painel verde de "repositório limpo" sob bypass foi
corrigido — aquele painel afirmava algo que o pacote não havia verificado, o que
para um agente que lê o stdout era desinformação. Agora é exibida uma mensagem
explícita de verificação ignorada.

## Nota sobre detecção de terminal

O pacote não confia apenas em `sys.stdin.isatty()`. Em Windows com Git Bash e o
stdin redirecionado, `isatty()` retorna `True` e a leitura estoura `EOFError`.
Nesse caso o pacote trata o `EOFError` como impossibilidade de perguntar e emite
o relatório de pendências, em vez de derrubar o processo com traceback. Efeito
colateral aceito: a linha do prompt pode aparecer no output antes do relatório.

A impossibilidade de perguntar nunca autoriza nada por si só — o modo autônomo é
sempre declarado, nunca inferido. Se ela sozinha habilitasse o modo, qualquer
contexto sem terminal (CI, cron, saída redirecionada) passaria a pular a revisão
final em silêncio, que é o comportamento de uma flag global concedida por
acidente.
