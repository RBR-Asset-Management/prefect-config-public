# Requisitos Técnicos — `rbr-prefect`

---
## Seção 1 — Visão Geral e Estrutura do Pacote

### 1.1 Descrição Geral

`rbr-prefect` é um pacote Python interno da RBR Asset Management que padroniza e simplifica o processo de deploy de flows do Prefect 3. O pacote encapsula toda a configuração de infraestrutura da RBR — credenciais, URLs, imagens Docker, variáveis de ambiente, volumes — eliminando a necessidade de repetir essas configurações em cada repositório de flow.

Cada dev importa o pacote no projeto em que estiver desenvolvendo um flow e utiliza as classes de deploy fornecidas. O arquivo `deploy.py` de cada projeto reside no próprio repositório do flow — não há repositório centralizado de deploys. O pacote é a única peça centralizada; os deploys permanecem distribuídos com seus respectivos flows.

---

### 1.2 Filosofia de Design

**Zero magic strings.** Nenhum valor literal hardcoded fora de arquivos de constantes dedicados. Toda string que representa uma configuração de infraestrutura, uma mensagem exibida ao dev, ou um valor padrão do sistema deve residir em uma classe de constantes — nunca inline no código de lógica.

**Separação estrita de responsabilidades.** Cada arquivo tem uma única responsabilidade. Arquivos de constantes não têm lógica. Arquivos de lógica não têm valores literais. A separação é aplicada tanto no pacote principal (`constants.py`, `deploy.py`) quanto no submódulo de CLI (`_cli/messages.py`, `_cli/ui.py`).

**Configuração na construção, execução explícita.** O objeto de deploy é configurado inteiramente no `__init__`. O método `.deploy()` é o único método com efeito colateral — nenhuma chamada de rede, nenhuma interação com a API do Prefect ocorre antes dele ser chamado explicitamente.

**Detecção automática com override explícito.** Valores que podem ser inferidos automaticamente — URL do repositório GitHub, branch atual, entrypoint do flow — são resolvidos via introspecção Git e de função Python. Todo valor automático pode ser sobrescrito pelo dev com um valor explícito. Quando valores automáticos são utilizados, o pacote os exibe no terminal antes de executar o deploy.

**Sem dependências extras.** O pacote utiliza exclusivamente bibliotecas que já são dependências diretas do Prefect (`rich`, `pydantic`) ou da biblioteca padrão do Python (`inspect`, `subprocess`, `pathlib`). Nenhuma nova dependência transitiva é introduzida, com exceção de `cronexpressions` para construção de expressões cron e `prefect-github` para integração com o GitHub.

---

### 1.3 Distribuição

O pacote é distribuído publicamente no PyPI sob o nome `rbr-prefect`. A decisão de distribuição pública é intencional e segura: todos os segredos, tokens e credenciais são referenciados como blocos do Prefect — nunca armazenados no código-fonte. URLs e caminhos de infraestrutura que aparecem no código são locais à rede interna da RBR e não representam risco de segurança por si só.

**Nome no PyPI:** `rbr-prefect`  
**Nome do pacote Python (importação):** `rbr_prefect`  
**Versão inicial:** `0.1.0`  
**Python requerido:** `>=3.12`

---

### 1.4 `pyproject.toml`

```toml
[project]
name = "rbr-prefect"
version = "0.1.0"
description = "Utilitário de deploy de flows Prefect para a RBR Asset Management."
readme = "README.md"
requires-python = ">=3.12"
license = { text = "MIT" }

dependencies = [
    "prefect>=3.0.0",
    "prefect-github>=0.4.2",
    "cronexpressions>=1.0.0",
]

[project.urls]
Repository = "https://github.com/RBR-Asset-Management/rbr-prefect"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.bumpversion]
current_version = "0.1.0"
commit = true
tag = true

[[tool.bumpversion.files]]
filename = "pyproject.toml"
search = 'version = "{current_version}"'
replace = 'version = "{new_version}"'

[[tool.bumpversion.files]]
filename = "rbr_prefect/__init__.py"
search = '__version__ = "{current_version}"'
replace = '__version__ = "{new_version}"'
```

**Dependências de desenvolvimento** (não incluídas no pacote distribuído):

```toml
[dependency-groups]
dev = [
    "bump2version>=1.0.1",
    "pytest>=8.0.0",
    "pytest-mock>=3.14.0",
]
```

---

### 1.5 Estrutura de Diretórios

```
rbr-prefect/                          # raiz do repositório
├── rbr_prefect/                      # pacote Python
│   ├── __init__.py                   # superfície pública do pacote
│   ├── constants.py                  # todas as constantes de infraestrutura RBR
│   ├── deploy.py                     # classes de deploy — BaseDeploy, DefaultDeploy, ScrapeDeploy
│   └── _cli/                         # submódulo interno de interface de terminal
│       ├── __init__.py               # expõe apenas funções de alto nível de ui.py
│       ├── messages.py               # constantes de texto e factories de mensagens
│       └── ui.py                     # lógica de apresentação com rich
├── tests/                            # testes automatizados
│   └── ...
├── .instructions/                    # instrução para claude
│   ├── REQUIREMENTS.md               # este documento
│   ├── TESTING_EXTENSIVE.md          # requisitos de testes extensivos, usar apenas como referência. Será implementado no futuro
│   └── TESTING_sIMPLE.md             # especificação do teste simplificado, deve ser implementado na primeira versão do utilitário
├── README.md                         # documentação de uso para devs
├── pyproject.toml
└── uv.lock
```

---

### 1.6 Separação de Responsabilidades entre Arquivos

| Arquivo | Responsabilidade | Tem lógica? | Tem valores literais? |
|---|---|---|---|
| `constants.py` | Fonte única da verdade para toda configuração de infraestrutura RBR | Não | Sim — é o único lugar autorizado |
| `deploy.py` | Classes de deploy; toda lógica de construção, validação e execução | Sim | Não — referencia `constants.py` |
| `_cli/messages.py` | Fonte única da verdade para todos os textos exibidos ao dev no terminal | Mínima — apenas factories de interpolação | Sim — é o único lugar autorizado para textos de UI |
| `_cli/ui.py` | Lógica de apresentação: formatação, prompts, prints | Sim | Não — referencia `messages.py` |
| `_cli/__init__.py` | Controle da superfície pública do submódulo `_cli` | Não | Não |
| `__init__.py` | Controle da superfície pública do pacote | Não | Não |

---

### 1.7 Fluxo de Uso pelo Dev

O fluxo típico de um dev criando um novo deploy é:

```python
# deploy.py — na raiz do repositório do flow
from rbr_prefect import DefaultDeploy
from flows.country_flow import country_flow

deploy = DefaultDeploy(
    flow_func=country_flow,
    name="country-flow-prod",
    tags=["BTG", "dados-externos"],
)

deploy.parameters = deploy.override(country_name="Argentina")
deploy.schedule(cron=every().weekday.at("09:00"))
deploy.deploy()
```

O dev nunca precisa informar: URL do GitHub, branch, entrypoint, URL da API do Prefect, credenciais de autenticação, imagem Docker, volumes, variáveis de ambiente de infraestrutura. Tudo isso é resolvido automaticamente pelo pacote.

---

### 1.8 Fluxo de Release do Pacote

O processo de publicação de novas versões é inteiramente local, sem pipeline de CI/CD:

```bash
# 1. Bump da versão (patch | minor | major)
bump2version patch

# 2. Build dos artifacts
uv build

# 3. Publicação no PyPI
uv publish
```

As credenciais do PyPI são configuradas localmente via variáveis de ambiente (`UV_PUBLISH_TOKEN`) ou no arquivo `~/.pypi/credentials` — nunca no repositório.

---

*Próxima seção: Seção 2 — `constants.py`*

---

## Seção 2 — `constants.py`

### 2.1 Papel e Princípios

`constants.py` é a **fonte única da verdade** para toda configuração de infraestrutura da RBR. É o único arquivo do pacote autorizado a conter valores literais de configuração. Qualquer string, URL, nome de imagem, nome de block ou caminho que represente uma decisão de infraestrutura deve residir aqui — nunca inline em `deploy.py`, `ui.py` ou qualquer outro arquivo de lógica.

**Princípios que governam este arquivo:**

- Zero lógica de negócio. O arquivo contém apenas definições de classes com atributos de classe.
- A única exceção permitida são métodos estáticos em `RBRBlocks` que compõem strings de template do Prefect programaticamente a partir das próprias constantes do arquivo — eliminando a última forma de magic string do sistema.
- Quando uma configuração de infraestrutura mudar (nova imagem Docker, nova URL de API, novo nome de block), apenas `constants.py` precisa ser editado. O diff do PR ficará isolado neste arquivo, tornando a revisão trivial e o histórico Git auditável.

---

### 2.2 Classe `RBRPrefectServer`

Centraliza os valores de conexão com o servidor Prefect da RBR.

```python
class RBRPrefectServer:
    API_URL = "https://prefect-eve.rbr.local/api"
    SSL_CERT_PATH = "/host-certs/rbr-root-ca.crt"
```

| Atributo | Valor | Uso |
|---|---|---|
| `API_URL` | `"https://prefect-eve.rbr.local/api"` | Variável de ambiente `PREFECT_API_URL` injetada nos `job_variables` de todo deploy |
| `SSL_CERT_PATH` | `"/host-certs/rbr-root-ca.crt"` | Variável de ambiente `PREFECT_API_SSL_CERT_FILE` injetada nos `job_variables`; corresponde ao ponto de montagem do volume de certificados dentro do container |

**Observação:** `SSL_CERT_PATH` é um caminho dentro do container Docker, não na máquina host. O mapeamento host→container é definido em `RBRDocker.CERT_VOLUME`.

---

### 2.3 Classe `RBRDocker`

Centraliza imagens Docker e configurações de container utilizadas nos deploys.

```python
class RBRDocker:
    DEFAULT_IMAGE = "prefecthq/prefect:3-python3.12"
    SCRAPE_IMAGE  = "rbr-custom/prefect-playwright:3-python3.12"
    CERT_VOLUME   = "/home/rbr-admin/certs:/host-certs:ro"
```

| Atributo | Valor | Uso |
|---|---|---|
| `DEFAULT_IMAGE` | `"prefecthq/prefect:3-python3.12"` | Imagem padrão para `DefaultDeploy`; passada como parâmetro `image` no `.deploy()` do Prefect |
| `SCRAPE_IMAGE` | `"rbr-custom/prefect-playwright:3-python3.12"` | Imagem customizada da RBR com Playwright instalado; utilizada por `ScrapeDeploy` |
| `CERT_VOLUME` | `"/home/rbr-admin/certs:/host-certs:ro"` | Mapeamento de volume no formato `host_path:container_path:mode`; injeta os certificados TLS da RBR dentro do container em modo somente leitura |

**Observação sobre `SCRAPE_IMAGE`:** Esta imagem deve estar disponível no registry Docker acessível pelo work pool. O valor exato do nome e tag deve ser atualizado quando uma nova versão da imagem for publicada no registry interno.

---

### 2.4 Classe `RBRWorkPools`

Centraliza os nomes dos work pools do Prefect configurados no servidor da RBR.

```python
class RBRWorkPools:
    DEFAULT = "default"
```

| Atributo | Valor | Uso |
|---|---|---|
| `DEFAULT` | `"default"` | Work pool padrão utilizado por todos os deploys — `DefaultDeploy` e `ScrapeDeploy`. Sobrescritável com prompt de confirmação obrigatório. |

**Observação:** A decisão de utilizar um único work pool para todos os flows (incluindo scraping) é intencional. A diferenciação entre tipos de flow é feita pela imagem Docker, não pelo work pool. Caso um work pool dedicado para scraping seja criado no futuro, um atributo `SCRAPE` deve ser adicionado aqui.

---

### 2.5 Classe `RBRBlocks`

Centraliza os nomes dos blocos do Prefect utilizados nos deploys e fornece métodos para compor programaticamente as strings de template do Prefect.

