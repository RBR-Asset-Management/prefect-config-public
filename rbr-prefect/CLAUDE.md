# CLAUDE.md — Guia de Implementação para Agente IA

Este arquivo orienta o agente IA na implementação do pacote `rbr-prefect`. Leia-o integralmente antes de qualquer modificação no código.

---

## Documentos de Referência Obrigatória

Os três documentos de referência residem na pasta `.instructions/` na raiz do repositório:

```
rbr-prefect/
└── .instructions/
    ├── REQUIREMENTS.md
    ├── TESTING_EXTENSIVE.md
    └── TESTING_SIMPLE.md
```

| Documento | Quando consultar |
|---|---|
| `.instructions/REQUIREMENTS.md` | Antes de criar ou modificar qualquer arquivo do pacote |
| `.instructions/TESTING_EXTENSIVE.md` | Apenas como contexto — **não implementar** (ver nota abaixo) |
| `.instructions/TESTING_SIMPLE.md` | Ao implementar ou executar o teste de integração manual |

**Nunca implemente de memória.** Se houver dúvida sobre um comportamento esperado, `.instructions/REQUIREMENTS.md` é a fonte de verdade.

### Escopo de testes para a v0.1.0

> **`TESTING_EXTENSIVE.md` — somente leitura.** Este documento descreve a suíte completa de testes automatizados do pacote. Seu conteúdo serve exclusivamente como enriquecimento de contexto e como guia para implementações **futuras**. Nenhum teste descrito nele deve ser criado agora.
>
> **`TESTING_SIMPLE.md` — implementar junto com o pacote.** O teste de integração manual descrito neste arquivo deve ser implementado como parte da entrega da v0.1.0, em paralelo com os módulos do pacote. Ao concluir a implementação do pacote, o arquivo `tests/simple-flow-source-gh/deploy_flow_country_rbr.py` deve existir e o procedimento de execução descrito no documento deve funcionar sem erros.

---

## Estrutura do Projeto

```
rbr-prefect/
├── .instructions/
│   ├── REQUIREMENTS.md              # fonte de verdade do pacote
│   ├── TESTING_EXTENSIVE.md         # contexto para testes futuros - nao implementar agora
│   └── TESTING_SIMPLE.md            # teste de integracao manual - implementar na v0.1.0
├── rbr_prefect/
│   ├── __init__.py          # superficie publica - DefaultDeploy, ScrapeDeploy, __version__
│   ├── constants.py         # unica fonte de valores literais de infraestrutura
│   ├── deploy.py            # toda logica de deploy - BaseDeploy, subclasses, strategies
│   └── _cli/
│       ├── __init__.py      # expoe apenas funcoes de alto nivel de ui.py
│       ├── messages.py      # unica fonte de textos exibidos ao dev
│       └── ui.py            # logica de apresentacao com rich
├── tests/
│   └── simple-flow-source-gh/
│       ├── flows/
│       │   └── flow_country.py
│       ├── deploy_flow_country.py       # referencia - nao modificar
│       └── deploy_flow_country_rbr.py   # implementar conforme TESTING_SIMPLE.md
├── CLAUDE.md                            # este arquivo
├── pyproject.toml
└── uv.lock
```

---

## Regras Absolutas

As regras abaixo nunca devem ser violadas, independentemente do contexto ou da solicitação:

### R1 — Zero magic strings fora de `constants.py`

Nenhum valor literal de infraestrutura pode aparecer fora de `constants.py`. Isso inclui URLs, nomes de imagem Docker, nomes de blocos do Prefect, nomes de work pools e caminhos de volume.

```python
# ERRADO — nunca faça isso em deploy.py ou qualquer outro arquivo de lógica
image = "prefecthq/prefect:3-python3.12"

# CORRETO
image = RBRDocker.DEFAULT_IMAGE
```

### R2 — Zero valores literais fora de `messages.py`

Nenhum texto exibido ao dev no terminal pode aparecer fora de `_cli/messages.py`. Isso inclui avisos, prompts, labels do painel de auditoria e mensagens de erro de validação.

```python
# ERRADO — nunca faça isso em ui.py
console.print("Sobrescrever o work pool é incomum...")

# CORRETO
console.print(WorkPoolMessages.OVERRIDE_WARNING)
```

### R3 — Apenas `.deploy()` tem efeitos colaterais

Nenhuma chamada de rede, nenhum acesso à API do Prefect e nenhum `subprocess` de escrita pode ocorrer fora do método `.deploy()`. O `__init__` pode chamar `subprocess` para leitura (via `GitHubSourceStrategy`), mas nunca para escrita.

