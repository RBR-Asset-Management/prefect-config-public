# PLAN.md — Suíte de Testes `rbr-prefect`

## Contexto e Motivação

O diretório `tests/simple-flow-source-gh/` contém um script manual que não é
executável em CI, não tem assertions e hardcoda valores que deveriam ser
resolvidos automaticamente. O problema é estrutural: o pacote `rbr-prefect`
vive dentro do repo `prefect-config-public`, então `git rev-parse
--show-toplevel` retorna a raiz desse repo — não a raiz de um projeto de
flow típico. O script atual mascara isso hardcodando `entrypoint`, `github_url`
e `branch`, o que anula o propósito do teste de auto-resolução.

### Princípio central da nova suíte

**O filesystem é real. A infraestrutura é mockada.**

`find_requirements()` executa de verdade sobre `tmp_path` do pytest. Git,
Prefect API e output do terminal são interceptados via `unittest.mock.patch`.
Isso permite testar a detecção automática de dependências com `bizdays` real
num `requirements.txt` real, enquanto nenhuma chamada de rede é feita.

---

## Estrutura Final de Diretórios

```
tests/
├── conftest.py                   # fixtures compartilhadas
├── flows/
│   ├── teste_flow.py             # flow canônico — mantém bizdays intencionalmente
│   └── requirements.txt          # bizdays + prefect
├── test_deploy_simple.py         # suíte pytest principal
└── e2e/
    ├── README.md                  # pré-requisitos e procedimento manual
    └── deploy_teste_flow.py       # script E2E — zero hardcodes de infraestrutura
```

O diretório `tests/simple-flow-source-gh/` é deletado inteiramente.

---

## Parte 1 — Arquivos de Flow

### `tests/flows/teste_flow.py`

Flow intencionalmente simples. `bizdays` é mantido para exercitar a detecção
automática de requirements — esse é o propósito, não a lógica de negócio do
flow.

```python
import json
from datetime import datetime

import httpx
from bizdays import Calendar
from prefect import flow, get_run_logger, task


@task
def fetch_country_data(country_name: str) -> dict:
    response = httpx.get(
        f"https://restcountries.com/v3.1/name/{country_name}",
        timeout=10,
    )
    response.raise_for_status()
    return response.json()[0]


@flow(name="teste-flow")
def teste_flow(country_name: str = "Brazil") -> dict:
    logger = get_run_logger()
    cal = Calendar.load("ANBIMA")
    d = datetime.now()
    msg = "é" if cal.isbizday(d) else "não é"
    logger.info(f"Hoje {d:%d-%m-%Y} {msg} dia útil")
    data = fetch_country_data(country_name)
    logger.info(json.dumps(data, indent=2, ensure_ascii=False))
    return data
```

### `tests/flows/requirements.txt`

```
bizdays
prefect
```

---

## Parte 2 — Fixtures (`tests/conftest.py`)

### Hierarquia de dependência das fixtures

```
tmp_path  (pytest built-in)
    └── fake_repo_root
            ├── fake_repo_with_requirements   (escreve requirements.txt)
            └── mock_git                       (subprocess.run → fake_repo_root)
                    └── mock_flow_file          (inspect.getfile → path em fake_repo_root)

mock_prefect                                   (independente — intercepta Prefect API)
mock_ui                                        (independente — suprime terminal)
flow_func                                      (session scope — importa teste_flow)
```

### Constantes de módulo (não fixtures)

```python
FAKE_GITHUB_URL = "https://github.com/some-org/some-repo.git"
FAKE_BRANCH = "main"
```

### Descrição de cada fixture

**`fake_repo_root(tmp_path)`**
Retorna `tmp_path`. Existe como fixture nomeada para semântica clara nos
parâmetros dos testes.

**`fake_repo_with_requirements(fake_repo_root)`**
Escreve `"bizdays\nprefect\n"` em `fake_repo_root / "requirements.txt"`.
Retorna `fake_repo_root` (não o path do arquivo) para que testes que
precisam do root ainda o tenham.

**`mock_git(fake_repo_root)`**
Faz `patch("subprocess.run")`. A função substituta inspeciona `cmd`:

