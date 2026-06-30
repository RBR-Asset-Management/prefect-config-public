# Guia de Migração: Auto-Install de Dependências (rbr-prefect 1.0.0)

A partir da versão **1.0.0**, os deploys Docker (`DefaultDeploy`, `SQLDeploy`,
`ScrapeDeploy`) passam a instalar dependências Python via **auto-install com
`uv`** por padrão. Este guia explica o que mudou e como migrar seus projetos.

> ✅ **Boa notícia:** como 100% dos nossos projetos já usam **`uv` + `pyproject.toml`**,
> a migração é praticamente nula. Não há nada a converter de `requirements.txt`
> para `uv` — assuma que essa parte já está pronta e correta no seu projeto. Na
> maioria dos casos, basta atualizar o `rbr-prefect` e conferir um detalhe do
> `pyproject.toml` (ver [checklist](#checklist-de-migração)).

---

## O que mudou

### Antes (≤ 0.3.x)

O pacote detectava as dependências do projeto e as injetava na variável de
ambiente `EXTRA_PIP_PACKAGES`, que o entrypoint da imagem Docker do Prefect
instalava com `pip` em runtime.

### Agora (≥ 1.0.0)

Existe um novo parâmetro **`dependency_mode`** nos deploys Docker, com default
`RBRDependencyMode.AUTO_INSTALL`:

| Modo | Comportamento |
|---|---|
| `auto_install` (**default**) | Injeta `PREFECT_RUNNER_AUTO_INSTALL_DEPENDENCIES=true`. O runner do Prefect usa `uv` para instalar, em runtime, as dependências declaradas em `[project].dependencies` do `pyproject.toml` do repositório clonado. **Não** injeta `EXTRA_PIP_PACKAGES`. |
| `pip_packages` | Comportamento legado: injeta `EXTRA_PIP_PACKAGES` a partir dos requirements detectados. |

Como `uv` lê diretamente o `pyproject.toml`, o auto-install combina
perfeitamente com projetos que já usam `uv` — a fonte de verdade das
dependências passa a ser o próprio `pyproject.toml`, sem duplicação.

> O `uv` já está presente nas imagens oficiais do Prefect e nas imagens
> customizadas da RBR (`SQL_IMAGE`, `SCRAPE_IMAGE`), então a pré-condição de
> ferramenta já está satisfeita.

---

## Por que essa mudança

- **Fonte única de verdade.** As dependências vivem só no `pyproject.toml` que o
  `uv` já gerencia — nada de manter um `requirements.txt` paralelo.
- **Menos divergência.** O ambiente de execução instala exatamente o que está
  declarado no projeto.
- **Falha barulhenta, não silenciosa.** O auto-install do Prefect falha
  *silenciosamente* em runtime se suas pré-condições não forem atendidas. Para
  evitar isso, o `rbr-prefect` faz um **check no momento do deploy** (ver abaixo).

---

## A rede de proteção: check no deploy

No modo `auto_install`, o `.deploy()` faz uma verificação **read-only** no
`pyproject.toml` da raiz do repositório. Ele exige:

1. que exista um `pyproject.toml` na raiz; e
2. que `prefect` esteja listado em `[project].dependencies`.

Se qualquer condição falhar, o deploy **para com um `ValueError` orientativo** —
em vez de deixar o auto-install falhar silenciosamente só na hora da execução do
flow. O check espelha exatamente a condição que o Prefect verifica em runtime,
então não há falso positivo.

---

## Checklist de migração

Para cada projeto de flow:

### 1. Atualize o `rbr-prefect` para `>= 1.0.0`

```bash
uv add "rbr-prefect>=1.0.0"
```

### 2. Garanta que `prefect` está em `[project].dependencies`

Este é o ponto que mais costuma faltar. O auto-install só funciona se `prefect`
estiver nas **dependências de runtime do projeto** (a tabela `[project]`), e não
apenas como dependência transitiva ou em um grupo de dev.

```toml
# pyproject.toml
[project]
name = "meu-projeto-de-flow"
dependencies = [
    "prefect",          # <- precisa estar aqui
    "pandas",
    "httpx",
    # ... demais dependências de runtime do flow
]
```

```bash
# Forma simples de garantir:
uv add prefect
```

> ⚠️ **Atenção (uv):** o auto-install instala apenas o que está em
> `[project].dependencies`. Dependências declaradas em
> `[dependency-groups]` (grupos de dev) ou em `[tool.uv]` **não** são
> instaladas em runtime. Se o flow precisa de um pacote em produção, ele tem que
> estar em `[project].dependencies`.

### 3. (Opcional) Remova `requirements_source` dos scripts de deploy

No modo `auto_install`, o `requirements_source` vira apenas informativo (o painel
ainda exibe, mas nada é injetado por ele). Você pode removê-lo dos scripts de
deploy para evitar confusão.

```diff
 deploy = DefaultDeploy(
     flow_func=meu_flow,
     name="meu-flow-prod",
     tags=["dados-externos"],
-    requirements_source="./requirements.txt",
 )
```

### 4. Faça o deploy normalmente

```bash
python deploy.py
```

O painel de auditoria mostrará a configuração; o check de pré-condição roda
antes da confirmação.

---

## Antes e depois (exemplo)

**Antes (0.3.x):**

```python
from rbr_prefect import DefaultDeploy
from flows.meu_flow import meu_flow

deploy = DefaultDeploy(
    flow_func=meu_flow,
    name="meu-flow-prod",
    tags=["dados-externos"],
    requirements_source="./requirements.txt",
)
deploy.deploy()
```

**Depois (1.0.0) — com `uv` + `pyproject.toml`:**

```python
from rbr_prefect import DefaultDeploy
from flows.meu_flow import meu_flow

deploy = DefaultDeploy(
    flow_func=meu_flow,
    name="meu-flow-prod",
    tags=["dados-externos"],
    # dependency_mode=auto_install é o default — nada a declarar.
    # As deps vêm do [project].dependencies do pyproject.toml.
)
deploy.deploy()
```

---

## Não quer migrar agora? Mantenha o comportamento antigo

Se por algum motivo você precisar manter a injeção via `EXTRA_PIP_PACKAGES`,
basta passar `dependency_mode=RBRDependencyMode.PIP_PACKAGES`:

```python
from rbr_prefect import DefaultDeploy
from rbr_prefect.constants import RBRDependencyMode
from flows.meu_flow import meu_flow

deploy = DefaultDeploy(
    flow_func=meu_flow,
    name="meu-flow-prod",
    tags=["dados-externos"],
    dependency_mode=RBRDependencyMode.PIP_PACKAGES,
    requirements_source="./requirements.txt",
)
deploy.deploy()
```

Isso é um escape hatch — a recomendação é migrar para `auto_install`, já que
todos os projetos usam `uv` + `pyproject.toml`.

---

## Troubleshooting

| Erro no deploy | Causa | Como resolver |
|---|---|---|
| `dependency_mode=auto_install exige um pyproject.toml ... mas nenhum foi encontrado` | Não há `pyproject.toml` na raiz do repositório | Use `uv` no projeto (todo projeto RBR já deveria ter um `pyproject.toml`). Confirme que o script de deploy roda dentro do repositório do flow. |
| `dependency_mode=auto_install exige que 'prefect' conste em [project].dependencies` | `prefect` não está nas dependências de runtime | `uv add prefect` (não basta estar em grupo de dev ou ser transitiva). |
| Flow falha em runtime com `ModuleNotFoundError`, mas o deploy passou | Dependência usada em runtime não está em `[project].dependencies` (está em grupo de dev / `[tool.uv]`) | Mova a dependência para `[project].dependencies` (`uv add <pacote>`). |

---

## E o `ProcessDeploy`?

O `ProcessDeploy` **não usa** auto-install nem `dependency_mode` — em deploys
process as dependências são responsabilidade do ambiente do worker. Veja o
[guia de deploy process](./deploy-process.md).