### R4 — Subclasses não reimplementam lógica de `BaseDeploy`

`DefaultDeploy` e `ScrapeDeploy` só podem: (a) fornecer defaults diferentes no `__init__`, e (b) sobrescrever os hooks `_build_extra_env()` e `_build_extra_job_variables()`. Qualquer outra lógica pertence ao `BaseDeploy`.

### R5 — `_cli` é totalmente privado

Nenhum arquivo fora do pacote importa diretamente de `_cli`. O `deploy.py` importa de `rbr_prefect._cli` (via `__init__.py` do submódulo), nunca de `rbr_prefect._cli.ui` ou `rbr_prefect._cli.messages` diretamente.

---

## Ordem de Implementação Recomendada

Implemente os módulos nesta ordem para minimizar dependências não resolvidas:

```
1. constants.py           — sem dependências internas
2. _cli/messages.py       — sem dependências internas
3. _cli/ui.py             — depende de messages.py
4. _cli/__init__.py       — depende de ui.py
5. deploy.py              — depende de constants.py e _cli/
   5a. BaseSourceStrategy (classe abstrata)
   5b. GitHubSourceStrategy
   5c. DockerSourceStrategy (esqueleto — apenas NotImplementedError)
   5d. BaseDeploy
   5e. DefaultDeploy
   5f. ScrapeDeploy
6. __init__.py            — depende de deploy.py
```

Não pule etapas. Um módulo incompleto em uma etapa anterior causará erros em cascata.

---

## Convenções de Código

### Nomenclatura

| Contexto | Convenção | Exemplo |
|---|---|---|
| Classes de constantes | `RBR<Domínio>` | `RBRDocker`, `RBRWorkPools` |
| Constantes públicas em classes de mensagens | `UPPER_CASE` | `OVERRIDE_WARNING` |
| Templates privados em classes de mensagens | `_UPPER_CASE` | `_OVERRIDE_CONFIRM` |
| Factories de mensagens | `snake_case` estático | `override_confirm(pool)` |
| Atributos de instância em `BaseDeploy` | `_snake_case` (privado) | `_flow_func`, `_image` |
| Hooks de extensão para subclasses | `_build_<domínio>` | `_build_extra_env()` |
| Métodos de resolução interna | `_resolve_<domínio>` | `_resolve_env()` |

### Imports

Organize os imports em três blocos separados por linha em branco, nesta ordem:

```python
# 1. Biblioteca padrão
import inspect
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path

# 2. Dependências externas (prefect, pydantic, rich, etc.)
from prefect.runner.storage import GitRepository
from rich.console import Console

# 3. Imports internos do pacote
from rbr_prefect.constants import RBRBlocks, RBRDocker
from rbr_prefect._cli import print_audit_panel
```

Nunca use imports circulares. A hierarquia de dependências é: `constants` → `messages` → `ui` → `deploy`.

### Type hints

Use type hints em todos os métodos públicos e nos atributos de instância definidos no `__init__`. Use `|` em vez de `Optional` e `Union` (Python 3.12+).

```python
# CORRETO
def __init__(self, github_url: str | None = None) -> None:

# EVITAR
def __init__(self, github_url: Optional[str] = None) -> None:
```

Nunca importe de `typing` `List` com L maiúsculo ou `Dict` com D maiúsculo. Utilize para type hints sempre `list` ou `dict` diretamente.

---

## Pontos de Atenção por Módulo

### `constants.py`

- Os métodos `auth_string_template()` e `header_template()` de `RBRBlocks` devem ser compostos **programaticamente** a partir dos outros atributos da classe, não hardcodados como strings completas. Isso é o que garante a propagação automática ao renomear o bloco.

### `_cli/messages.py`

- Templates `_UPPER_CASE` nunca devem ser usados diretamente fora da classe onde foram definidos — apenas via factory methods.
- Cada factory deve usar `.format()` sobre o template privado, não f-strings com os valores inline.
- Mensagens de `ValidationMessages` são usadas como argumentos de `ValueError` e `RuntimeError` em `deploy.py` — devem ser orientativas e mencionar como o dev pode resolver o problema.

### `_cli/ui.py`

- A instância `_console` deve ser criada com `file=sys.stdout` explícito.
- `print_handoff` deve ser a **última** função de `ui.py` chamada antes de `deployable.deploy()` — este contrato é verificado nos testes de integração.
- Funções `confirm_*` devem retornar `bool` — a decisão de abortar com `SystemExit` é do chamador (`BaseDeploy`), não da função de UI.

### `deploy.py` — `GitHubSourceStrategy`