| Condição em `cmd` | `result.stdout` |
|---|---|
| `"--show-toplevel"` in cmd | `str(fake_repo_root) + "\n"` |
| `"get-url"` in cmd | `FAKE_GITHUB_URL + "\n"` |
| `"--abbrev-ref"` in cmd | `FAKE_BRANCH + "\n"` |

`result.returncode = 0` em todos os casos.
Yield `{"repo_root": fake_repo_root, "github_url": FAKE_GITHUB_URL, "branch": FAKE_BRANCH}`.

**`mock_flow_file(mock_git, fake_repo_root)`**
Faz `patch("inspect.getfile")` retornando `str(fake_repo_root / "flows" / "teste_flow.py")`.
O arquivo não precisa existir no disco — apenas o path importa para `relative_to()`.
Yield `fake_repo_root / "flows" / "teste_flow.py"`.

**`mock_prefect()`**
Cria `mock_deployable = MagicMock()` com `mock_deployable.deploy = MagicMock(return_value=None)`.
Faz patch de:
- `prefect_github.GitHubCredentials.load` → `MagicMock()`
- `rbr_prefect.deploy.GitHubSourceStrategy.build` → `MagicMock()`

Para interceptar `flow_func.from_source(...)` em `BaseDeploy.deploy()`:
investigar a API do objeto `Flow` do Prefect e escolher o método mais estável.
Se `from_source` não for patchável diretamente via `patch.object`, fazer patch
de `rbr_prefect.deploy.BaseDeploy.deploy` e verificar argumentos via `call_args`.
Yield `mock_deployable`.

**`mock_ui()`**
Faz patch de `rbr_prefect._cli.ui.Confirm.ask` → `True`.
Faz patch de `rbr_prefect._cli.ui._console` → `MagicMock()`.
Yield o mock do `_console`.

**`flow_func()`** (scope="session")
```python
from tests.flows.teste_flow import teste_flow
return teste_flow
```

---

## Parte 3 — Casos de Teste (`tests/test_deploy_simple.py`)

### `TestAutoResolve`

Valida que a resolução automática via git produz os valores corretos.

| Teste | Fixtures | Assertion |
|---|---|---|
| `test_resolve_github_url` | `mock_git, mock_ui, flow_func` | `strategy.resolved_github_url == FAKE_GITHUB_URL` |
| `test_resolve_branch` | `mock_git, mock_ui, flow_func` | `strategy.resolved_branch == FAKE_BRANCH` |
| `test_resolve_entrypoint_format` | `mock_git, mock_flow_file, mock_ui, flow_func` | `deploy._entrypoint == "flows/teste_flow.py:teste_flow"` — sem path absoluto, separador posix |
| `test_repo_root_cached` | `mock_git, mock_ui, flow_func` | `subprocess.run` chamado exatamente 1x para `--show-toplevel` após 2 acessos a `resolved_repo_root` |

### `TestExplicitOverrides`

Valida que overrides explícitos suprimem chamadas ao git.

| Teste | Assertion |
|---|---|
| `test_explicit_github_url_skips_subprocess` | Com `github_url=` explícito, nenhuma chamada com `"get-url"` em cmd |
| `test_explicit_branch_skips_subprocess` | Com `branch=` explícito, nenhuma chamada com `"--abbrev-ref"` em cmd |
| `test_explicit_entrypoint_skips_getfile` | Com `entrypoint=` explícito, `inspect.getfile` não chamado (patch com `side_effect=AssertionError`) |

### `TestInstantiation`

Valida construção e defaults das subclasses.

| Teste | Assertion |
|---|---|
| `test_default_deploy_defaults` | `_image == RBRDocker.DEFAULT_IMAGE`, `_work_pool_name == RBRWorkPools.DEFAULT` |
| `test_scrape_deploy_image` | `_image == RBRDocker.SCRAPE_IMAGE` |
| `test_sql_deploy_image` | `_image == RBRDocker.SQL_IMAGE` |
| `test_empty_tags_raises` | `ValueError` com texto de `ValidationMessages.TAGS_REQUIRED` |
| `test_env_mutex_raises` | `env_override={}` + `extra_env={}` → `ValueError` |
| `test_job_variables_mutex_raises` | `job_variables_override={}` + `extra_job_variables={}` → `ValueError` |