```python
class RBRBlocks:
    GITHUB_CREDENTIALS = "rbr-org-github-finegrained-access-token"
    BASIC_AUTH         = "walle-basic-auth"

    # Templates internos — não para uso direto fora desta classe
    _BLOCK_TYPE_BASIC_AUTH = "basic-auth-credentials"
    _AUTH_STRING_FIELD     = "token_config.auth_string"
    _HEADER_FIELD          = "token_config.header"

    @staticmethod
    def auth_string_template() -> str:
        """
        Retorna a string de template do Prefect para o campo auth_string
        do bloco Basic Auth, no formato esperado pela variável de ambiente
        PREFECT_API_AUTH_STRING.

        Formato gerado:
        {{ prefect.blocks.basic-auth-credentials.walle-basic-auth.token_config.auth_string }}
        """
        return (
            f"{{{{ prefect.blocks"
            f".{RBRBlocks._BLOCK_TYPE_BASIC_AUTH}"
            f".{RBRBlocks.BASIC_AUTH}"
            f".{RBRBlocks._AUTH_STRING_FIELD} }}}}"
        )

    @staticmethod
    def header_template() -> str:
        """
        Retorna a string de template do Prefect para o campo header
        do bloco Basic Auth, no formato esperado pela variável de ambiente
        PREFECT_CLIENT_CUSTOM_HEADERS.

        Formato gerado:
        {{ prefect.blocks.basic-auth-credentials.walle-basic-auth.token_config.header }}
        """
        return (
            f"{{{{ prefect.blocks"
            f".{RBRBlocks._BLOCK_TYPE_BASIC_AUTH}"
            f".{RBRBlocks.BASIC_AUTH}"
            f".{RBRBlocks._HEADER_FIELD} }}}}"
        )
```

| Atributo / Método | Tipo | Uso |
|---|---|---|
| `GITHUB_CREDENTIALS` | Constante pública | Nome do bloco `GitHubCredentials` carregado via `GitHubCredentials.load(RBRBlocks.GITHUB_CREDENTIALS)` em `GitHubSourceStrategy` |
| `BASIC_AUTH` | Constante pública | Nome do bloco `BasicAuthCredentials`; parte da composição das strings de template |
| `_BLOCK_TYPE_BASIC_AUTH` | Constante privada | Slug do tipo do bloco no Prefect; usado internamente pelos factories |
| `_AUTH_STRING_FIELD` | Constante privada | Caminho do campo dentro do bloco; usado internamente pelos factories |
| `_HEADER_FIELD` | Constante privada | Caminho do campo dentro do bloco; usado internamente pelos factories |
| `auth_string_template()` | Método estático público | Retorna a string de template completa para `PREFECT_API_AUTH_STRING` |
| `header_template()` | Método estático público | Retorna a string de template completa para `PREFECT_CLIENT_CUSTOM_HEADERS` |

**Motivação para os métodos factory em `RBRBlocks`:** As strings de template do Prefect para referência de blocos têm o formato `{{ prefect.blocks.<tipo>.<nome>.<campo> }}`. Hardcodar essas strings inteiras em `deploy.py` introduziria magic strings longas e frágeis. Ao compô-las programaticamente a partir dos atributos `BASIC_AUTH`, `_BLOCK_TYPE_BASIC_AUTH` e dos campos, garante-se que uma mudança no nome do bloco (ex: `walle-basic-auth` → `rbr-basic-auth`) se propague automaticamente para ambas as strings de template com a edição de um único atributo.

---

### 2.6 Classe `RBRJobVariables`

Centraliza as configurações fixas de `job_variables` que são aplicadas a todos os deploys da RBR, independentemente do tipo de flow.

```python
class RBRJobVariables:
    AUTO_REMOVE        = True
    IMAGE_PULL_POLICY  = "IfNotPresent"
```

| Atributo | Valor | Uso |
|---|---|---|
| `AUTO_REMOVE` | `True` | Configuração `auto_remove` nos `job_variables`; garante que containers Docker são removidos automaticamente após a execução do flow |
| `IMAGE_PULL_POLICY` | `"IfNotPresent"` | Configuração `image_pull_policy` nos `job_variables`; evita pull desnecessário da imagem se ela já estiver disponível localmente no worker |

---

### 2.7 Visão Consolidada de Como as Constantes São Consumidas

A tabela abaixo mapeia cada constante ao ponto exato onde ela é consumida na arquitetura do pacote:

| Constante | Consumida em | Contexto de uso |
|---|---|---|
| `RBRPrefectServer.API_URL` | `BaseDeploy._build_base_env()` | Variável de ambiente `PREFECT_API_URL` nos `job_variables` |
| `RBRPrefectServer.SSL_CERT_PATH` | `BaseDeploy._build_base_env()` | Variável de ambiente `PREFECT_API_SSL_CERT_FILE` nos `job_variables` |
| `RBRDocker.DEFAULT_IMAGE` | `DefaultDeploy.__init__` (default) | Parâmetro `image` no `.deploy()` do Prefect |
| `RBRDocker.SCRAPE_IMAGE` | `ScrapeDeploy.__init__` (default) | Parâmetro `image` no `.deploy()` do Prefect |
| `RBRDocker.CERT_VOLUME` | `BaseDeploy._build_base_job_variables()` | Chave `volumes` nos `job_variables` |
| `RBRWorkPools.DEFAULT` | `BaseDeploy.__init__` (default) | Parâmetro `work_pool_name` no `.deploy()` do Prefect |
| `RBRBlocks.GITHUB_CREDENTIALS` | `GitHubSourceStrategy._build()` | `GitHubCredentials.load(...)` |
| `RBRBlocks.auth_string_template()` | `BaseDeploy._build_base_env()` | Variável de ambiente `PREFECT_API_AUTH_STRING` nos `job_variables` |
| `RBRBlocks.header_template()` | `BaseDeploy._build_base_env()` | Variável de ambiente `PREFECT_CLIENT_CUSTOM_HEADERS` nos `job_variables` |
| `RBRJobVariables.AUTO_REMOVE` | `BaseDeploy._build_base_job_variables()` | Chave `auto_remove` nos `job_variables` |
| `RBRJobVariables.IMAGE_PULL_POLICY` | `BaseDeploy._build_base_job_variables()` | Chave `image_pull_policy` nos `job_variables` |

---

### 2.8 Regra de Evolução do Arquivo

Sempre que uma nova configuração de infraestrutura precisar ser introduzida no pacote, o processo é:

1. Adicionar o atributo na classe de constantes apropriada em `constants.py`.
2. Referenciar o atributo no arquivo de lógica que o consome.
3. Nunca introduzir o valor literal diretamente no arquivo de lógica.

Se nenhuma das classes existentes for o lar semântico correto para a nova constante, uma nova classe deve ser criada seguindo o padrão `RBR<Domínio>`.

---

*Próxima seção: Seção 3 — `_cli/messages.py` e `_cli/ui.py`*

---
## Seção 3 — `_cli/messages.py` e `_cli/ui.py`

### 3.1 Papel do Submódulo `_cli`

O submódulo `_cli` encapsula toda a interação com o terminal durante o processo de deploy. Ele é **interno ao pacote** — o prefixo `_` sinaliza que nenhum de seus membros faz parte da superfície pública. O dev que usa o pacote nunca importa diretamente de `_cli`; apenas `deploy.py` o consome.

O submódulo é dividido em dois arquivos com responsabilidades distintas e complementares:

- **`messages.py`** — o que é exibido. Fonte única da verdade para todos os textos, avisos e prompts mostrados ao dev no terminal. Nenhum texto literal aparece em `ui.py`.
- **`ui.py`** — como é exibido. Toda lógica de formatação, cores, painéis e prompts usando `rich`. Nenhum texto literal aparece aqui — apenas referências a `messages.py`.

---

### 3.2 Convenção de `messages.py`

O arquivo segue uma convenção de três tipos de membros por classe:

**Constantes públicas** (`UPPER_CASE`) — strings sem interpolação, para uso direto em `ui.py`:
```python
OVERRIDE_WARNING = "Sobrescrever o work pool é incomum e raramente necessário."
```

**Templates privados** (`_UPPER_CASE`) — strings com placeholders `{var}`, nunca usados diretamente fora da classe:
```python
_OVERRIDE_CONFIRM = "Confirma a sobrescrita do work pool para '{pool}'?"
```

**Métodos factory públicos** (`snake_case`) — recebem os valores de interpolação e retornam a string final; encapsulam o conhecimento dos placeholders:
```python
@staticmethod
def override_confirm(pool: str) -> str:
    return WorkPoolMessages._OVERRIDE_CONFIRM.format(pool=pool)
```

Esta convenção garante que `ui.py` nunca precisa conhecer a estrutura interna dos templates — apenas chama o factory com os argumentos corretos.

---

### 3.3 Classes de Mensagens em `messages.py`

#### `DeployMessages`

Mensagens do fluxo principal de auditoria e execução do deploy.

```python
class DeployMessages:
    # Cabeçalhos do painel de auditoria
    RESOLVED_HEADER   = "Valores resolvidos automaticamente"
    OVERRIDES_HEADER  = "Overrides aplicados"
    ENV_HEADER        = "Variáveis de ambiente (env resolvido)"

    # Labels das linhas do painel de auditoria
    LABEL_GITHUB_URL  = "github_url"
    LABEL_BRANCH      = "branch"
    LABEL_ENTRYPOINT  = "entrypoint"
    LABEL_PARAMETERS  = "parameters"
    LABEL_IMAGE       = "image"
    LABEL_WORK_POOL   = "work_pool_name"
    LABEL_TAGS        = "tags"
    LABEL_SCHEDULE    = "schedule"

    # Separador de passagem de responsabilidade
    HANDOFF_MESSAGE   = "Configuração validada. Passando para o Prefect..."

    # Templates e factories
    _DEPLOY_STARTING  = "Iniciando deploy: '{name}'"

    @staticmethod
    def deploy_starting(name: str) -> str:
        return DeployMessages._DEPLOY_STARTING.format(name=name)
```

#### `WorkPoolMessages`

Mensagens relacionadas ao prompt de confirmação de override do work pool.

```python
class WorkPoolMessages:
    OVERRIDE_WARNING  = (
        "Sobrescrever o work pool é incomum e raramente necessário. "
        "O work pool padrão RBR é suficiente para a grande maioria dos flows."
    )
    OVERRIDE_ABORTED  = "Deploy abortado pelo usuário."

    _OVERRIDE_CONFIRM = "Confirma a sobrescrita do work pool para '{pool}'?"

    @staticmethod
    def override_confirm(pool: str) -> str:
        return WorkPoolMessages._OVERRIDE_CONFIRM.format(pool=pool)
```

#### `ConcurrencyMessages`

Mensagens relacionadas ao prompt de confirmação de configuração de concurrency limit.

```python
class ConcurrencyMessages:
    WARNING = (
        "Configurar concurrency limit diretamente no deploy é incomum. "
        "O work pool e a queue já gerenciam concorrência por padrão."
    )
    ABORTED = "Deploy abortado pelo usuário."
    CONFIRM = "O controle de concorrência já existe no work pool. Confirma mesmo assim?"
```

#### `EnvMessages`

Mensagens relacionadas ao override total do env.

```python
class EnvMessages:
    OVERRIDE_WARNING = (
        "⚠  OVERRIDE TOTAL do env aplicado — "
        "toda a configuração de ambiente base da RBR foi ignorada."
    )
```

#### `JobVariablesMessages`

Mensagens relacionadas ao override total de job_variables.

```python
class JobVariablesMessages:
    OVERRIDE_WARNING = (
        "⚠  OVERRIDE TOTAL de job_variables aplicado — "
        "toda a configuração base de job_variables da RBR foi ignorada."
    )
```

#### `ScheduleMessages`

Mensagens relacionadas à configuração avançada de schedule.

