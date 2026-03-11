# TESTING_SIMPLE.md — Teste de Deploy: Flow Simples com Source GitHub

---

## Objetivo

Verificar que o pacote `rbr-prefect` consegue realizar o deploy de um flow simples usando `GitHubSourceStrategy` de ponta a ponta — desde a resolução automática do repositório até o registro do deploy no servidor Prefect da RBR.

Este é um **teste de integração manual**, não um teste automatizado com mocks. Ele requer acesso real ao servidor Prefect (`prefect-eve.rbr.local`) e ao repositório GitHub `RBR-Asset-Management/prefect-v3-test`.

---

## Contexto

O arquivo `tests/simple-flow-source-gh/deploy_flow_country.py` já existe como implementação de referência usando a API do Prefect diretamente (sem o pacote `rbr-prefect`). O teste simples consiste em criar uma versão equivalente desse mesmo deploy usando as classes do pacote, e verificar que o resultado no servidor Prefect é idêntico.

### Flow de referência

```
tests/simple-flow-source-gh/
├── flows/
│   └── flow_country.py          # flow a ser deployado
└── deploy_flow_country.py       # deploy de referência (API Prefect direta)
```

O flow `country_flow` em `flow_country.py` faz uma requisição HTTP para a API pública `restcountries.com` e loga o resultado. É intencionalmente simples — sem dependências internas, sem banco de dados, sem credenciais de negócio.

---

## Implementação do Teste

### Arquivo a criar

```
tests/simple-flow-source-gh/
├── flows/
│   └── flow_country.py
├── deploy_flow_country.py       # referência (não modificar)
└── deploy_flow_country_rbr.py   # novo — usa rbr_prefect
```

### Conteúdo esperado de `deploy_flow_country_rbr.py`

O arquivo deve reproduzir o mesmo deploy de `deploy_flow_country.py`, mas usando `DefaultDeploy` do pacote `rbr-prefect` em vez da API do Prefect diretamente:

```python
from rbr_prefect import DefaultDeploy
from flows.flow_country import country_flow

if __name__ == "__main__":
    deploy = DefaultDeploy(
        flow_func=country_flow,
        name="country-prefect-test",
        tags=["teste"],
    )
    deploy.parameters = deploy.override(country_name="Brazil")
    deploy.deploy()
```

O pacote deve inferir automaticamente todos os valores que estão hardcoded em `deploy_flow_country.py`:

| Valor em `deploy_flow_country.py` | Como o pacote deve resolver |
|---|---|
| `url="https://github.com/RBR-Asset-Management/prefect-v3-test.git"` | `git remote get-url origin` |
| `branch="main"` | `git rev-parse --abbrev-ref HEAD` |
| `entrypoint="rbr-prefect/tests/.../country_flow.py:country_flow"` | `inspect.getfile(country_flow)` + `relative_to(repo_root)` |
| `credentials=GitHubCredentials.load("rbr-org-github-finegrained-access-token")` | `RBRBlocks.GITHUB_CREDENTIALS` |
| `work_pool_name="default"` | `RBRWorkPools.DEFAULT` |
| `image="prefecthq/prefect:3-python3.12"` | `RBRDocker.DEFAULT_IMAGE` |
| `job_variables={...}` completo | `BaseDeploy._build_base_job_variables()` + `_build_base_env()` |

---

## Critérios de Sucesso

### Critério 1 — Execução sem erros

Executar `python deploy_flow_country_rbr.py` a partir do diretório `tests/simple-flow-source-gh/` deve completar sem exceções.

### Critério 2 — Painel de auditoria exibido

O terminal deve exibir o painel de auditoria do `rbr-prefect` com os valores resolvidos automaticamente antes da linha separadora do Prefect. Verificar visualmente que:

- `github_url` foi detectado corretamente como `https://github.com/RBR-Asset-Management/prefect-v3-test.git`
- `branch` foi detectado como `main`
- `entrypoint` foi resolvido como `rbr-prefect/tests/simple-flow-source-gh/flows/flow_country.py:country_flow`
- `parameters` exibe `{"country_name": "Brazil"}`