### `TestOverride`

Valida `override()` e o setter de `parameters`.

| Teste | Assertion |
|---|---|
| `test_override_merges_over_defaults` | `override(country_name="Argentina")` == `{"country_name": "Argentina"}` |
| `test_override_preserves_other_defaults` | Parâmetros não mencionados mantêm default |
| `test_override_invalid_key_raises` | `ValueError` mencionando o nome do parâmetro inválido |
| `test_parameters_setter_validates` | `deploy.parameters = {"bad_key": 1}` → `ValueError` |
| `test_parameters_setter_accepts_valid` | `deploy.parameters = deploy.override(country_name="X")` sem exceção; `_parameters["country_name"] == "X"` |

### `TestSchedule`

Valida `.schedule()`.

| Teste | Assertion |
|---|---|
| `test_no_args_raises` | `ValueError` |
| `test_two_args_raises` | `cron` + `interval` → `ValueError` |
| `test_cron_sets_cron_schedule` | `deploy._schedule` é `CronSchedule` |
| `test_schedule_returns_self` | Retorno é `deploy` (`is deploy`) |
| `test_interval_calls_confirm` | `Confirm.ask` chamado quando `interval=` fornecido |
| `test_interval_abort_raises_systemexit` | `Confirm.ask` retornando `False` → `SystemExit(0)` |

### `TestJobVariables`

Valida hierarquia de merge de `job_variables`.

| Teste | Assertion |
|---|---|
| `test_base_keys_present` | `volumes`, `auto_remove`, `image_pull_policy` no resultado |
| `test_cert_volume_in_volumes` | `RBRDocker.CERT_VOLUME` em `result["volumes"]` |
| `test_extra_merged_preserves_base` | `extra_job_variables={"k": "v"}` adiciona sem remover base |
| `test_override_bypass_total` | `job_variables_override={"only": True}` → resultado é exatamente `{"only": True}` |
| `test_env_key_not_overridable_via_extra` | `extra_job_variables={"env": {"bad": "x"}}` → `result["env"]` ainda é o de `_resolve_env()` |

### `TestEnv`

Valida hierarquia de merge de `env`.

| Teste | Assertion |
|---|---|
| `test_ssl_cert_in_base_env` | `PREFECT_API_SSL_CERT_FILE` presente; valor é `RBRPrefectServer.SSL_CERT_PATH` |
| `test_extra_env_merged` | `extra_env={"MY_VAR": "x"}` adiciona sem remover base |
| `test_env_override_bypass` | `env_override={"ONLY": "x"}` → env é exatamente `{"ONLY": "x"}` |

### `TestRequirementsResolution`

Valida detecção automática e explícita de requirements. `find_requirements()`
executa de verdade — o filesystem é real (`tmp_path`).

| Teste | Fixtures extras | Assertion |
|---|---|---|
| `test_no_requirements_when_empty_repo` | `mock_git` | `EXTRA_PIP_PACKAGES` ausente do env |
| `test_auto_detects_requirements_txt` | `fake_repo_with_requirements` | `EXTRA_PIP_PACKAGES` presente; `"bizdays"` e `"prefect"` na string |
| `test_detection_mode_is_txt` | `fake_repo_with_requirements` | `_requirements_detection_mode == RequirementsMessages.AUTO_DETECTED_TXT` |
| `test_explicit_requirements_source` | `fake_repo_root` | Arquivo em subpasta custom detectado; pacotes corretos no env |
| `test_explicit_source_detection_mode` | `fake_repo_root` | `_requirements_detection_mode` menciona o path do arquivo |
| `test_invalid_requirements_source_raises` | `mock_git` | `ValueError` para path inexistente |
| `test_requirements_format_is_space_separated` | `fake_repo_with_requirements` | `EXTRA_PIP_PACKAGES` é `str` com pacotes separados por espaço |
| `test_no_double_resolution` | `fake_repo_with_requirements` | `find_requirements` chamado exatamente 1x mesmo com `_resolve_requirements()` chamado 2x |