```python
class ScheduleMessages:
    ADVANCED_WARNING = (
        "Interval e rrule são configurações avançadas de schedule. "
        "Para a maioria dos casos, o parâmetro cron é suficiente."
    )
    ADVANCED_CONFIRM = "Confirma o uso de schedule avançado (interval/rrule)?"
    ABORTED          = "Deploy abortado pelo usuário."
```

#### `ValidationMessages`

Mensagens de erro de validação lançadas como exceções ou exibidas antes de abortar.

```python
class ValidationMessages:
    TAGS_REQUIRED     = "Pelo menos uma tag é obrigatória."
    NAME_REQUIRED     = "O parâmetro 'name' é obrigatório."
    OUTSIDE_GIT_REPO  = (
        "Não foi possível detectar um repositório Git. "
        "Verifique se o script de deploy está dentro de um repositório Git "
        "ou forneça 'github_url' e 'branch' explicitamente."
    )
    NO_REMOTE_ORIGIN  = (
        "Não foi encontrado um remote 'origin' no repositório Git. "
        "Forneça 'github_url' explicitamente."
    )

    _INVALID_PARAM    = (
        "Parâmetro de override inválido: '{param}'. "
        "A função '{flow}' não possui esse parâmetro."
    )
    _SCHEDULE_MUTEX   = (
        "Apenas um tipo de schedule pode ser configurado por vez. "
        "Forneça 'cron', 'interval' ou 'rrule' — não múltiplos simultaneamente."
    )

    @staticmethod
    def invalid_param(param: str, flow: str) -> str:
        return ValidationMessages._INVALID_PARAM.format(param=param, flow=flow)

    @staticmethod
    def schedule_mutex() -> str:
        return ValidationMessages._SCHEDULE_MUTEX
```

---

### 3.4 `_cli/__init__.py`

Expõe apenas as funções de alto nível de `ui.py`. `messages.py` permanece invisível para fora do submódulo.

```python
from .ui import (
    print_audit_panel,
    print_handoff,
    confirm_work_pool_override,
    confirm_concurrency_limit,
    confirm_advanced_schedule,
)
```

---

### 3.5 Lógica de `ui.py`

`ui.py` utiliza `rich` para toda a formatação. Uma única instância de `Console` é criada no topo do módulo com `file=sys.stdout` explícito para garantir flush síncrono antes da passagem de responsabilidade ao Prefect.

```python
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.prompt import Confirm
from rich.table import Table
import sys

_console = Console(file=sys.stdout)
```

#### Função `print_audit_panel`

Exibe o painel de auditoria com todos os valores resolvidos e overrides aplicados imediatamente antes do deploy. Recebe um dict estruturado com os valores resolvidos e overrides.

```python
def print_audit_panel(resolved: dict, overrides: dict, env: dict) -> None:
    ...
```

Comportamento esperado:
- Exibe uma tabela com duas colunas (`campo` | `valor`) para os valores resolvidos automaticamente, usando o cabeçalho `DeployMessages.RESOLVED_HEADER`.
- Se `overrides` não estiver vazio, exibe uma segunda tabela com os overrides aplicados, usando o cabeçalho `DeployMessages.OVERRIDES_HEADER`.
- Exibe uma terceira tabela com o env resolvido e merged, usando o cabeçalho `DeployMessages.ENV_HEADER`.
- Warnings de override total de env ou job_variables são exibidos em vermelho via `EnvMessages.OVERRIDE_WARNING` e `JobVariablesMessages.OVERRIDE_WARNING` quando aplicável.

#### Função `print_handoff`

Exibe o separador visual que marca a passagem de responsabilidade do terminal ao Prefect. Deve ser a última chamada de `ui.py` antes de `deployable.deploy()` ser invocado.

```python
def print_handoff(name: str) -> None:
    _console.print(DeployMessages.deploy_starting(name))
    _console.print(Rule(DeployMessages.HANDOFF_MESSAGE, style="green"))
```

O `rich.Rule` renderiza uma linha horizontal com o texto centralizado — separador visual claro entre o output do `rbr-prefect` e o output do Prefect.

#### Função `confirm_work_pool_override`

Exibe aviso e solicita confirmação interativa quando o dev fornece um `work_pool_name` diferente do default. Retorna `True` se confirmado, `False` se negado.

```python
def confirm_work_pool_override(pool_name: str) -> bool:
    _console.print(WorkPoolMessages.OVERRIDE_WARNING, style="yellow")
    confirmed = Confirm.ask(WorkPoolMessages.override_confirm(pool_name))
    if not confirmed:
        _console.print(WorkPoolMessages.OVERRIDE_ABORTED, style="red")
    return confirmed
```

#### Função `confirm_concurrency_limit`

Exibe aviso e solicita confirmação interativa quando o dev fornece `concurrency_limit`. Retorna `True` se confirmado, `False` se negado.

```python
def confirm_concurrency_limit() -> bool:
    _console.print(ConcurrencyMessages.WARNING, style="yellow")
    confirmed = Confirm.ask(ConcurrencyMessages.CONFIRM)
    if not confirmed:
        _console.print(ConcurrencyMessages.ABORTED, style="red")
    return confirmed
```

#### Função `confirm_advanced_schedule`

Exibe aviso e solicita confirmação interativa quando o dev usa `interval` ou `rrule` em vez de `cron`. Retorna `True` se confirmado, `False` se negado.

```python
def confirm_advanced_schedule() -> bool:
    _console.print(ScheduleMessages.ADVANCED_WARNING, style="yellow")
    confirmed = Confirm.ask(ScheduleMessages.ADVANCED_CONFIRM)
    if not confirmed:
        _console.print(ScheduleMessages.ABORTED, style="red")
    return confirmed
```

---

### 3.6 Contrato de Passagem de Responsabilidade do Terminal

A interação do `rbr-prefect` com o terminal é **estritamente sequencial e pré-execução**. O contrato é:

1. Toda interação com o terminal ocorre dentro do método `.deploy()` de `BaseDeploy`, antes da chamada a `deployable.deploy()`.
2. A ordem das interações é fixa: validações → prompts de confirmação → painel de auditoria → linha separadora (`print_handoff`).
3. `print_handoff` é a **última** chamada a `ui.py` antes de `deployable.deploy()` ser invocado.
4. O terminal não é limpo em nenhum momento — o output do Prefect continua imediatamente após a linha separadora. A ausência de limpeza é intencional e deve ser preservada.
5. Todos os prints de `ui.py` são síncronos e bloqueantes por design do `rich.Console` com `file=sys.stdout`.

```
[rbr-prefect owns o terminal]
  → validações de parâmetros (exceções síncronas se inválido)
  → confirm_work_pool_override()   # apenas se work_pool foi sobrescrito
  → confirm_concurrency_limit()    # apenas se concurrency_limit foi fornecido
  → confirm_advanced_schedule()    # apenas se interval ou rrule foi usado
  → print_audit_panel()            # sempre
  → print_handoff()                # sempre, última chamada

[Prefect owns o terminal]
  → deployable.deploy(...)         # único efeito colateral real
```

Se qualquer prompt de confirmação retornar `False`, o deploy é abortado com `SystemExit(0)` — não uma exceção, pois o abort é uma decisão do usuário, não um erro.

---

*Próxima seção: Seção 4 — Source Strategy*


## Seção 4 — Source Strategy

### 4.1 Motivação e Papel

A "source strategy" é a abstração que responde à pergunta: **de onde o Prefect vai buscar o código do flow no momento da execução?** Atualmente a resposta é sempre "do GitHub via `flow.from_source()`", mas existe um caso de uso futuro previsto onde o código estará embutido diretamente em uma imagem Docker customizada no registry da RBR.

Para que a adição dessa segunda estratégia no futuro não exija alterações nas classes de deploy (`BaseDeploy`, `DefaultDeploy`, `ScrapeDeploy`), a lógica de construção do source é isolada em uma hierarquia própria de classes. As classes de deploy são agnósticas à estratégia — elas apenas chamam `source_strategy.build()` e recebem o objeto que o Prefect espera.

Toda a hierarquia de source strategy reside em `deploy.py`, junto às classes de deploy, pois são conceitos intimamente relacionados e não justificam um arquivo separado.

---

### 4.2 Hierarquia de Classes

```
BaseSourceStrategy          (classe base abstrata — define o contrato)
├── GitHubSourceStrategy    (implementação atual — from_source + GitRepository)
└── DockerSourceStrategy    (esqueleto futuro — código embutido na imagem)
```

---

### 4.3 `BaseSourceStrategy`

Define o contrato que toda estratégia de source deve implementar. É uma classe abstrata com um único método obrigatório.

```python
from abc import ABC, abstractmethod

class BaseSourceStrategy(ABC):

    @abstractmethod
    def build(self) -> any:
        """
        Constrói e retorna o objeto de source esperado pelo Prefect.
        Para GitHubSourceStrategy, retorna um GitRepository.
        Para DockerSourceStrategy, retorna None (código já está na imagem).
        """
        ...

    @abstractmethod
    def resolve_entrypoint(self, flow_func: Callable) -> str:
        """
        Resolve o entrypoint no formato esperado pelo Prefect:
        'caminho/relativo/ao/repo/flow_file.py:nome_da_funcao'

        A lógica de resolução é responsabilidade da estratégia pois
        depende do contexto de onde o código reside.
        """
        ...
```

**Observação de design:** `resolve_entrypoint` é método da estratégia — e não de `BaseDeploy` — porque a forma de calcular o entrypoint depende intrinsecamente de onde o código reside. Para `GitHubSourceStrategy`, o entrypoint é relativo à raiz do repositório Git. Para `DockerSourceStrategy`, pode ser relativo à raiz da imagem ou a um caminho fixo configurado na imagem.

---

### 4.4 `GitHubSourceStrategy`

Implementação atual e padrão. Responsável por:

1. Detectar automaticamente a URL do repositório GitHub, o branch atual e a raiz do repositório Git via chamadas `subprocess` ao `git`.
2. Calcular o entrypoint relativo da função flow usando `inspect.getfile()` e `pathlib.Path.relative_to()`.
3. Construir e retornar o objeto `GitRepository` do `prefect-github`.

```python
from prefect.runner.storage import GitRepository
from prefect_github import GitHubCredentials
from rbr_prefect.constants import RBRBlocks

class GitHubSourceStrategy(BaseSourceStrategy):

    def __init__(
        self,
        github_url: str | None = None,
        branch: str | None = None,
    ) -> None:
        """
        Se github_url ou branch forem None, serão detectados automaticamente
        via introspecção Git no momento em que build() ou resolve_entrypoint()
        forem chamados.
        """
        self._github_url_override = github_url
        self._branch_override     = branch
        self._repo_root: Path | None = None  # cache após primeira detecção

    def build(self) -> GitRepository:
        return GitRepository(
            url=self._resolve_github_url(),
            branch=self._resolve_branch(),
            credentials=GitHubCredentials.load(RBRBlocks.GITHUB_CREDENTIALS),
        )

    def resolve_entrypoint(self, flow_func: Callable) -> str:
        repo_root   = self._resolve_repo_root()
        source_file = Path(inspect.getfile(flow_func))

        # Normaliza .pyc → .py
        if source_file.suffix == ".pyc":
            source_file = source_file.with_suffix(".py")

        relative_path = source_file.relative_to(repo_root)
        func_name     = flow_func.__name__

        return f"{relative_path.as_posix()}:{func_name}"
```

#### 4.4.1 Detecção Automática via Git

Todos os valores automáticos são obtidos via `subprocess` chamando o CLI do `git`. As chamadas são feitas de forma lazy — apenas quando o valor é necessário pela primeira vez — e o `repo_root` é cacheado para evitar múltiplas chamadas ao subprocess.

```python
def _resolve_repo_root(self) -> Path:
    if self._repo_root is not None:
        return self._repo_root

    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=True,
    )
    self._repo_root = Path(result.stdout.strip())
    return self._repo_root

def _resolve_github_url(self) -> str:
    if self._github_url_override is not None:
        return self._github_url_override

    result = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()

def _resolve_branch(self) -> str:
    if self._branch_override is not None:
        return self._branch_override

    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()
```

