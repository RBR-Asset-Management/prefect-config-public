# Guia: Deploy em Worker Process (`ProcessDeploy`)

Este guia explica como usar o `ProcessDeploy` — o tipo de deploy para flows que
rodam em um **worker do tipo process** da RBR.

---

## O que é um deploy process?

Diferente dos deploys Docker (`DefaultDeploy`, `SQLDeploy`, `ScrapeDeploy`), que
executam cada flow run dentro de um container, o `ProcessDeploy` faz o worker
executar o flow como um **subprocesso no próprio ambiente Python do worker** —
sem container, sem imagem.

| Aspecto | Deploys Docker | `ProcessDeploy` |
|---|---|---|
| Onde o flow roda | Container Docker efêmero | Subprocesso na máquina do worker |
| Imagem | `prefecthq/prefect` / imagens RBR | Nenhuma |
| Work pool | `default` | `windows` (`RBRWorkPools.PROCESS`) |
| Origem do código | GitHub (`from_source`) | GitHub (`from_source`) — **igual** |
| Dependências Python | Gerenciadas pelo deploy (auto-install / pip) | **Responsabilidade do worker** |
| Certificado TLS / `PREFECT_API_URL` | Injetados pelo deploy | Já presentes no worker |

O código continua sendo buscado do GitHub no momento da execução — a única
diferença real está em **onde** e **como** o flow executa.

---

## Quando usar

Use `ProcessDeploy` quando o flow precisa:

- Rodar diretamente em uma máquina **Windows do domínio RBR** (ex.: acesso a
  recursos locais, drives de rede mapeados, softwares instalados na máquina,
  automações específicas de Windows).
- Executar em um ambiente onde não se deseja (ou não é possível) usar container.

Para a grande maioria dos flows de dados (HTTP, processamento, SQL, scraping),
**continue usando os deploys Docker** — eles são mais isolados e reprodutíveis.

---

## Pré-requisito: dependências no ambiente do worker

> ⚠️ **`ProcessDeploy` NÃO gerencia dependências Python.**

Como o flow roda no ambiente Python do próprio worker (compartilhado e
duradouro), as dependências do flow **precisam já estar instaladas nesse
ambiente**. O deploy não injeta `EXTRA_PIP_PACKAGES` nem ativa o auto-install via
`uv` — isso é intencional, para não poluir o ambiente do worker entre execuções
de flows diferentes.

Na prática, o responsável pelo worker garante que o ambiente Python onde o
`prefect worker start` roda tenha todas as dependências dos flows daquele pool
(por exemplo, via `uv sync` / `uv pip install` no venv do worker).

Por isso o `ProcessDeploy` **não expõe** os parâmetros `image` nem
`dependency_mode` — passá-los gera `TypeError`. No deploy, um painel de aviso
lembra que as dependências são responsabilidade do worker.

---

## Uso básico

```python
from rbr_prefect import ProcessDeploy
from flows.meu_flow import meu_flow

deploy = ProcessDeploy(
    flow_func=meu_flow,
    name="meu-flow-process",
    tags=["windows", "automacao-local"],
)
deploy.deploy()
```

Não é preciso informar work pool, imagem, certificado nem URL da API — tudo é
resolvido automaticamente. O work pool default já é o `windows`.

---

## Parâmetros

```python
deploy = ProcessDeploy(
    flow_func=meu_flow,
    name="meu-flow-process",
    tags=["windows"],
)
deploy.parameters = deploy.override(country_name="Argentina")
deploy.schedule(cron).deploy()
```

### Com schedule

```python
from rbr_prefect import ProcessDeploy
from rbr_prefect.cron import CronBuilder
from flows.meu_flow import meu_flow

deploy = ProcessDeploy(
    flow_func=meu_flow,
    name="meu-flow-process",
    tags=["windows"],
)

# Todo dia útil às 04:00
deploy.schedule(CronBuilder().on_weekdays().at_hour(4).at_minute(0))
deploy.deploy()
```

### Parâmetros aceitos

| Parâmetro | Default | Descrição |
|---|---|---|
| `flow_func` | — (obrigatório) | Função decorada com `@flow` |
| `name` | — (obrigatório) | Nome do deploy no Prefect |
| `tags` | — (obrigatório) | Lista com ao menos uma tag |
| `github_url` | auto (via git) | Override da URL do repositório |
| `branch` | auto (via git) | Override do branch |
| `entrypoint` | auto (introspecção) | Override do entrypoint |
| `requirements_source` | auto | Apenas **informativo** no painel (ver abaixo) |
| `work_pool_name` | `RBRWorkPools.PROCESS` (`"windows"`) | Override do work pool |
| `extra_env` / `env_override` | — | Customização de variáveis de ambiente |
| `extra_job_variables` / `job_variables_override` | — | Customização de job_variables |
| `concurrency_limit` | — | Limite de concorrência (uso incomum) |

> O `ProcessDeploy` **não** tem `image` nem `dependency_mode` — diferente dos
> deploys Docker.

### Sobre `requirements_source` no process

O painel de requirements ainda é exibido (informativo), para você visualizar o
que o flow espera. Mas **nada é injetado** — as dependências precisam estar no
worker. Trate o painel apenas como referência do que instalar no ambiente do
worker.

---

## job_variables úteis no process pool

Um work pool process aceita job_variables diferentes das do Docker. As mais
comuns:

```python
deploy = ProcessDeploy(
    flow_func=meu_flow,
    name="meu-flow-process",
    tags=["windows"],
    extra_job_variables={
        "working_dir": r"C:\\caminho\\de\\trabalho",
        "stream_output": True,
    },
)
```

> Não use `volumes`, `auto_remove` ou `image_pull_policy` aqui — essas são
> específicas de Docker e não existem no work pool process.

---

## O que acontece no `.deploy()`

1. **Git pre-flight check** — mesmo dos demais deploys (alerta sobre alterações
   não commitadas / sem push).
2. **Painel de auditoria** — valores resolvidos (sem linha de `image`, pois o
   process não usa imagem).
3. **Painel de requirements** — informativo.
4. **Aviso de dependências** — lembrete de que as deps são do worker.
5. **Confirmação** — você revisa e confirma.
6. **Deploy** — registrado no Prefect, apontando para o work pool `windows`.

---

## Teste manual (e2e)

Há um script de referência em
[`tests/e2e/deploy_teste_flow_process.py`](../tests/e2e/deploy_teste_flow_process.py):

```bash
cd rbr-prefect
python tests/e2e/deploy_teste_flow_process.py
```

Requer um worker process registrado no pool `windows` com as dependências do
flow já instaladas no ambiente.

---

## Resumo

- `ProcessDeploy` roda o flow direto no worker (sem Docker), no pool `windows`.
- O código continua vindo do GitHub.
- **Dependências são responsabilidade do ambiente do worker** — instale-as lá.
- Sem `image`, sem `dependency_mode`.
- Para deploys que gerenciam dependências automaticamente, use os deploys
  Docker com `dependency_mode` — veja o
  [guia de migração para auto-install](./migracao-auto-install.md).