---

## Parte 4 — Script E2E (`tests/e2e/deploy_teste_flow.py`)

Com o flow e o pacote no mesmo repo (`prefect-config-public`), o script valida
auto-resolução de verdade — sem nenhum hardcode de infraestrutura:

```python
"""
Teste E2E manual — requer infraestrutura real da RBR.
NÃO faz parte do pytest. Ver tests/e2e/README.md.

Executar a partir da raiz do rbr-prefect/:
    cd rbr-prefect
    python tests/e2e/deploy_teste_flow.py
"""
from rbr_prefect import DefaultDeploy
from rbr_prefect.cron import CronBuilder
from tests.flows.teste_flow import teste_flow

if __name__ == "__main__":
    deploy = DefaultDeploy(
        flow_func=teste_flow,
        name="rbr-prefect-teste-flow",
        tags=["rbr-prefect", "teste"],
        requirements_source="tests/flows/requirements.txt",
    )
    deploy.parameters = deploy.override(country_name="Brazil")
    deploy.schedule(CronBuilder().on_weekdays().at_hour(4).at_minute(0))
    deploy.deploy()
```

O que este script valida automaticamente (sem hardcodes):

| Valor | Resolvido via |
|---|---|
| `github_url` | `git remote get-url origin` → URL do `prefect-config-public` |
| `branch` | `git rev-parse --abbrev-ref HEAD` |
| `entrypoint` | `inspect.getfile(teste_flow)` + `relative_to(repo_root)` → `rbr-prefect/tests/flows/teste_flow.py:teste_flow` |
| `requirements` | `from_requirements_txt("tests/flows/requirements.txt")` |

---

## Parte 5 — Configuração (`pyproject.toml`)

Adicionar seção `[tool.pytest.ini_options]`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
collect_ignore = ["tests/e2e"]
python_files = ["test_*.py"]
python_functions = ["test_*"]
addopts = "-v --tb=short"
```

`collect_ignore` garante que o script E2E nunca é coletado pelo pytest.

Garantir no grupo `[dependency-groups] dev`:
```toml
dev = [
    "pytest>=8.0.0",
    "pytest-mock>=3.14.0",
    "bump2version>=1.0.1",
]
```

---

## Parte 6 — Atualizações em `.instructions/CLAUDE.md`

1. Seção "Estrutura do Projeto": atualizar a árvore de `tests/` para a nova estrutura.
2. Seção "Escopo de testes para a v0.1.0":
   - Remover referência a `tests/simple-flow-source-gh/`
   - Critério de aceite passa a ser: `uv run pytest` verde **e** execução manual de `tests/e2e/deploy_teste_flow.py` contra a infraestrutura real

---

## Ordem de Execução

```
1. Criar tests/flows/teste_flow.py
2. Criar tests/flows/requirements.txt
3. Criar tests/e2e/README.md
4. Criar tests/e2e/deploy_teste_flow.py
5. Criar tests/conftest.py  (fixtures na ordem da hierarquia descrita na Parte 2)
6. Criar tests/test_deploy_simple.py  (classes na ordem da Parte 3)
7. Atualizar pyproject.toml
8. Atualizar .instructions/CLAUDE.md
9. Deletar tests/simple-flow-source-gh/
10. uv run pytest
11. uv run pytest --cov=rbr_prefect --cov-report=term-missing
    Reportar output completo de cobertura
```

---

## Restrições

- Não modificar nenhum arquivo em `rbr_prefect/`. Esta tarefa é exclusivamente de testes.
- Não usar `pytest-mock`'s `mocker` fixture. Usar `unittest.mock.patch` diretamente em `conftest.py` para centralizar e reutilizar a lógica de mock.
- Seguir as convenções de imports em três blocos e type hints de `CLAUDE.md` também nos arquivos de teste.
- Imports dentro dos métodos de teste (não no topo do arquivo) para evitar problemas em ambiente sem infraestrutura real.