- O cache de `_repo_root` é essencial para performance — verificar que `subprocess.run` para `--show-toplevel` é chamado no máximo uma vez por instância.
- A normalização `.pyc` → `.py` em `resolve_entrypoint` deve ocorrer **antes** do `relative_to()`, não depois.
- Erros do subprocess devem capturar `subprocess.CalledProcessError` e relançar como `RuntimeError` com mensagem do `ValidationMessages` correspondente.
- As propriedades `resolved_github_url`, `resolved_branch` e `resolved_repo_root` devem delegar para os métodos `_resolve_*` — não duplicar a lógica.

### `deploy.py` — `BaseDeploy`

- A ordem de operações no `__init__` definida na Seção 5.4 do `REQUIREMENTS.md` é estrita. Não reordene as etapas.
- Os prompts de confirmação (`confirm_work_pool_override`, `confirm_concurrency_limit`) ocorrem no `__init__`, não no `.deploy()`. O aborto via `SystemExit(0)` também ocorre no `__init__`.
- `_resolve_job_variables()` deve sempre injetar o `env` por último via `_resolve_env()`, mesmo que `extra_job_variables` contenha a chave `env`. Isso previne que o dev sobrescreva acidentalmente o env base RBR via `extra_job_variables`.
- `_build_description()` depende de `importlib.metadata.version("rbr-prefect")` — nos testes, esta chamada deve ser mockada.
- O parâmetro `name` de `.deploy(name=...)` é um override opcional para aquela chamada específica — não modifica `self._name`.

### `__init__.py`

- `__all__` deve ser mantido em sincronia com os imports exportados. Ao adicionar uma nova subclasse pública no futuro, ambos devem ser atualizados.
- `BaseDeploy` e `GitHubSourceStrategy` são **importáveis** mas **não exportadas** via `__all__` — este é o comportamento correto e intencional.

---

## Erros Comuns a Evitar

### Lógica condicional em `constants.py`

`constants.py` não deve ter `if`, `for` nem lógica de negócio. A única exceção são os métodos estáticos de `RBRBlocks` que compõem strings a partir dos próprios atributos da classe.

### Texto hardcoded em `deploy.py`

```python
# ERRADO
raise ValueError("Pelo menos uma tag é obrigatória.")

# CORRETO
raise ValueError(ValidationMessages.TAGS_REQUIRED)
```

### Merge incorreto de `env` em `_resolve_job_variables`

```python
# ERRADO — extra_job_variables pode sobrescrever o env base RBR se contiver chave "env"
merged = {**base, **extras, **user}
return merged

# CORRETO — env sempre resolvido por último, de forma independente
merged = {**base, **extras, **user}
merged["env"] = self._resolve_env()   # sobrescreve qualquer "env" que veio de extras/user
return merged
```

### `subprocess` sem `check=True`

```python
# ERRADO — falhas silenciosas
result = subprocess.run(["git", "remote", "get-url", "origin"], capture_output=True)

# CORRETO — lança CalledProcessError que pode ser capturado e relançado como RuntimeError
result = subprocess.run(
    ["git", "remote", "get-url", "origin"],
    capture_output=True,
    text=True,
    check=True,
)
```

### Aborto com exceção em vez de `SystemExit`

Quando o usuário nega um prompt de confirmação, o aborto deve ser `SystemExit(0)` — não `ValueError` nem `RuntimeError`. O aborto é uma decisão do usuário, não um erro do programa.

```python
# ERRADO
if not confirmed:
    raise ValueError(WorkPoolMessages.OVERRIDE_ABORTED)

# CORRETO
if not confirmed:
    raise SystemExit(0)
```

---

## Fluxo de Verificação Antes de Concluir uma Tarefa

Antes de marcar qualquer tarefa como concluída, execute mentalmente este checklist:

- [ ] Nenhum valor literal de infraestrutura fora de `constants.py`
- [ ] Nenhum texto de UI fora de `_cli/messages.py`
- [ ] Nenhuma chamada de rede fora de `.deploy()`
- [ ] Subclasses não reimplementam lógica de `BaseDeploy`
- [ ] Imports organizados em três blocos na ordem correta
- [ ] Type hints em todos os métodos públicos
- [ ] Erros lançados com mensagens de `ValidationMessages`
- [ ] `SystemExit(0)` (não exceção) para abortos por decisão do usuário
- [ ] `__all__` em `__init__.py` atualizado se novos nomes públicos foram adicionados
- [ ] Nenhuma regressão nos contratos documentados em `.instructions/TESTING_EXTENSIVE.md`