#### 4.4.2 Tratamento de Erros da Detecção Automática

Quando a detecção automática falha — script executado fora de um repositório Git, remote `origin` inexistente, `inspect.getfile()` retornando caminho fora do repo — a classe deve lançar exceções descritivas que orientem o dev sobre como resolver o problema.

| Situação de erro | Exceção | Mensagem orientativa |
|---|---|---|
| `git rev-parse --show-toplevel` falha | `RuntimeError` | "Não foi possível detectar a raiz do repositório Git. Certifique-se de executar o deploy.py dentro de um repositório Git, ou forneça `github_url` explicitamente." |
| `git remote get-url origin` falha | `RuntimeError` | "Não foi possível detectar a URL do repositório remoto. Certifique-se de que o remote 'origin' está configurado, ou forneça `github_url` explicitamente." |
| `source_file` não está dentro de `repo_root` | `ValueError` | "O arquivo da função flow está fora do repositório Git detectado. Forneça o `entrypoint` explicitamente." |
| `inspect.getfile()` retorna `.pyc` e `.py` correspondente não existe | `FileNotFoundError` | "Não foi possível localizar o arquivo fonte (.py) da função flow." |

Todas as exceções devem ser lançadas **antes** de qualquer interação com o terminal via `_cli/ui.py`, para que o dev veja o erro imediatamente na construção do objeto, não no momento do deploy.

#### 4.4.3 Valores Resolvidos Automaticamente — Exposição para o Print de Auditoria

`GitHubSourceStrategy` deve expor os valores resolvidos como propriedades somente leitura para que `BaseDeploy` possa passá-los ao `_cli/ui.py` no momento do print de auditoria:

```python
@property
def resolved_github_url(self) -> str:
    return self._resolve_github_url()

@property
def resolved_branch(self) -> str:
    return self._resolve_branch()

@property
def resolved_repo_root(self) -> Path:
    return self._resolve_repo_root()
```

Essas propriedades são chamadas apenas uma vez, pois o `repo_root` é cacheado e `github_url`/`branch` usam os overrides diretos quando fornecidos.

---

### 4.5 `DockerSourceStrategy` — Esqueleto Futuro

Classe esqueleto que sinaliza explicitamente que a funcionalidade será implementada no futuro. Não contém lógica — apenas a estrutura e documentação da intenção.

```python
class DockerSourceStrategy(BaseSourceStrategy):
    """
    Estratégia de source para flows cujo código está embutido diretamente
    em uma imagem Docker customizada no registry da RBR.

    Neste caso, o Prefect não precisa buscar o código de um repositório
    externo — o entrypoint aponta para um caminho fixo dentro da imagem.

    ** NÃO IMPLEMENTADO — previsto para implementação futura. **

    Quando implementado, esta estratégia deverá:
    - Receber o caminho do entrypoint dentro da imagem como parâmetro obrigatório.
    - Retornar None em build() (sem GitRepository necessário).
    - O deploy será realizado via flow.deploy() diretamente, sem from_source().
    """

    def build(self) -> None:
        raise NotImplementedError(
            "DockerSourceStrategy ainda não está implementada. "
            "Use GitHubSourceStrategy para deploys a partir do GitHub."
        )

    def resolve_entrypoint(self, flow_func: Callable) -> str:
        raise NotImplementedError(
            "DockerSourceStrategy ainda não está implementada."
        )
```

---

### 4.6 Como `BaseDeploy` Consome a Source Strategy

`BaseDeploy` recebe a estratégia como parâmetro no `__init__` com `GitHubSourceStrategy` como default. O tipo declarado é `BaseSourceStrategy`, garantindo que qualquer implementação futura seja aceita sem alterações em `BaseDeploy`.

```python
class BaseDeploy(Generic[P]):
    def __init__(
        self,
        ...,
        source_strategy: BaseSourceStrategy | None = None,
    ) -> None:
        # Se None, instancia GitHubSourceStrategy com detecção automática
        self._source_strategy = source_strategy or GitHubSourceStrategy()
```

O `entrypoint` é resolvido pela estratégia imediatamente na construção:

```python
        self._entrypoint = (
            entrypoint
            or self._source_strategy.resolve_entrypoint(flow_func)
        )
```

No momento do `.deploy()`, a estratégia constrói o source:

```python
        deployable = flow_func.from_source(
            source=self._source_strategy.build(),
            entrypoint=self._entrypoint,
        )
```

---

### 4.7 Resumo dos Overrides Disponíveis na Source Strategy

O dev raramente precisará customizar a source strategy. Quando precisar, há dois níveis de intervenção:

**Nível 1 — Override de valores individuais** (uso mais comum): passar `github_url` e/ou `branch` diretamente no construtor de `BaseDeploy`, que os repassa para `GitHubSourceStrategy`:

```python
DefaultDeploy(
    flow_func=country_flow,
    name="country-flow-staging",
    github_url="https://github.com/RBR/outro-repo.git",
    branch="staging",
    tags=["BTG"],
)
```

**Nível 2 — Override da estratégia inteira** (uso excepcional): passar uma instância customizada de `BaseSourceStrategy`:

```python
DefaultDeploy(
    flow_func=country_flow,
    name="country-flow-prod",
    source_strategy=GitHubSourceStrategy(
        github_url="https://github.com/RBR/repo-especial.git",
        branch="release/v2",
    ),
    tags=["BTG"],
)
```

---

*Próxima seção: Seção 5 — `BaseDeploy` e `Generic[P]`*

---

## Seção 5 — `BaseDeploy` e `Generic[P]`

### 5.1 Papel e Responsabilidades

`BaseDeploy` é a classe central do pacote. Ela concentra toda a lógica de construção, validação e execução de um deploy Prefect, encapsulando completamente a infraestrutura RBR. Nenhuma subclasse precisa reimplementar lógica — elas apenas fornecem defaults diferentes para os parâmetros do `__init__`.

Responsabilidades exclusivas de `BaseDeploy`:

- Receber e validar todos os parâmetros de configuração do deploy.
- Resolver automaticamente valores não fornecidos (entrypoint, parâmetros do flow) via introspecção.
- Expor o método `override()` tipado com `Generic[P]` para override de parâmetros com autocomplete.
- Construir os `job_variables` finais via hierarquia de merge com tratamento especial do `env`.
- Orquestrar a sequência de execução do `.deploy()`: prints de auditoria → prompts de confirmação → execução via Prefect.

---

### 5.2 `Generic[P]` e Tipagem

`BaseDeploy` é parametrizada pelo `ParamSpec` da função flow fornecida no `__init__`. Isso é o que permite ao método `override()` oferecer autocomplete com os parâmetros reais do flow.

```python
from typing import Any, Callable, Generic, ParamSpec

P = ParamSpec("P")

class BaseDeploy(Generic[P]):
    ...
```

O `P` é capturado implicitamente pelo Pylance no momento da instanciação, quando `flow_func: Callable[P, Any]` é passado. A partir daí, `self.override` é reconhecido como uma callable com a assinatura de `flow_func`, oferecendo autocomplete completo para os parâmetros do flow.

---

### 5.3 Construtor — Assinatura Completa

```python
def __init__(
    self,
    # --- Obrigatórios ---
    flow_func: Callable[P, Any],
    name: str,
    tags: list[str],

    # --- Source (override opcional) ---
    source_strategy: BaseSourceStrategy | None = None,
    github_url: str | None = None,
    branch: str | None = None,
    entrypoint: str | None = None,

    # --- Imagem Docker ---
    image: str = RBRDocker.DEFAULT_IMAGE,   # sobrescrito pelas subclasses

    # --- Work pool ---
    work_pool_name: str = RBRWorkPools.DEFAULT,

    # --- Parâmetros do flow ---
    # Não fornecido aqui diretamente — resolvido via override() ou defaults da função

    # --- job_variables customizados ---
    extra_job_variables: dict[str, Any] | None = None,
    job_variables_override: dict[str, Any] | None = None,

    # --- env customizado ---
    extra_env: dict[str, str] | None = None,
    env_override: dict[str, str] | None = None,

    # --- Concurrency (uso incomum — exige confirmação) ---
    concurrency_limit: int | None = None,
) -> None:
```

#### 5.3.1 Parâmetros Obrigatórios

| Parâmetro | Tipo | Descrição |
|---|---|---|
| `flow_func` | `Callable[P, Any]` | Função decorada com `@flow`. Base para introspecção de entrypoint, parâmetros e tipagem via `Generic[P]`. |
| `name` | `str` | Nome do deploy no Prefect. Pode ser sobrescrito no momento de chamar `.deploy(name=...)`. |
| `tags` | `list[str]` | Lista de tags para categorização no Prefect UI. Mínimo de uma tag obrigatório. Exemplos: `["BTG"]` para fluxos que automatizam a busca de dados no portal BTG; `["carteiras"]` para fluxos que automatizam a busca de carteiras diárias dos fundos de investimento. |

#### 5.3.2 Parâmetros de Source

| Parâmetro | Tipo | Default | Descrição |
|---|---|---|---|
| `source_strategy` | `BaseSourceStrategy \| None` | `None` | Instância completa de estratégia. Quando `None`, `GitHubSourceStrategy` é instanciada automaticamente. Override de nível 2 — uso excepcional. |
| `github_url` | `str \| None` | `None` | Override da URL do repositório GitHub. Quando fornecido, repassado para `GitHubSourceStrategy`. Quando `None`, detectado automaticamente via `git remote get-url origin`. |
| `branch` | `str \| None` | `None` | Override do branch. Quando `None`, detectado via `git rev-parse --abbrev-ref HEAD`. |
| `entrypoint` | `str \| None` | `None` | Override manual do entrypoint no formato `"caminho/flow.py:funcao"`. Quando `None`, calculado automaticamente por `source_strategy.resolve_entrypoint(flow_func)`. |

#### 5.3.3 Parâmetros de Infraestrutura

| Parâmetro | Tipo | Default | Descrição |
|---|---|---|---|
| `image` | `str` | `RBRDocker.DEFAULT_IMAGE` | Imagem Docker para execução do flow. Sobrescrito por `DefaultDeploy` e `ScrapeDeploy` com seus próprios defaults. |
| `work_pool_name` | `str` | `RBRWorkPools.DEFAULT` | Nome do work pool. Sobrescrever exige confirmação via prompt no terminal. |

#### 5.3.4 Parâmetros de Customização de `job_variables`

| Parâmetro | Tipo | Default | Descrição |
|---|---|---|---|
| `extra_job_variables` | `dict[str, Any] \| None` | `None` | Chaves adicionais merged sobre o dict base RBR. Permite adicionar ou sobrescrever chaves individuais sem descartar o restante. |
| `job_variables_override` | `dict[str, Any] \| None` | `None` | Substituição total do dict de `job_variables`. Ignora completamente a configuração base RBR. Uso excepcional — exige aviso no print de auditoria. |

#### 5.3.5 Parâmetros de Customização de `env`

| Parâmetro | Tipo | Default | Descrição |
|---|---|---|---|
| `extra_env` | `dict[str, str] \| None` | `None` | Variáveis de ambiente adicionais merged sobre o env base RBR. Nunca sobrescreve as variáveis RBR acidentalmente. |
| `env_override` | `dict[str, str] \| None` | `None` | Substituição total do dict `env`. Ignora inclusive as variáveis de ambiente base RBR. Exige aviso crítico no print de auditoria. |

#### 5.3.6 Parâmetro de Concorrência

| Parâmetro | Tipo | Default | Descrição |
|---|---|---|---|
| `concurrency_limit` | `int \| None` | `None` | Limite de execuções concorrentes do deploy. O work pool e queue já gerenciam concorrência — uso direto aqui é incomum. Quando fornecido, exige confirmação via prompt no terminal. |

---

### 5.4 Lógica de Inicialização

A sequência de operações dentro do `__init__` deve seguir esta ordem estrita:

```
1. Validar tags (mínimo uma obrigatória)
2. Validar mutualmente exclusivos: job_variables_override XOR extra_job_variables
3. Validar mutualmente exclusivos: env_override XOR extra_env
4. Prompt de confirmação se work_pool_name != RBRWorkPools.DEFAULT
5. Prompt de confirmação se concurrency_limit is not None
6. Instanciar source_strategy (GitHubSourceStrategy com github_url/branch se fornecidos)
7. Resolver entrypoint via source_strategy.resolve_entrypoint(flow_func) ou override
8. Resolver parameters defaults via inspect.signature(flow_func)
9. Armazenar todos os valores nos atributos de instância
```

Os prompts de confirmação (passos 4 e 5) ocorrem na construção — não no `.deploy()` — para que o dev veja os avisos antes de qualquer processamento adicional.

#### 5.4.1 Validação de Tags

```python
if not tags:
    raise ValueError(
        "Pelo menos uma tag é obrigatória. "
        "Exemplos: ['BTG'] para fluxos do portal BTG, "
        "['carteiras'] para fluxos de carteiras diárias."
    )
```

#### 5.4.2 Resolução de `parameters` via `inspect.signature`

Os parâmetros padrão do flow são extraídos automaticamente da assinatura da função. Apenas parâmetros com valor default são incluídos — parâmetros obrigatórios sem default não fazem sentido como `parameters` de deploy.

```python
import inspect

def _extract_default_parameters(self, flow_func: Callable) -> dict[str, Any]:
    sig = inspect.signature(flow_func)
    return {
        name: param.default
        for name, param in sig.parameters.items()
        if param.default is not inspect.Parameter.empty
    }
```

O resultado é armazenado em `self._parameters` e pode ser atualizado pelo dev via `self.parameters = self.override(...)`.

#### 5.4.3 Validação dos Parâmetros de Override

Quando o dev atribui `deploy.parameters = deploy.override(country_name="Argentina")`, a classe valida que todas as chaves fornecidas existem de fato na assinatura da função flow, prevenindo typos silenciosos:

```python
def _validate_parameter_keys(self, overrides: dict[str, Any]) -> None:
    sig = inspect.signature(self._flow_func)
    valid_keys = set(sig.parameters.keys())
    invalid_keys = set(overrides.keys()) - valid_keys
    if invalid_keys:
        raise ValueError(
            f"Parâmetros inválidos para o flow '{self._flow_func.__name__}': "
            f"{invalid_keys}. "
            f"Parâmetros válidos: {valid_keys}."
        )
```

---

### 5.5 Método `override()`

`override()` é o mecanismo central para que o dev sobrescreva os parâmetros padrão do flow com autocomplete completo no Pylance.

```python
def override(self, **kwargs: P.kwargs) -> dict[str, Any]:
    """
    Retorna um dicionário de parâmetros para sobrescrever os defaults
    do flow. Aceita exatamente os mesmos argumentos nomeados que a
    função flow, com autocomplete completo no Pylance.

    Uso:
        deploy.parameters = deploy.override(country_name="Argentina")

    Os parâmetros fornecidos são validados contra a assinatura real
    da função flow — typos geram ValueError imediatamente.
    """
    overrides = dict(**kwargs)
    self._validate_parameter_keys(overrides)
    return {**self._parameters, **overrides}
```

**Comportamento:** `override()` faz merge sobre os defaults já extraídos da função — não substitui o dict inteiro. Parâmetros não mencionados no `override()` mantêm seus valores default originais.

**Tipagem:** A assinatura `**kwargs: P.kwargs` é o que permite ao Pylance inferir os parâmetros válidos. O `P` capturado em `Generic[P]` na instanciação da classe propaga a tipagem para este método.

**Atribuição:** O resultado é atribuído via `deploy.parameters = deploy.override(...)`. O atributo `parameters` tem um setter que dispara `_validate_parameter_keys` adicionalmente:

```python
@property
def parameters(self) -> dict[str, Any]:
    return self._parameters

@parameters.setter
def parameters(self, value: dict[str, Any]) -> None:
    self._validate_parameter_keys(value)
    self._parameters = value
```

---

### 5.6 Resolução de `job_variables` — `_resolve_job_variables()`

```python
def _resolve_job_variables(self) -> dict[str, Any]:
    if self._job_variables_override is not None:
        # Bypass total — aviso já foi exibido no print de auditoria
        return self._job_variables_override

    base   = self._build_base_job_variables()     # invariante RBR — definido em BaseDeploy
    extras = self._build_extra_job_variables()    # extensões da subclasse (se houver)
    user   = self._extra_job_variables or {}      # adições do dev

    merged = {**base, **extras, **user}

    # env é sempre resolvido separadamente e injetado por último
    # para garantir que nunca seja sobrescrito por extra_job_variables
    merged["env"] = self._resolve_env()

    return merged
```

#### 5.6.1 `_build_base_job_variables()` — Invariante RBR

Constrói o dict base de `job_variables` que é aplicado a todos os deploys da RBR, sem exceção. Definido em `BaseDeploy` e nunca sobrescrito pelas subclasses.

```python
def _build_base_job_variables(self) -> dict[str, Any]:
    return {
        "volumes":            [RBRDocker.CERT_VOLUME],
        "auto_remove":        RBRJobVariables.AUTO_REMOVE,
        "image_pull_policy":  RBRJobVariables.IMAGE_PULL_POLICY,
    }
```

#### 5.6.2 `_build_extra_job_variables()` — Extensão das Subclasses

Hook para que subclasses adicionem `job_variables` específicos sem sobrescrever o base. Em `BaseDeploy`, retorna dict vazio. `ScrapeDeploy` pode sobrescrever se necessário.

```python
def _build_extra_job_variables(self) -> dict[str, Any]:
    return {}  # subclasses sobrescrevem se necessário
```

---

### 5.7 Resolução de `env` — `_resolve_env()`

O `env` dentro de `job_variables` recebe tratamento especial com três camadas de merge independentes. O merge superficial de `job_variables` seria insuficiente pois substituiria o dict `env` inteiro se o dev incluísse a chave `env` em `extra_job_variables`.

```python
def _resolve_env(self) -> dict[str, str]:
    if self._env_override is not None:
        # Bypass total inclusive do env base RBR
        # Aviso crítico já exibido no print de auditoria
        return self._env_override

    base      = self._build_base_env()        # variáveis RBR — definido em BaseDeploy
    subclass  = self._build_extra_env()       # variáveis específicas da subclasse
    user      = self._extra_env or {}         # variáveis adicionadas pelo dev

    return {**base, **subclass, **user}
```

**Hierarquia de precedência** (ordem crescente de prioridade): base RBR → subclasse → dev. O dev sempre vence, subclasse vence o base.

#### 5.7.1 `_build_base_env()` — Env Base RBR

Constrói as variáveis de ambiente invariantes da RBR que são injetadas em todos os containers de todos os deploys.

```python
def _build_base_env(self) -> dict[str, str]:
    return {
        "PREFECT_API_URL":             RBRPrefectServer.API_URL,
        "PREFECT_API_SSL_CERT_FILE":   RBRPrefectServer.SSL_CERT_PATH,
        "PREFECT_API_AUTH_STRING":     RBRBlocks.auth_string_template(),
        "PREFECT_CLIENT_CUSTOM_HEADERS": RBRBlocks.header_template(),
    }
```

#### 5.7.2 `_build_extra_env()` — Hook para Subclasses

Hook análogo ao de `job_variables`. Em `BaseDeploy`, retorna dict vazio. `ScrapeDeploy` sobrescreve para adicionar variáveis específicas do Playwright.

```python
def _build_extra_env(self) -> dict[str, str]:
    return {}  # subclasses sobrescrevem se necessário
```

---

### 5.8 Descrição Automática do Deploy

A descrição do deploy é gerada automaticamente a partir dos valores já resolvidos na construção, sem nenhum input adicional do dev. Inclui referência direta ao arquivo no GitHub.

```python
def _build_description(self) -> str:
    strategy = self._source_strategy
    file_path = self._entrypoint.split(":")[0]
    github_url = strategy.resolved_github_url.removesuffix(".git")
    branch = strategy.resolved_branch

    file_url = f"{github_url}/blob/{branch}/{file_path}"

    return (
        f"Flow: {self._flow_func.__name__}\n"
        f"Repositório: {strategy.resolved_github_url}\n"
        f"Branch: {branch}\n"
        f"Entrypoint: {self._entrypoint}\n"
        f"Arquivo: {file_url}\n"
        f"Pacote rbr-prefect: {importlib.metadata.version('rbr-prefect')}"
    )
```

A versão do pacote `rbr-prefect` é incluída na descrição para rastreabilidade — ao inspecionar um deploy no Prefect UI, é possível saber exatamente qual versão da lógica de deploy foi utilizada.

---

### 5.9 Atributos de Instância — Referência Completa

| Atributo | Tipo | Origem |
|---|---|---|
| `_flow_func` | `Callable[P, Any]` | Parâmetro `flow_func` |
| `_name` | `str` | Parâmetro `name` |
| `_tags` | `list[str]` | Parâmetro `tags` |
| `_image` | `str` | Parâmetro `image` |
| `_work_pool_name` | `str` | Parâmetro `work_pool_name` |
| `_source_strategy` | `BaseSourceStrategy` | Parâmetro `source_strategy` ou `GitHubSourceStrategy()` |
| `_entrypoint` | `str` | Parâmetro `entrypoint` ou `source_strategy.resolve_entrypoint(flow_func)` |
| `_parameters` | `dict[str, Any]` | Defaults de `inspect.signature(flow_func)` — atualizável via setter |
| `_extra_job_variables` | `dict[str, Any]` | Parâmetro `extra_job_variables` ou `{}` |
| `_job_variables_override` | `dict[str, Any] \| None` | Parâmetro `job_variables_override` |
| `_extra_env` | `dict[str, str]` | Parâmetro `extra_env` ou `{}` |
| `_env_override` | `dict[str, str] \| None` | Parâmetro `env_override` |
| `_concurrency_limit` | `int \| None` | Parâmetro `concurrency_limit` |
| `_schedule` | `Any \| None` | Definido via `.schedule()` — inicialmente `None` |

---

*Próxima seção: Seção 6 — `DefaultDeploy` e `ScrapeDeploy`*

---

## Seção 6 — `DefaultDeploy` e `ScrapeDeploy`

### 6.1 Princípio de Design das Subclasses

`DefaultDeploy` e `ScrapeDeploy` são intencionalmente simples. Todo o comportamento e lógica residem em `BaseDeploy`. As subclasses existem exclusivamente para:

1. Fornecer **defaults diferentes** para os parâmetros `image` e `work_pool_name` no `__init__`.
2. Sobrescrever os **hooks de extensão** `_build_extra_env()` e `_build_extra_job_variables()` quando a subclasse precisa de configurações adicionais além do base RBR.

Nenhuma subclasse deve reimplementar lógica já presente em `BaseDeploy`. Se uma necessidade de lógica surgir em uma subclasse, ela deve ser avaliada para elevação ao `BaseDeploy` como hook de extensão.

A diferença entre as duas subclasses é visível com clareza ao comparar seus construtores lado a lado — **apenas os valores default divergem**.

---

### 6.2 `DefaultDeploy`

Classe de deploy padrão para flows que utilizam a imagem oficial do Prefect. Não adiciona nenhuma variável de ambiente extra nem `job_variables` adicionais além do base RBR.