### Critério 3 — Deploy registrado no Prefect UI

Acessar `https://prefect-eve.rbr.local` e verificar que o deploy `country-prefect-test` aparece na lista de deploys com:

- Work pool: `default`
- Tags: `["teste"]`
- Parâmetros: `{"country_name": "Brazil"}`

### Critério 4 — Equivalência com o deploy de referência

O deploy criado por `deploy_flow_country_rbr.py` deve ser **funcionalmente idêntico** ao criado por `deploy_flow_country.py`. Disparar uma execução manual de ambos no Prefect UI e verificar que ambos completam com sucesso, retornando os dados do país "Brazil".

### Critério 5 — `job_variables` corretos no container

Ao inspecionar a execução do flow no Prefect UI (aba de detalhes do flow run), verificar que as variáveis de ambiente foram injetadas corretamente no container:

```
PREFECT_API_URL             = https://prefect-eve.rbr.local/api
PREFECT_API_SSL_CERT_FILE   = /host-certs/rbr-root-ca.crt
PREFECT_API_AUTH_STRING     = {{ prefect.blocks.basic-auth-credentials.walle-basic-auth.token_config.auth_string }}
PREFECT_CLIENT_CUSTOM_HEADERS = {{ prefect.blocks.basic-auth-credentials.walle-basic-auth.token_config.header }}
```

---

## Pré-requisitos para Execução

Antes de executar o teste, verificar:

1. **`rbr-prefect` instalado no ambiente** — `pip install -e .` a partir da raiz do repositório, ou `uv sync`.
2. **`profiles.toml` configurado** — credenciais de acesso ao servidor Prefect configuradas via `prefect-config-install` ou manualmente em `~/.prefect/profiles.toml`.
3. **Bloco `rbr-org-github-finegrained-access-token` existente** no servidor Prefect — necessário para `GitHubCredentials.load()`.
4. **Bloco `walle-basic-auth` existente** no servidor Prefect — necessário para os templates de autenticação no env.
5. **Repositório clonado em branch `main`** com remote `origin` apontando para `RBR-Asset-Management/prefect-v3-test`.
6. **Worker ativo no work pool `default`** no servidor Prefect para que o flow run possa ser executado.

---

## Procedimento de Execução

```bash
# 1. A partir da raiz do repositório rbr-prefect
cd tests/simple-flow-source-gh

# 2. Executar o deploy usando o pacote rbr-prefect
python deploy_flow_country_rbr.py

# 3. Verificar o output no terminal — painel de auditoria deve aparecer
# 4. Acessar https://prefect-eve.rbr.local e verificar o deploy registrado
# 5. Disparar execução manual e verificar que o flow run completa com sucesso
```

---

## Diagnóstico de Falhas Comuns

| Sintoma | Causa provável | O que verificar |
|---|---|---|
| `RuntimeError: Não foi possível detectar a raiz do repositório Git` | Script executado fora de um repositório Git, ou Git não instalado | Executar `git rev-parse --show-toplevel` manualmente no diretório |
| `RuntimeError: Não foi possível detectar a URL do repositório remoto` | Remote `origin` não configurado | Executar `git remote get-url origin` e verificar o output |
| `ValueError: O arquivo da função flow está fora do repositório Git` | Repositório clonado em caminho inesperado, ou `inspect.getfile` retornando caminho errado | Verificar o caminho absoluto de `flow_country.py` e o repo root detectado no painel de auditoria |
| `prefect.exceptions.ObjectNotFound` ao carregar credenciais | Bloco `rbr-org-github-finegrained-access-token` não existe no servidor | Criar o bloco `GitHubCredentials` no Prefect UI antes de executar |
| Deploy criado mas flow run falha com `401 Unauthorized` | Bloco `walle-basic-auth` não existe ou credenciais inválidas | Verificar o bloco no Prefect UI e recriar se necessário |
| Deploy criado mas flow run falha com erro de certificado SSL | Volume de certificados não montado corretamente no worker | Verificar que o path `/home/rbr-admin/certs` existe no host do worker |