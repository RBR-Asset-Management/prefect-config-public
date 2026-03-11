# rbr-prefect

Utilitário de deploy de flows Prefect para a RBR Asset Management.

## Instalação

```bash
pip install rbr-prefect
```

Ou para desenvolvimento local:

```bash
pip install -e .
```

## Uso Básico

```python
from rbr_prefect import DefaultDeploy
from flows.my_flow import my_flow

deploy = DefaultDeploy(
    flow_func=my_flow,
    name="my-flow-prod",
    tags=["dados-externos"],
)
deploy.parameters = deploy.override(country_name="Brazil")
deploy.deploy()
```

Para flows de scraping com Playwright:

```python
from rbr_prefect import ScrapeDeploy
from flows.scraper import scraper_flow

deploy = ScrapeDeploy(
    flow_func=scraper_flow,
    name="scraper-prod",
    tags=["BTG", "scraping"],
)
deploy.deploy()
```

## Agendamento

```python
from cronexpressions import every

deploy = DefaultDeploy(
    flow_func=my_flow,
    name="my-flow-prod",
    tags=["dados-externos"],
)
deploy.schedule(cron=every().weekday.at("09:00"))
deploy.deploy()
```

---

## Release: Bump de Versão e Publicação no PyPI

O processo de publicação é inteiramente local, sem pipeline de CI/CD.

### Pré-requisitos

1. **bump2version** instalado:
   ```bash
   uv add --dev bump2version
   ```

2. **Credenciais do PyPI** configuradas localmente via variável de ambiente:
   ```bash
   export UV_PUBLISH_TOKEN="pypi-xxxxxxxxxxxxxxxxxxxx"
   ```

   Ou via arquivo `~/.pypirc`:
   ```ini
   [distutils]
   index-servers = pypi

   [pypi]
   username = __token__
   password = pypi-xxxxxxxxxxxxxxxxxxxx
   ```

### Fluxo Completo de Release

```bash
# 1. Garantir que o branch main está limpo e atualizado
git checkout main
git pull origin main
git status  # deve estar limpo

# 2. Executar os testes (quando implementados)
uv run pytest

# 3. Bumpar a versão
#    Escolher: patch (0.1.0 → 0.1.1) | minor (0.1.0 → 0.2.0) | major (0.1.0 → 1.0.0)
bump2version patch

# O bump2version automaticamente:
#   - Atualiza a versão em pyproject.toml e rbr_prefect/__init__.py
#   - Cria o commit: "Bump version: 0.1.0 → 0.1.1"
#   - Cria a tag: "v0.1.1"

# 4. Push do commit e da tag
git push origin main
git push origin --tags

# 5. Build dos artifacts
uv build

# 6. Publicação no PyPI
uv publish
```

### Tipos de Bump

| Comando | Exemplo | Quando usar |
|---------|---------|-------------|
| `bump2version patch` | 0.1.0 → 0.1.1 | Bug fixes, pequenas correções |
| `bump2version minor` | 0.1.0 → 0.2.0 | Novas funcionalidades retrocompatíveis |
| `bump2version major` | 0.1.0 → 1.0.0 | Breaking changes |

### Verificando a Versão

```python
import rbr_prefect
print(rbr_prefect.__version__)
```

Ou via importlib:

```python
import importlib.metadata
print(importlib.metadata.version("rbr-prefect"))
```

---

## Licença

MIT