```python
class DefaultDeploy(BaseDeploy[P]):
    """
    Deploy padrão para flows da RBR.

    Utiliza a imagem oficial do Prefect (prefecthq/prefect:3-python3.12)
    e o work pool padrão. Adequado para flows de coleta de dados via HTTP,
    processamento, transformação e qualquer flow que não requeira um
    navegador headless ou dependências especiais além do Prefect.
    """

    def __init__(
        self,
        flow_func: Callable[P, Any],
        name: str,
        tags: list[str],
        source_strategy: BaseSourceStrategy | None = None,
        github_url: str | None = None,
        branch: str | None = None,
        entrypoint: str | None = None,
        image: str = RBRDocker.DEFAULT_IMAGE,
        work_pool_name: str = RBRWorkPools.DEFAULT,
        extra_job_variables: dict[str, Any] | None = None,
        job_variables_override: dict[str, Any] | None = None,
        extra_env: dict[str, str] | None = None,
        env_override: dict[str, str] | None = None,
        concurrency_limit: int | None = None,
    ) -> None:
        super().__init__(
            flow_func=flow_func,
            name=name,
            tags=tags,
            source_strategy=source_strategy,
            github_url=github_url,
            branch=branch,
            entrypoint=entrypoint,
            image=image,
            work_pool_name=work_pool_name,
            extra_job_variables=extra_job_variables,
            job_variables_override=job_variables_override,
            extra_env=extra_env,
            env_override=env_override,
            concurrency_limit=concurrency_limit,
        )
```

#### 6.2.1 O que `DefaultDeploy` **não** sobrescreve

| Hook / Método | Comportamento herdado de `BaseDeploy` |
|---|---|
| `_build_extra_env()` | Retorna `{}` — nenhuma variável de ambiente adicional |
| `_build_extra_job_variables()` | Retorna `{}` — nenhum `job_variable` adicional |
| `_resolve_job_variables()` | Herdado integralmente |
| `_resolve_env()` | Herdado integralmente |
| `.override()` | Herdado integralmente |
| `.schedule()` | Herdado integralmente |
| `.deploy()` | Herdado integralmente |

`DefaultDeploy` é essencialmente um alias tipado de `BaseDeploy` com defaults explicitamente declarados. O valor de tê-la como subclasse separada — e não usar `BaseDeploy` diretamente — é semântico e de descoberta: o dev lê `DefaultDeploy` no código e entende imediatamente o contexto de uso, sem precisar consultar os defaults de `BaseDeploy`.

---

### 6.3 `ScrapeDeploy`

Classe de deploy para flows que utilizam Playwright para automação de navegador. Diferencia-se de `DefaultDeploy` em dois aspectos: usa a imagem customizada da RBR com Playwright instalado e injeta variáveis de ambiente específicas do Playwright no container via `_build_extra_env()`.

```python
class ScrapeDeploy(BaseDeploy[P]):
    """
    Deploy para flows de scraping que utilizam Playwright.

    Utiliza a imagem customizada da RBR baseada no Prefect com Playwright
    para Python 3.12 pré-instalado. Injeta automaticamente as variáveis
    de ambiente necessárias para o funcionamento do Playwright em ambiente
    containerizado (sem display, modo headless).

    Adequado para flows que automatizam interações com portais web como
    BTG, XP, ou qualquer sistema que requeira um navegador headless.
    """

    def __init__(
        self,
        flow_func: Callable[P, Any],
        name: str,
        tags: list[str],
        source_strategy: BaseSourceStrategy | None = None,
        github_url: str | None = None,
        branch: str | None = None,
        entrypoint: str | None = None,
        image: str = RBRDocker.SCRAPE_IMAGE,        # ← default diferente
        work_pool_name: str = RBRWorkPools.DEFAULT,
        extra_job_variables: dict[str, Any] | None = None,
        job_variables_override: dict[str, Any] | None = None,
        extra_env: dict[str, str] | None = None,
        env_override: dict[str, str] | None = None,
        concurrency_limit: int | None = None,
    ) -> None:
        super().__init__(
            flow_func=flow_func,
            name=name,
            tags=tags,
            source_strategy=source_strategy,
            github_url=github_url,
            branch=branch,
            entrypoint=entrypoint,
            image=image,
            work_pool_name=work_pool_name,
            extra_job_variables=extra_job_variables,
            job_variables_override=job_variables_override,
            extra_env=extra_env,
            env_override=env_override,
            concurrency_limit=concurrency_limit,
        )
```

#### 6.3.1 `_build_extra_env()` — Variáveis do Playwright

`ScrapeDeploy` sobrescreve o hook `_build_extra_env()` para injetar as variáveis de ambiente necessárias ao Playwright em ambiente containerizado. O dev que usa `ScrapeDeploy` não precisa conhecer nem fornecer essas variáveis — elas são parte da responsabilidade da classe.

```python
def _build_extra_env(self) -> dict[str, str]:
    return {
        "PLAYWRIGHT_BROWSERS_PATH": RBRDocker.PLAYWRIGHT_BROWSERS_PATH,
        "DISPLAY":                  RBRDocker.PLAYWRIGHT_DISPLAY,
    }
```

As constantes correspondentes devem ser adicionadas em `RBRDocker` em `constants.py`:

```python
class RBRDocker:
    ...
    PLAYWRIGHT_BROWSERS_PATH = "/ms-playwright"
    PLAYWRIGHT_DISPLAY       = ""           # display vazio — modo headless
```

**Observação:** Os valores exatos de `PLAYWRIGHT_BROWSERS_PATH` e `PLAYWRIGHT_DISPLAY` dependem de como a imagem `rbr-custom/prefect-playwright:3-python3.12` foi construída. Eles devem ser validados contra o `Dockerfile` da imagem customizada e atualizados em `constants.py` caso a estrutura da imagem mude.

#### 6.3.2 O que `ScrapeDeploy` **não** sobrescreve

| Hook / Método | Comportamento herdado de `BaseDeploy` |
|---|---|
| `_build_extra_job_variables()` | Retorna `{}` — nenhum `job_variable` adicional além do base RBR |
| `_resolve_job_variables()` | Herdado integralmente |
| `_resolve_env()` | Herdado integralmente — chama `_build_extra_env()` via polimorfismo |
| `.override()` | Herdado integralmente |
| `.schedule()` | Herdado integralmente |
| `.deploy()` | Herdado integralmente |

---

### 6.4 Comparativo entre as Subclasses

| Aspecto | `DefaultDeploy` | `ScrapeDeploy` |
|---|---|---|
| `image` default | `RBRDocker.DEFAULT_IMAGE` | `RBRDocker.SCRAPE_IMAGE` |
| `work_pool_name` default | `RBRWorkPools.DEFAULT` | `RBRWorkPools.DEFAULT` |
| `_build_extra_env()` | `{}` | Variáveis do Playwright |
| `_build_extra_job_variables()` | `{}` | `{}` |
| Caso de uso | Flows HTTP, processamento, transformação | Flows com Playwright / automação de navegador |

---

### 6.5 Exemplo de Uso Comparativo

```python
# DefaultDeploy — flow de coleta de dados via API REST
from rbr_prefect import DefaultDeploy
from flows.country_flow import country_flow

deploy = DefaultDeploy(
    flow_func=country_flow,
    name="country-flow-prod",
    tags=["dados-externos", "rest-api"],
)
deploy.parameters = deploy.override(country_name="Brazil")
deploy.deploy()


# ScrapeDeploy — flow de scraping no portal BTG
from rbr_prefect import ScrapeDeploy
from flows.btg_scraper import btg_scraper_flow

deploy = ScrapeDeploy(
    flow_func=btg_scraper_flow,
    name="btg-scraper-prod",
    tags=["BTG", "scraping"],
)
deploy.deploy()
```

---

### 6.6 Adição de Futuras Subclasses

O padrão estabelecido por `DefaultDeploy` e `ScrapeDeploy` define como qualquer futura subclasse deve ser criada:

1. Herdar de `BaseDeploy[P]`.
2. Replicar a assinatura completa do `__init__`, alterando apenas os **valores default** dos parâmetros que divergem.
3. Delegar integralmente para `super().__init__()`.
4. Sobrescrever `_build_extra_env()` e/ou `_build_extra_job_variables()` se a subclasse precisar de configurações adicionais.
5. **Nunca** reimplementar lógica já presente em `BaseDeploy`.

Exemplos de subclasses que poderiam ser criadas no futuro seguindo este padrão: `DBTDeploy` para flows de transformação com dbt, `SparkDeploy` para flows com PySpark, `DockerDeploy` utilizando a `DockerSourceStrategy` quando implementada.

---

*Próxima seção: Seção 7 — Builder Pattern: `.schedule()` e `.deploy()`*

---

## Seção 7 — Builder Pattern: `.schedule()` e `.deploy()`

### 7.1 Papel dos Métodos no Design Geral

O builder pattern com encadeamento de métodos é aplicado aos dois momentos que ocorrem **após** a construção do objeto:

- `.schedule()` — configura a agenda de execução automática do flow. Retorna `self` para permitir encadeamento. Não tem efeitos colaterais.
- `.deploy()` — único método com efeitos colaterais de todo o pacote. Orquestra prints de auditoria, prompts de confirmação e executa o deploy via API do Prefect.

O `.schedule()` é opcional. O `.deploy()` é sempre o passo final e obrigatório.

---

### 7.2 Método `.schedule()`

#### 7.2.1 Assinatura

```python
def schedule(
    self,
    cron: Any | None = None,
    *,
    interval: datetime.timedelta | None = None,
    rrule: str | None = None,
) -> "BaseDeploy[P]":
    """
    Configura a agenda de execução automática do flow.

    Parâmetros
    ----------
    cron:
        Expressão de agendamento construída com o pacote `cronexpressions`.
        Interface principal e recomendada para agendamentos regulares.
        Exemplo: every().weekday.at("09:00")

    interval:
        Intervalo de execução como timedelta. Configuração avançada —
        exige confirmação via prompt no terminal.
        Exemplo: datetime.timedelta(hours=6)

    rrule:
        String no formato iCalendar RRULE. Configuração avançada —
        exige confirmação via prompt no terminal.
        Exemplo: "FREQ=WEEKLY;BYDAY=MO,WE,FR"

    Retorna
    -------
    self — permite encadeamento com .deploy().

    Restrição
    ---------
    Apenas um dos três parâmetros pode ser fornecido por chamada.
    Fornecer mais de um levanta ValueError imediatamente.
    """
```

#### 7.2.2 Validação de Exclusividade Mútua

```python
    provided = sum([
        cron     is not None,
        interval is not None,
        rrule    is not None,
    ])
    if provided == 0:
        raise ValueError(
            "É necessário fornecer exatamente um dos parâmetros: "
            "cron, interval ou rrule."
        )
    if provided > 1:
        raise ValueError(
            "Apenas um parâmetro de agendamento pode ser fornecido por vez: "
            "cron, interval ou rrule são mutuamente exclusivos."
        )
```

#### 7.2.3 Prompt de Confirmação para Configurações Avançadas

`interval` e `rrule` são considerados configurações avançadas. Quando fornecidos, um prompt de confirmação é exibido no terminal antes de prosseguir:

```python
    if interval is not None or rrule is not None:
        confirmed = confirm_advanced_schedule()  # _cli/ui.py
        if not confirmed:
            raise SystemExit(ScheduleMessages.ADVANCED_ABORTED)
```

O `cron` via `cronexpressions` não exige confirmação — é a interface padrão e recomendada.

#### 7.2.4 Integração com `cronexpressions`

O pacote `cronexpressions` fornece uma DSL legível para construção de expressões cron, eliminando strings cron cruas como `"0 9 * * 1-5"`. O dev constrói a expressão usando a API do pacote, e `.schedule()` recebe o objeto resultante.

O objeto gerado pelo `cronexpressions` é convertido para a string cron que o Prefect espera via `.expression` ou equivalente — verificar a API exata do pacote na versão especificada em `pyproject.toml`.

Exemplos de uso com `cronexpressions`:

```python
from cronexpressions import every

# Todo dia útil às 09:00
deploy.schedule(cron=every().weekday.at("09:00"))

# Todo dia às 06:30
deploy.schedule(cron=every().day.at("06:30"))

# A cada hora
deploy.schedule(cron=every().hour)

# Toda segunda-feira às 08:00
deploy.schedule(cron=every().monday.at("08:00"))
```

Internamente, `.schedule()` extrai a string cron do objeto `cronexpressions` e constrói o objeto `CronSchedule` do Prefect:

```python
    if cron is not None:
        from prefect.schedules import CronSchedule
        cron_string = str(cron)   # ou cron.expression — validar com a API do pacote
        self._schedule = CronSchedule(cron=cron_string)
```

#### 7.2.5 Configurações de `interval` e `rrule`

```python
    if interval is not None:
        from prefect.schedules import IntervalSchedule
        self._schedule = IntervalSchedule(interval=interval)

    if rrule is not None:
        from prefect.schedules import RRuleSchedule
        self._schedule = RRuleSchedule(rrule=rrule)
```

#### 7.2.6 Retorno para Encadeamento

```python
    return self
```

O retorno de `self` é o que habilita o encadeamento fluente:

```python
(
    DefaultDeploy(flow_func=country_flow, name="country-flow-prod", tags=["dados-externos"])
    .schedule(cron=every().weekday.at("09:00"))
    .deploy()
)
```

---

### 7.3 Método `.deploy()`

#### 7.3.1 Assinatura

```python
def deploy(self, name: str | None = None) -> None:
    """
    Executa o deploy do flow no servidor Prefect da RBR.

    Este é o único método com efeitos colaterais do pacote.
    Nenhuma chamada de rede ocorre antes deste método ser invocado.

    Sequência de execução:
    1. Exibe resumo de valores resolvidos automaticamente (auditoria)
    2. Exibe overrides aplicados pelo dev (se houver)
    3. Exibe aviso se job_variables_override ou env_override foram usados
    4. Exibe separador visual de passagem de responsabilidade
    5. Chama flow_func.from_source(...).deploy(...)
       → A partir deste ponto o Prefect owns o terminal

    Parâmetros
    ----------
    name:
        Override opcional do nome do deploy. Quando fornecido, sobrescreve
        o `name` definido na construção. Útil para deployar o mesmo flow
        em múltiplos ambientes a partir da mesma instância.
    """
```

#### 7.3.2 Sequência Interna de Execução

A ordem das operações dentro de `.deploy()` é estrita e não deve ser alterada. Toda interação com o terminal deve estar concluída antes de `deployable.deploy()` ser invocado.

```
Fase 1 — rbr-prefect owns o terminal
│
├── 1. _log_resolved_values()
│       Exibe valores resolvidos automaticamente:
│       github_url, branch, entrypoint, parameters (defaults da função)
│
├── 2. _log_overrides()
│       Exibe overrides aplicados pelo dev (parameters, extra_env,
│       extra_job_variables) — omitido se nenhum override foi fornecido
│
├── 3. _log_warnings()
│       Exibe avisos críticos se job_variables_override ou env_override
│       foram utilizados (bypass das configurações base RBR)
│
├── 4. _log_env_resolved()
│       Exibe o dict env final após merge das três camadas
│
├── 5. _log_handoff()
│       Exibe o separador visual de passagem de responsabilidade:
│       "[rbr-prefect] ✓ Configuração validada. Passando para o Prefect..."
│       seguido de uma rich.rule horizontal
│
│  ← Linha divisória: nenhuma interação com o terminal após este ponto
│
Fase 2 — Prefect owns o terminal
│
├── 6. Construção do deployable via from_source
│       deployable = flow_func.from_source(
│           source=source_strategy.build(),
│           entrypoint=self._entrypoint,
│       )
│
└── 7. Execução do deploy via API do Prefect
        deployable.deploy(
            name=name or self._name,
            work_pool_name=self._work_pool_name,
            image=self._image,
            build=False,
            push=False,
            job_variables=self._resolve_job_variables(),
            parameters=self._parameters,
            description=self._build_description(),
            tags=self._tags,
            schedules=[self._schedule] if self._schedule else [],
            concurrency_limit=self._concurrency_limit,
        )
```

#### 7.3.3 Print de Auditoria — Detalhamento

O print de auditoria exibido antes do deploy é formatado com `rich` e organizado em seções claras. Cada valor resolvido automaticamente é identificado explicitamente para que o dev possa verificar que a detecção automática produziu o resultado esperado.

**Formato do resumo:**

```
┌─────────────────────────────────────────────────────────┐
│  rbr-prefect — Resumo do Deploy                         │
├─────────────────────────────────────────────────────────┤
│  Valores resolvidos automaticamente                     │
│    → github_url  : https://github.com/RBR/.../repo.git  │
│    → branch      : main                                 │
│    → entrypoint  : flows/country_flow.py:country_flow   │
│    → parameters  : {"country_name": "Brazil"}           │
│                                                         │
│  Configuração do deploy                                 │
│    → name        : country-flow-prod                    │
│    → image       : prefecthq/prefect:3-python3.12       │
│    → work_pool   : default                              │
│    → tags        : ["dados-externos", "rest-api"]       │
│    → schedule    : weekdays at 09:00                    │
│                                                         │
│  Env resolvido (merged)                                 │
│    → PREFECT_API_URL             : https://...          │
│    → PREFECT_API_SSL_CERT_FILE   : /host-certs/...      │
│    → PREFECT_API_AUTH_STRING     : {{ prefect.blocks... │
│    → PREFECT_CLIENT_CUSTOM_HEADERS: {{ prefect.blocks...│
└─────────────────────────────────────────────────────────┘
```

Se `parameters` foram sobrescritos via `deploy.parameters = deploy.override(...)`, uma seção adicional é exibida:

```
│  Overrides aplicados                                    │
│    → parameters  : {"country_name": "Argentina"}        │
```

Se `job_variables_override` ou `env_override` foram utilizados, um painel de aviso em vermelho é exibido:

```
┌─────────────────────────────────────────────────────────┐
│  ⚠  ATENÇÃO                                             │
│  job_variables_override aplicado — configuração base    │
│  RBR completamente ignorada.                            │
└─────────────────────────────────────────────────────────┘
```

#### 7.3.4 Separador de Passagem de Responsabilidade

Imediatamente antes de invocar `flow_func.from_source()`, o separador visual é exibido. Este é o último output do pacote `rbr-prefect` — tudo que vem depois é do Prefect.

```python
    console.print(DeployMessages.HANDOFF_MESSAGE)  # "✓ Configuração validada. Passando para o Prefect..."
    console.rule(style="dim")
```

A ausência de limpeza de terminal entre o output do `rbr-prefect` e o do Prefect é **intencional** — o dev vê o histórico completo da sessão em sequência.

#### 7.3.5 `build=False` e `push=False`

Os parâmetros `build=False` e `push=False` são sempre passados ao `.deploy()` do Prefect. A responsabilidade de build e push da imagem Docker é externa ao pacote — as imagens são gerenciadas independentemente no registry da RBR. O pacote assume que a imagem já está disponível no registry e apenas referencia seu nome.

---

### 7.4 Padrões de Uso do Builder

#### Uso mínimo absoluto

```python
DefaultDeploy(
    flow_func=country_flow,
    name="country-flow-prod",
    tags=["dados-externos"],
).deploy()
```

#### Com schedule encadeado

```python
from cronexpressions import every

(
    DefaultDeploy(
        flow_func=country_flow,
        name="country-flow-prod",
        tags=["dados-externos"],
    )
    .schedule(cron=every().weekday.at("09:00"))
    .deploy()
)
```

#### Com override de parâmetros e schedule

```python
from cronexpressions import every

deploy = DefaultDeploy(
    flow_func=country_flow,
    name="country-flow-prod",
    tags=["BTG", "dados-externos"],
)
deploy.parameters = deploy.override(country_name="Argentina")
deploy.schedule(cron=every().day.at("06:30"))
deploy.deploy()
```

#### Com override do nome no deploy (multi-ambiente)

```python
deploy = DefaultDeploy(
    flow_func=country_flow,
    name="country-flow",
    tags=["dados-externos"],
)

# Deploy para produção
deploy.deploy(name="country-flow-prod")

# Reutiliza a mesma instância para staging
deploy.deploy(name="country-flow-staging")
```

---

### 7.5 Invariante de Efeitos Colaterais

O contrato fundamental do pacote é que **apenas `.deploy()` tem efeitos colaterais**. Isso implica:

- A construção do objeto (`__init__`) nunca faz chamadas de rede, exceto pelos prompts de confirmação via terminal que são interações locais.
- `.schedule()` nunca faz chamadas de rede — apenas armazena o objeto de schedule em `self._schedule`.
- `GitHubCredentials.load()` é chamado apenas dentro de `.deploy()`, quando `source_strategy.build()` é invocado.
- Todos os métodos de resolução (`_resolve_env`, `_resolve_job_variables`, `_build_description`) são chamados dentro de `.deploy()` — não na construção.

Esta separação garante que instâncias de `BaseDeploy` podem ser criadas, inspecionadas e testadas sem efeitos colaterais, e que o ponto exato de execução é sempre claro e explícito no código do dev.

---

*Próxima seção: Seção 8 — `__init__.py` e superfície pública*

---

## Seção 8 — `__init__.py` e Superfície Pública

### 8.1 Princípio de Design da Superfície Pública

A superfície pública do pacote é o conjunto de nomes que o dev pode importar diretamente de `rbr_prefect`. Ela deve ser **mínima, explícita e estável** — qualquer nome exportado publicamente é um contrato que não pode ser removido ou renomeado sem uma major version bump.

Dois níveis de acesso são deliberadamente diferenciados:

- **Acesso direto** — classes de deploy disponíveis no topo do pacote via `from rbr_prefect import ...`. Zero fricção para o caso de uso principal.
- **Acesso por submódulo** — constantes disponíveis via `from rbr_prefect.constants import ...`. O dev precisa de um import explícito adicional, o que comunica que está saindo do fluxo principal e acessando detalhes de infraestrutura.

Tudo que não estiver explicitamente exportado é considerado privado — detalhe de implementação sujeito a mudança sem aviso.

---

### 8.2 `rbr_prefect/__init__.py` — Topo do Pacote

Este arquivo controla o que fica disponível quando o dev faz `from rbr_prefect import ...` ou `import rbr_prefect`.

```python
"""
rbr-prefect — Utilitário de deploy de flows Prefect para a RBR Asset Management.

Uso básico:
    from rbr_prefect import DefaultDeploy, ScrapeDeploy

Para referenciar constantes de infraestrutura:
    from rbr_prefect.constants import RBRDocker, RBRWorkPools
"""

from rbr_prefect.deploy import DefaultDeploy, ScrapeDeploy

__version__ = "0.1.0"

__all__ = [
    "DefaultDeploy",
    "ScrapeDeploy",
    "__version__",
]
```

#### 8.2.1 O que é exportado diretamente

| Nome | Tipo | Justificativa |
|---|---|---|
| `DefaultDeploy` | Classe | Ponto de entrada principal — todo dev usa |
| `ScrapeDeploy` | Classe | Ponto de entrada para flows de scraping |
| `__version__` | `str` | Convenção de pacotes Python — permite verificar versão instalada em runtime |

#### 8.2.2 O que **não** é exportado diretamente

| Nome | Razão da exclusão |
|---|---|
| `BaseDeploy` | Classe base interna — devs não a instanciam diretamente |
| `BaseSourceStrategy` | Abstração interna — não faz parte do fluxo normal de uso |
| `GitHubSourceStrategy` | Detalhe de implementação — acessível via `source_strategy` override quando necessário, mas não exportado no topo |
| `DockerSourceStrategy` | Não implementado — não deve ser exposto até estar funcional |
| Qualquer classe de `constants.py` | Acessível via submódulo `rbr_prefect.constants` |
| Qualquer função de `_cli/` | Totalmente privado — prefixo `_` no nome do submódulo sinaliza isso |

**Observação sobre `BaseDeploy` e `GitHubSourceStrategy`:** Embora não exportadas no topo, elas não precisam estar em `__all__` para serem importáveis diretamente quando o dev precisar. Um dev avançado pode fazer `from rbr_prefect.deploy import BaseDeploy` para criar uma subclasse customizada — isso é deliberadamente possível mas não anunciado na superfície principal.

---

### 8.3 `rbr_prefect/constants.py` — Acesso por Submódulo

As constantes não são reexportadas em `rbr_prefect/__init__.py`. O dev acessa o módulo de constantes com um import explícito:

```python
from rbr_prefect.constants import RBRDocker, RBRWorkPools, RBRPrefectServer, RBRBlocks, RBRJobVariables
```

Ou importando o módulo inteiro:

```python
from rbr_prefect import constants
constants.RBRDocker.DEFAULT_IMAGE
```

Esta separação é intencional. Quando um dev importa uma constante, ele está tomando uma decisão consciente de referenciar um valor de infraestrutura — geralmente para fazer um override explícito em um deploy. O import adicional torna essa intenção visível no código:

```python
from rbr_prefect import DefaultDeploy
from rbr_prefect.constants import RBRWorkPools

# A referência à constante comunica que este deploy usa um work pool não-padrão
deploy = DefaultDeploy(
    flow_func=my_flow,
    name="my-flow",
    tags=["dados-externos"],
    work_pool_name=RBRWorkPools.DEFAULT,  # explícito e auditável
)
```

#### 8.3.1 `constants.py` não tem seu próprio `__all__`

Todas as classes de constantes são públicas dentro do módulo. O dev pode importar qualquer uma delas. Não há necessidade de `__all__` em `constants.py` — a convenção `RBR<Domínio>` já comunica que são constantes de infraestrutura e não detalhes de implementação.

---

### 8.4 `rbr_prefect/_cli/__init__.py` — Submódulo Totalmente Privado

O submódulo `_cli` é totalmente privado. O prefixo `_` no nome do diretório é a sinalização convencional em Python de que o conteúdo não faz parte da API pública.

```python
# rbr_prefect/_cli/__init__.py
# Expõe apenas as funções de alto nível que deploy.py precisa consumir.
# Nenhuma função deste módulo é parte da API pública do pacote.

from rbr_prefect._cli.ui import (
    print_deploy_summary,
    print_overrides,
    print_critical_warning,
    print_env_resolved,
    print_handoff,
    confirm_work_pool_override,
    confirm_concurrency_limit,
    confirm_advanced_schedule,
)
```

`deploy.py` importa de `rbr_prefect._cli` — não diretamente de `rbr_prefect._cli.ui` ou `rbr_prefect._cli.messages`. O `__init__.py` do submódulo é a única interface que `deploy.py` enxerga, isolando completamente a estrutura interna do submódulo de seus consumidores.

---

### 8.5 Mapa Completo de Imports Válidos

A tabela abaixo documenta todos os imports válidos e inválidos do pacote para referência dos devs e do Claude Code durante a implementação:

| Import | Válido? | Caso de uso |
|---|---|---|
| `from rbr_prefect import DefaultDeploy` | ✅ | Uso padrão |
| `from rbr_prefect import ScrapeDeploy` | ✅ | Uso padrão para scraping |
| `from rbr_prefect import __version__` | ✅ | Verificação de versão em runtime |
| `from rbr_prefect.constants import RBRDocker` | ✅ | Override de imagem |
| `from rbr_prefect.constants import RBRWorkPools` | ✅ | Override de work pool |
| `from rbr_prefect.constants import RBRPrefectServer` | ✅ | Referência à URL da API |
| `from rbr_prefect.constants import RBRBlocks` | ✅ | Referência a nomes de blocks |
| `from rbr_prefect.constants import RBRJobVariables` | ✅ | Referência a defaults de job variables |
| `from rbr_prefect.deploy import BaseDeploy` | ✅ (avançado) | Criação de subclasse customizada |
| `from rbr_prefect.deploy import GitHubSourceStrategy` | ✅ (avançado) | Override de source strategy |
| `from rbr_prefect._cli import ...` | ⛔ | Privado — não usar externamente |
| `from rbr_prefect._cli.ui import ...` | ⛔ | Privado — não usar externamente |
| `from rbr_prefect._cli.messages import ...` | ⛔ | Privado — não usar externamente |

---

### 8.6 Verificação de Versão em Runtime

A constante `__version__` em `__init__.py` é sincronizada com o `pyproject.toml` via `bump2version` (configurado na Seção 1). Adicionalmente, a versão pode ser acessada via `importlib.metadata` sem importar o pacote diretamente — padrão utilizado em `_build_description()` de `BaseDeploy`:

```python
import importlib.metadata

version = importlib.metadata.version("rbr-prefect")
```

As duas formas de acesso devem sempre retornar o mesmo valor. A sincronização é garantida pela configuração do `bump2version` que atualiza ambos os arquivos simultaneamente.

---

*Próxima seção: Seção 9 — Distribuição e Versionamento*

---

## Seção 9 — Distribuição e Versionamento

### 9.1 Visão Geral

O processo de publicação de novas versões do pacote é inteiramente local e manual — sem pipelines de CI/CD, sem triggers automáticos por push ou merge. Um mantenedor autorizado executa uma sequência de três comandos na sua máquina para bumpar a versão, construir os artifacts e publicar no PyPI.

Esta decisão é intencional: o pacote `rbr-prefect` é de infraestrutura interna e suas releases são pouco frequentes e deliberadas. A complexidade de um pipeline de CI/CD não se justifica para esse volume de releases.

---

### 9.2 Ferramentas Utilizadas

| Ferramenta | Papel | Instalação |
|---|---|---|
| `bump2version` | Atualiza a versão sincronizadamente em `pyproject.toml` e `rbr_prefect/__init__.py`, cria commit Git e tag automaticamente | `uv add --dev bump2version` |
| `uv build` | Constrói os artifacts de distribuição (`.whl` e `.tar.gz`) na pasta `dist/` | Nativo do `uv` |
| `uv publish` | Publica os artifacts em `dist/` no PyPI usando as credenciais configuradas localmente | Nativo do `uv` |

---

### 9.3 Configuração do `bump2version`

A configuração do `bump2version` reside no `pyproject.toml` (já detalhada na Seção 1). O comportamento configurado é:

- Ao executar `bump2version <parte>`, a versão é atualizada em dois arquivos simultaneamente: `pyproject.toml` e `rbr_prefect/__init__.py`.
- Um commit Git é criado automaticamente com a mensagem `Bump version: X.Y.Z → X.Y.Z+1`.
- Uma tag Git é criada automaticamente no formato `vX.Y.Z`.
- O commit e a tag devem ser pushed manualmente ao repositório após o bump.

#### 9.3.1 Arquivo `.bumpversion.cfg` — alternativa ao `pyproject.toml`

Caso a configuração do `bump2version` no `pyproject.toml` cause conflitos com outras ferramentas, ela pode ser extraída para um arquivo `.bumpversion.cfg` na raiz do repositório:

```ini
[bumpversion]
current_version = 0.1.0
commit = True
tag = True

[bumpversion:file:pyproject.toml]
search = version = "{current_version}"
replace = version = "{new_version}"

[bumpversion:file:rbr_prefect/__init__.py]
search = __version__ = "{current_version}"
replace = __version__ = "{new_version}"
```

A configuração no `pyproject.toml` é preferida por manter tudo em um único arquivo, mas o `.bumpversion.cfg` é igualmente válido.

---

### 9.4 Configuração de Credenciais do PyPI

As credenciais de publicação são configuradas **localmente na máquina do mantenedor** — nunca no repositório. Existem duas formas equivalentes:

**Via variável de ambiente (recomendada para uso pontual):**

```bash
export UV_PUBLISH_TOKEN="pypi-xxxxxxxxxxxxxxxxxxxx"
uv publish
```

**Via arquivo de configuração `~/.pypirc` (recomendada para uso recorrente):**

```ini
[distutils]
index-servers = pypi

[pypi]
username = __token__
password = pypi-xxxxxxxxxxxxxxxxxxxx
```

O token PyPI deve ter escopo restrito ao projeto `rbr-prefect` — nunca usar um token com permissões globais de conta.

---

### 9.5 Fluxo Completo de Release

A sequência completa de uma release, executada localmente pelo mantenedor:

```bash
# 1. Garantir que o branch main está limpo e atualizado
git checkout main
git pull origin main
git status  # deve estar limpo — sem arquivos modificados

# 2. Executar os testes antes de qualquer bump
uv run pytest

# 3. Bumpar a versão
#    Escolher: patch (0.1.0 → 0.1.1) | minor (0.1.0 → 0.2.0) | major (0.1.0 → 1.0.0)
bump2version patch

# O bump2version automaticamente:
#   - Atualiza a versão em pyproject.toml e rbr_prefect/__init__.py
#   - Cria o commit: "Bump version: 0.1.0 → 0.1.1"
#   - Cria a tag: "v0.1.1"

# 4. Push do commit e da tag para o repositório
git push origin main
git push origin --tags

# 5. Limpar artifacts anteriores (boa prática)
rm -rf dist/

# 6. Construir os artifacts de distribuição
uv build

# Resultado em dist/:
#   rbr_prefect-0.1.1-py3-none-any.whl
#   rbr_prefect-0.1.1.tar.gz

# 7. Verificar o conteúdo do wheel antes de publicar (opcional mas recomendado)
uv run python -m zipfile -l dist/rbr_prefect-0.1.1-py3-none-any.whl

# 8. Publicar no PyPI
uv publish
```

---

### 9.6 Critérios para Escolha da Parte da Versão

O pacote segue [Semantic Versioning](https://semver.org/) estritamente:

| Tipo de mudança | Parte a bumpar | Exemplo |
|---|---|---|
| Correção de bug sem impacto na interface pública | `patch` | `0.1.0 → 0.1.1` |
| Nova funcionalidade compatível com versões anteriores (nova subclasse, novo parâmetro opcional) | `minor` | `0.1.0 → 0.2.0` |
| Mudança que quebra compatibilidade (renomear classe, remover parâmetro, alterar comportamento de método existente) | `major` | `0.1.0 → 1.0.0` |
| Atualização de constante de infraestrutura (nova URL, nova imagem) sem mudança de interface | `patch` | `0.1.0 → 0.1.1` |

**Atenção especial:** Mudanças em `constants.py` que alterem valores de configuração (ex: nova URL da API, novo nome de block) são `patch` apenas se a interface das classes de deploy não mudar. Se a mudança exigir que devs atualizem seus `deploy.py`, deve ser `minor` com nota no changelog.

---

### 9.7 `CHANGELOG.md`

O repositório deve manter um `CHANGELOG.md` na raiz seguindo o formato [Keep a Changelog](https://keepachangelog.com/)

```txt
# Changelog

## [Unreleased]

## [0.1.1] - 2025-XX-XX
### Fixed
- Descrição do fix

## [0.1.0] - 2025-XX-XX
### Added
- Release inicial
- DefaultDeploy com detecção automática de repositório Git
- ScrapeDeploy com suporte a Playwright
- Integração com cronexpressions para agendamento
```

A atualização do `CHANGELOG.md` deve ser feita **antes** do `bump2version` — o bump deve incluir o changelog atualizado no mesmo commit.

---

### 9.8 Verificação Pós-Publicação

Após o `uv publish`, verificar que a nova versão está disponível:

```bash
# Verificar no PyPI (pode levar alguns segundos para propagar)
pip index versions rbr-prefect

# Instalar a nova versão em ambiente limpo para smoke test
pip install rbr-prefect==0.1.1
python -c "import rbr_prefect; print(rbr_prefect.__version__)"
```

---

### 9.9 Instalação pelos Devs

Após a publicação, os devs adicionam o pacote aos seus projetos normalmente:

```bash
# Com uv (recomendado — mesmo toolchain do pacote)
uv add rbr-prefect

# Com pip
pip install rbr-prefect

# Fixar versão mínima no pyproject.toml do projeto de flow
# (recomendado para garantir reproducibilidade)
dependencies = [
    "prefect>=3.0.0",
    "rbr-prefect>=0.1.0",
]
```

---

*Próxima seção: Seção 10 — `TESTING.md`*

---

