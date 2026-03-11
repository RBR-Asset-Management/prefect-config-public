# TESTING.md — Requisitos de Testes: `rbr-prefect`

---

## Visão Geral

Este documento define **o que precisa ser testado** em cada módulo do pacote `rbr-prefect`, as estratégias de mock recomendadas e os critérios de cobertura esperados. Ele não contém implementações — serve como guia para o desenvolvimento da suíte de testes.

### Filosofia de Teste

O pacote tem um invariante central que deve guiar toda a estratégia de teste: **apenas `.deploy()` tem efeitos colaterais**. Isso significa que toda a construção e configuração do objeto deve ser testável sem nenhuma chamada de rede, sem acesso ao filesystem real e sem interação com a API do Prefect. Os testes devem refletir e reforçar esse invariante.

Três categorias de dependências externas precisam ser mockadas sistematicamente:

- **Git CLI** — chamadas `subprocess` para `git remote get-url`, `git rev-parse` e similares em `GitHubSourceStrategy`.
- **Prefect API** — `GitHubCredentials.load()`, `flow.from_source()` e `deployable.deploy()` em `BaseDeploy.deploy()`.
- **Terminal / `rich`** — `Console.print()`, `Confirm.ask()` e `Rule` em `_cli/ui.py`.

---

## Estratégias de Mock

### Mock do Git CLI

Toda detecção automática em `GitHubSourceStrategy` usa `subprocess.run()`. O mock deve interceptar essa chamada e retornar objetos `CompletedProcess` simulados.

```
subprocess.run → mock por comando argv[0:3]
  ["git", "rev-parse", "--show-toplevel"]  → retorna /fake/repo/root
  ["git", "remote", "get-url", "origin"]   → retorna https://github.com/RBR/repo.git
  ["git", "rev-parse", "--abbrev-ref", "HEAD"] → retorna main
```

Cenários de falha devem simular `subprocess.CalledProcessError` para testar o tratamento de erros de cada comando individualmente.

O `repo_root` cacheado (`self._repo_root`) significa que os testes de cache podem verificar que `subprocess.run` é chamado exatamente uma vez em chamadas múltiplas à mesma propriedade.

### Mock da Prefect API

As chamadas ao Prefect ocorrem exclusivamente dentro de `.deploy()`, o que facilita o isolamento. Os pontos de mock são:

```
GitHubCredentials.load(name)   → retorna objeto mock de credenciais
flow_func.from_source(...)     → retorna objeto mock "deployable"
deployable.deploy(...)         → retorna None (sem efeito colateral)
importlib.metadata.version()   → retorna string de versão fixa "0.1.0"
```

A função `flow_func` passada nos testes deve ser uma função Python simples decorada com `@flow` (ou um mock callable) para permitir introspecção via `inspect.signature` e `inspect.getfile`.

### Mock do Terminal (`rich`)

As funções de `_cli/ui.py` interagem com o terminal via `rich.Console` e `rich.prompt.Confirm`. O mock deve:

```
Console.print(...)    → capturar chamadas para assertar mensagens exibidas
Confirm.ask(...)      → retornar True ou False conforme o cenário
```

Para testes de `.deploy()` que não focam no terminal, o mock deve simplesmente suprimir o output sem verificar o conteúdo.

### Mock do `inspect.getfile`

Para testar a resolução de entrypoint em `GitHubSourceStrategy.resolve_entrypoint()`, `inspect.getfile(flow_func)` deve retornar um caminho controlado. O mock deve simular:
- Caminho dentro do repositório (caso feliz).
- Caminho fora do repositório (caso de erro `ValueError`).
- Caminho `.pyc` com e sem `.py` correspondente.

---

## Seção 1 — `constants.py`

### Natureza dos Testes

`constants.py` não tem lógica condicional — apenas definições de classe com atributos e dois métodos factory. Os testes aqui são de **contrato**: garantem que os valores e a estrutura que o restante do pacote espera permanecem estáveis e corretos.

### O que testar

**Estrutura e valores das classes de constantes**

Verificar que cada classe existe e cada atributo tem o valor literal esperado. Qualquer mudança inadvertida em um valor de infraestrutura (ex: URL da API, nome de imagem) será detectada imediatamente.

| Classe | Atributos a verificar |
|---|---|
| `RBRPrefectServer` | `API_URL`, `SSL_CERT_PATH` |
| `RBRDocker` | `DEFAULT_IMAGE`, `SCRAPE_IMAGE`, `CERT_VOLUME`, `PLAYWRIGHT_BROWSERS_PATH`, `PLAYWRIGHT_DISPLAY` |
| `RBRWorkPools` | `DEFAULT` |
| `RBRBlocks` | `GITHUB_CREDENTIALS`, `BASIC_AUTH`, `_BLOCK_TYPE_BASIC_AUTH`, `_AUTH_STRING_FIELD`, `_HEADER_FIELD` |
| `RBRJobVariables` | `AUTO_REMOVE`, `IMAGE_PULL_POLICY` |

**Métodos factory de `RBRBlocks`**

Os dois métodos `auth_string_template()` e `header_template()` devem produzir strings no formato exato que o Prefect espera para referência de blocos.

- `auth_string_template()` deve conter `prefect.blocks`, o slug do tipo, o nome do bloco e o caminho do campo `auth_string`, todos separados por ponto, envoltos em `{{ }}`.
- `header_template()` deve ter a mesma estrutura com o caminho do campo `header`.
- A consistência entre os templates e os atributos privados (`_BLOCK_TYPE_BASIC_AUTH`, `_AUTH_STRING_FIELD`, etc.) deve ser verificada: alterar `BASIC_AUTH` deve alterar automaticamente ambos os templates.

**Cobertura esperada:** 100% de linhas — não há branches condicionais.

---

## Seção 2 — `_cli/messages.py`

### Natureza dos Testes

`messages.py` contém apenas strings e métodos factory de interpolação. Os testes garantem que os factories produzem os textos esperados e que as constantes existem como strings não-vazias.

### O que testar

**Existência e tipo das constantes públicas**

Cada constante `UPPER_CASE` de cada classe deve existir e ser do tipo `str` com conteúdo não-vazio. Isso previne regressões onde uma mensagem é apagada ou renomeada.

**Métodos factory — interpolação correta**

Cada método factory deve ser testado com pelo menos:
- Um input válido representativo.
- Verificação de que o placeholder foi substituído pelo valor fornecido.
- Verificação de que o restante da string está presente.

| Método | Input de teste | O que verificar |
|---|---|---|
| `DeployMessages.deploy_starting(name)` | `"my-flow"` | `"my-flow"` presente na string retornada |
| `WorkPoolMessages.override_confirm(pool)` | `"custom-pool"` | `"custom-pool"` presente na string retornada |
| `ValidationMessages.invalid_param(param, flow)` | `"country"`, `"my_flow"` | Ambos os valores presentes |
| `ValidationMessages.schedule_mutex()` | — | String não-vazia contendo "cron", "interval", "rrule" |

**Separação entre templates privados e constantes públicas**

Verificar que templates `_UPPER_CASE` não aparecem literais (sem interpolação) em nenhum output — apenas os resultados dos factories são usados externamente.

**Cobertura esperada:** 100% de linhas.

---

## Seção 3 — `_cli/ui.py`

### Natureza dos Testes

`ui.py` é o módulo mais orientado a efeitos colaterais do pacote. Os testes verificam **quais** funções do `rich` são chamadas e **com quais argumentos**, não o conteúdo visual renderizado.

### Estratégia de mock

Todas as funções de `ui.py` devem ser testadas com `Console.print` e `Confirm.ask` mockados. A instância `_console` pode ser substituída antes dos testes ou as funções podem ser testadas via patch do módulo.

### O que testar

**`print_handoff(name)`**

- `_console.print` deve ser chamado com uma string contendo o nome do deploy.
- Um objeto `Rule` (ou equivalente) deve ser renderizado após a mensagem.
- A função não deve lançar exceções com qualquer string de nome válida.

**`print_audit_panel(resolved, overrides, env)`**

- Com `overrides` vazio: nenhuma seção de overrides deve ser exibida.
- Com `overrides` não-vazio: seção de overrides deve estar presente no output.
- Com `env_override` ou `job_variables_override` sinalizados: aviso em vermelho deve aparecer.
- Os dicts passados devem ter seus valores representados no output — verificar que `_console.print` foi chamado pelo menos uma vez com cada valor relevante.

**`confirm_work_pool_override(pool_name)`**

- Quando `Confirm.ask` retorna `True`: função retorna `True` e não imprime mensagem de abort.
- Quando `Confirm.ask` retorna `False`: função retorna `False` e imprime `WorkPoolMessages.OVERRIDE_ABORTED`.
- O aviso de override deve ser impresso antes do `Confirm.ask` em ambos os cenários.

**`confirm_concurrency_limit()`**

- Comportamento análogo ao `confirm_work_pool_override`: retorno correto nos dois casos, aviso impresso antes do prompt.

**`confirm_advanced_schedule()`**

- Comportamento análogo: retorno correto nos dois casos, aviso impresso antes do prompt.

**Cobertura esperada:** ≥ 90% de linhas — branches de formatação interna do `rich` podem ser difíceis de atingir.

---

## Seção 4 — `GitHubSourceStrategy`

### Natureza dos Testes

Esta é a classe com maior quantidade de lógica condicional e dependências externas no pacote. Os testes cobrem detecção automática, overrides explícitos, caching e todos os cenários de erro da integração com o Git.

### O que testar

**Detecção automática — caso feliz**

Com `subprocess.run` mockado para os três comandos Git:
- `_resolve_github_url()` deve retornar a URL do remote `origin`.
- `_resolve_branch()` deve retornar o branch atual.
- `_resolve_repo_root()` deve retornar o caminho da raiz do repositório como `Path`.

**Override de valores individuais**

- Ao passar `github_url` no `__init__`, `subprocess.run` **não deve** ser chamado para o comando `get-url origin`.
- Ao passar `branch` no `__init__`, `subprocess.run` **não deve** ser chamado para o comando `rev-parse --abbrev-ref HEAD`.
- Os overrides devem ser retornados diretamente pelas propriedades correspondentes.

**Caching de `repo_root`**

- Chamar `_resolve_repo_root()` múltiplas vezes deve resultar em exatamente **uma** chamada a `subprocess.run` para o comando `--show-toplevel`. Verificar que a segunda chamada retorna o valor cacheado sem novo subprocess.

**`resolve_entrypoint(flow_func)`**

- Com `inspect.getfile` retornando um caminho dentro do `repo_root` mockado: o entrypoint deve ter o formato `"pasta/flow_file.py:nome_da_funcao"`.
- O separador de path deve ser `/` (posix), não `\` — importante para compatibilidade cross-platform.
- Com arquivo `.pyc`: deve ser normalizado para `.py` antes de calcular o path relativo.
- Com arquivo `.pyc` cujo `.py` correspondente não existe: deve lançar `FileNotFoundError`.

**Propriedades `resolved_*` para auditoria**

- `resolved_github_url`, `resolved_branch` e `resolved_repo_root` devem retornar os mesmos valores que os métodos internos, aproveitando o cache quando já resolvidos.

**Cenários de erro — subprocess falha**

Cada chamada a `subprocess.run` deve ser testada individualmente simulando `CalledProcessError`:

| Comando que falha | Exceção esperada | Mensagem deve mencionar |
|---|---|---|
| `git rev-parse --show-toplevel` | `RuntimeError` | "repositório Git" ou "git" |
| `git remote get-url origin` | `RuntimeError` | "remote", "origin" |

**Cenário de erro — entrypoint fora do repositório**

Quando `inspect.getfile` retorna um path que não é subpath do `repo_root`: deve lançar `ValueError`.

**`build()` — integração com Prefect**

Com `GitHubCredentials.load` mockado:
- Deve retornar um `GitRepository` (ou mock equivalente).
- Os argumentos passados ao `GitRepository` devem corresponder aos valores resolvidos.
- `GitHubCredentials.load` deve ser chamado com `RBRBlocks.GITHUB_CREDENTIALS`.

**`DockerSourceStrategy.build()` e `resolve_entrypoint()`**

Ambos devem lançar `NotImplementedError` com mensagem orientativa.

---

## Seção 5 — `BaseDeploy.__init__` e Validações

### Natureza dos Testes

O construtor de `BaseDeploy` é responsável por toda validação inicial e resolução de valores. Os testes cobrem o contrato de cada validação, a lógica de default e a correta delegação para a source strategy.

Para todos os testes desta seção, usar uma `flow_func` simples com assinatura conhecida, e mockar `GitHubSourceStrategy` para evitar chamadas reais ao Git.

### O que testar

**Validação de `tags`**

- Lista vazia deve lançar `ValueError`.
- `None` deve lançar `TypeError` ou `ValueError`.
- Lista com ao menos um elemento deve passar sem exceção.

**Validação de mutualidade exclusiva `env_override` vs `extra_env`**

- Fornecer ambos simultaneamente deve lançar `ValueError`.
- Fornecer apenas `env_override`: nenhuma exceção.
- Fornecer apenas `extra_env`: nenhuma exceção.

**Validação de mutualidade exclusiva `job_variables_override` vs `extra_job_variables`**

- Comportamento análogo ao pair de env.

**Prompt de confirmação para `work_pool_name` não-padrão**

- Quando `work_pool_name != RBRWorkPools.DEFAULT` e `confirm_work_pool_override` retorna `False`: deve chamar `SystemExit(0)`.
- Quando `confirm_work_pool_override` retorna `True`: construção deve completar normalmente.
- Quando `work_pool_name == RBRWorkPools.DEFAULT`: `confirm_work_pool_override` **não** deve ser chamado.

**Prompt de confirmação para `concurrency_limit`**

- Quando fornecido e `confirm_concurrency_limit` retorna `False`: deve chamar `SystemExit(0)`.
- Quando fornecido e retorna `True`: construção completa normalmente.
- Quando não fornecido: função de confirmação não deve ser chamada.

**Resolução do entrypoint**

- Sem `entrypoint` explícito: `source_strategy.resolve_entrypoint(flow_func)` deve ser chamado e seu retorno armazenado.
- Com `entrypoint` explícito: `resolve_entrypoint` **não** deve ser chamado; o valor explícito deve ser armazenado diretamente.

**Instanciação da source strategy**

- Sem `source_strategy` explícito: uma `GitHubSourceStrategy` deve ser instanciada automaticamente.
- Com `github_url` e/ou `branch` fornecidos: esses valores devem ser repassados para `GitHubSourceStrategy`.
- Com `source_strategy` explícito: deve ser usado diretamente sem criar nova instância.

**Extração de `parameters` default via `inspect.signature`**

- Para uma `flow_func` com parâmetros com default: o dict extraído deve conter apenas os parâmetros que têm default.
- Para uma `flow_func` sem parâmetros com default: `_parameters` deve ser um dict vazio.
- Para uma `flow_func` com parâmetros obrigatórios sem default: esses parâmetros **não** devem aparecer em `_parameters`.

---

## Seção 6 — `BaseDeploy.override()` e o Setter de `parameters`

### Natureza dos Testes

O método `override()` é o mecanismo principal de customização para o dev. Os testes garantem que o merge sobre defaults funciona corretamente e que a validação de chaves previne typos silenciosos.

### O que testar

**Merge sobre defaults**

- Chamar `override(param_a="novo")` em um flow com defaults `{param_a: "original", param_b: "outro"}` deve retornar `{param_a: "novo", param_b: "outro"}` — parâmetros não mencionados mantêm seu default.
- Chamar `override()` sem argumentos deve retornar uma cópia dos defaults sem alteração.

**Validação de chaves**

- Passar uma chave que não existe na assinatura do flow deve lançar `ValueError` com o nome do parâmetro inválido na mensagem.
- Passar múltiplas chaves onde uma é inválida deve lançar `ValueError`.
- Passar apenas chaves válidas não deve lançar exceção.

**Setter de `parameters`**

- Atribuir um dict com chaves inválidas via `deploy.parameters = {...}` deve lançar `ValueError`.
- Atribuir um dict válido deve atualizar `self._parameters`.
- Atribuir via `deploy.parameters = deploy.override(...)` deve funcionar corretamente como padrão de uso principal.

**Idempotência**

- Chamar `override` duas vezes com valores diferentes deve sempre ser baseado nos defaults originais do flow — não acumular overrides sobre o resultado anterior.

---

## Seção 7 — Resolução de `job_variables` e `env`

### Natureza dos Testes

A hierarquia de merge é a lógica mais complexa do pacote fora da source strategy. Os testes verificam cada camada do merge e os casos de bypass total.

### O que testar

**`_build_base_job_variables()`**

- Deve retornar um dict com exatamente as chaves `volumes`, `auto_remove`, `image_pull_policy`.
- Os valores devem corresponder às constantes de `RBRJobVariables` e `RBRDocker`.
- A chave `volumes` deve ser uma lista com exatamente `[RBRDocker.CERT_VOLUME]`.

**`_resolve_job_variables()` — hierarquia de merge**

- Sem nenhum override do dev: resultado deve conter todas as chaves base.
- Com `extra_job_variables`: chaves extras devem ser adicionadas; chaves base devem ser preservadas.
- Com `job_variables_override`: o resultado deve ser **exatamente** o dict fornecido — sem chaves base da RBR.
- O `env` deve sempre ser a última chave resolvida via `_resolve_env()`, mesmo quando `extra_job_variables` inclui a chave `env`.

**`_build_base_env()`**

- Deve retornar exatamente as quatro variáveis de ambiente RBR: `PREFECT_API_URL`, `PREFECT_API_SSL_CERT_FILE`, `PREFECT_API_AUTH_STRING`, `PREFECT_CLIENT_CUSTOM_HEADERS`.
- Os valores de `PREFECT_API_AUTH_STRING` e `PREFECT_CLIENT_CUSTOM_HEADERS` devem ser os templates de bloco gerados por `RBRBlocks.auth_string_template()` e `RBRBlocks.header_template()`.

**`_resolve_env()` — hierarquia de merge**

- Sem overrides: resultado deve conter apenas as chaves do base RBR.
- Com `extra_env`: chaves extras adicionadas; chaves base preservadas.
- Com chave em `extra_env` que colide com chave base: a chave do `extra_env` do dev deve vencer.
- Com `env_override`: resultado deve ser **exatamente** o dict fornecido — sem variáveis de ambiente RBR.

**`_build_extra_env()` em `ScrapeDeploy`**

- Deve retornar as variáveis do Playwright (`PLAYWRIGHT_BROWSERS_PATH`, `DISPLAY`).
- O merge com o base RBR deve conter ambas as variáveis RBR e as do Playwright.

**`_build_extra_env()` em `DefaultDeploy`**

- Deve retornar dict vazio.

---

## Seção 8 — `BaseDeploy.schedule()`

### Natureza dos Testes

`.schedule()` não tem efeitos colaterais de rede — apenas valida, opcionalmente prompta e armazena o schedule. Os testes verificam as validações, o prompt para casos avançados e o retorno para encadeamento.

### O que testar

**Exclusividade mútua dos parâmetros**

- Chamar `.schedule()` sem nenhum parâmetro deve lançar `ValueError`.
- Passar `cron` e `interval` simultaneamente deve lançar `ValueError`.
- Passar `cron` e `rrule` simultaneamente deve lançar `ValueError`.
- Passar `interval` e `rrule` simultaneamente deve lançar `ValueError`.
- Passar os três simultaneamente deve lançar `ValueError`.

**`cron` — caminho feliz**

- Com um objeto válido do `cronexpressions`: `_schedule` deve ser um `CronSchedule` do Prefect.
- `confirm_advanced_schedule` **não** deve ser chamado.
- O método deve retornar `self` para permitir encadeamento.

**`interval` — confirmação obrigatória**

- `confirm_advanced_schedule` **deve** ser chamado.
- Quando confirma: `_schedule` deve ser um `IntervalSchedule`; método retorna `self`.
- Quando nega: `SystemExit` ou abort deve ocorrer.

**`rrule` — confirmação obrigatória**

- Comportamento análogo ao `interval`.

**Retorno para encadeamento**

- O retorno de `.schedule(cron=...)` deve ser a própria instância, permitindo `deploy.schedule(...).deploy()`.

---

## Seção 9 — `BaseDeploy.deploy()`

### Natureza dos Testes

`.deploy()` é o único método com efeitos colaterais — todos os testes desta seção devem mockar `flow_func.from_source()` e `deployable.deploy()`. O foco é verificar que os argumentos corretos são passados ao Prefect e que a sequência de chamadas ao terminal está correta.

### O que testar

**Sequência de interações com o terminal**

Usando mocks para todas as funções de `_cli/ui.py`, verificar a ordem de chamada:
1. `print_audit_panel` deve ser chamado antes de `print_handoff`.
2. `print_handoff` deve ser chamado antes de `from_source`.
3. Nenhuma função de `_cli/ui.py` deve ser chamada **após** `from_source`.

**Argumentos passados ao `deployable.deploy()`**

- `name` deve corresponder ao nome do deploy (ou ao override passado em `.deploy(name=...)`).
- `work_pool_name` deve ser o valor do `_work_pool_name`.
- `image` deve ser o valor do `_image`.
- `build` deve ser `False`.
- `push` deve ser `False`.
- `job_variables` deve ser o resultado de `_resolve_job_variables()`.
- `parameters` deve ser o valor de `_parameters`.
- `tags` deve ser o valor de `_tags`.
- `schedules` deve ser `[_schedule]` quando schedule foi configurado, ou `[]` quando não foi.
- `concurrency_limit` deve ser o valor de `_concurrency_limit` (incluindo `None`).

**Override de nome no momento do `.deploy(name=...)`**

- Passar `name` no `.deploy()` deve sobrescrever o nome configurado no construtor apenas para essa chamada.

**`from_source()` — argumentos**

- `source` deve ser o resultado de `source_strategy.build()`.
- `entrypoint` deve ser o valor de `_entrypoint`.

**`_build_description()`**

- Deve retornar string contendo o nome da função flow, a URL do repositório, o branch, o entrypoint e a versão do pacote.
- A URL do arquivo no GitHub deve ser corretamente composta (sem `.git`, com `/blob/branch/path`).
- `importlib.metadata.version("rbr-prefect")` deve ser mockado para retornar uma versão fixa.

**Flags de aviso no painel de auditoria**

- Com `job_variables_override` fornecido: `print_audit_panel` deve receber sinalização de que o bypass está ativo.
- Com `env_override` fornecido: analogamente.

---

## Seção 10 — `DefaultDeploy` e `ScrapeDeploy`

### Natureza dos Testes

As subclasses têm lógica mínima — apenas defaults diferentes e, no caso do `ScrapeDeploy`, o hook `_build_extra_env()`. Os testes verificam que os defaults estão corretos e que a herança funciona como esperado.

### O que testar

**Defaults de `DefaultDeploy`**

- `_image` deve ser `RBRDocker.DEFAULT_IMAGE`.
- `_work_pool_name` deve ser `RBRWorkPools.DEFAULT`.
- `_build_extra_env()` deve retornar `{}`.
- `_build_extra_job_variables()` deve retornar `{}`.

**Defaults de `ScrapeDeploy`**

- `_image` deve ser `RBRDocker.SCRAPE_IMAGE`.
- `_work_pool_name` deve ser `RBRWorkPools.DEFAULT`.
- `_build_extra_env()` deve retornar dict com `PLAYWRIGHT_BROWSERS_PATH` e `DISPLAY`.
- `_build_extra_job_variables()` deve retornar `{}`.

**`ScrapeDeploy` — env merged inclui Playwright e RBR**

- `_resolve_env()` deve retornar um dict com as quatro variáveis RBR **mais** as variáveis do Playwright.
- As variáveis do Playwright não devem sobrescrever as variáveis base RBR.

**Herança total de `BaseDeploy`**

- `DefaultDeploy` e `ScrapeDeploy` devem ter os atributos `override`, `schedule` e `deploy` — herdados sem reimplementação.

**Cenário end-to-end mínimo (smoke test)**

Com todos os mocks de Git e Prefect ativos, um fluxo completo de:
```
Instanciar → .schedule() → .deploy()
```
deve executar sem exceções para ambas as subclasses, com os argumentos corretos passados ao Prefect mockado.

---

## Seção 11 — Superfície Pública (`__init__.py`)

### Natureza dos Testes

Testes de contrato da API pública. Garantem que o pacote expõe exatamente o que promete e nada mais.

### O que testar

**Imports diretos válidos**

- `from rbr_prefect import DefaultDeploy` deve funcionar sem erro.
- `from rbr_prefect import ScrapeDeploy` deve funcionar sem erro.
- `from rbr_prefect import __version__` deve retornar uma string no formato semver (`X.Y.Z`).

**Imports por submódulo válidos**

- `from rbr_prefect.constants import RBRDocker` e demais classes de constantes devem funcionar.
- `from rbr_prefect.deploy import BaseDeploy` deve funcionar (acesso avançado documentado).
- `from rbr_prefect.deploy import GitHubSourceStrategy` deve funcionar.

**Sincronização de versão**

- `rbr_prefect.__version__` deve ser igual ao retorno de `importlib.metadata.version("rbr-prefect")` quando o pacote está instalado em desenvolvimento (`pip install -e .`).

**`__all__` contém exatamente os membros documentados**

- `rbr_prefect.__all__` deve conter `["DefaultDeploy", "ScrapeDeploy", "__version__"]` — nem mais, nem menos.

**Submódulo `_cli` não exportado**

- `hasattr(rbr_prefect, "_cli")` deve ser `False` após `import rbr_prefect`.

---

## Seção 12 — Cenários de Integração

### Natureza dos Testes

Testes que exercitam múltiplos módulos em conjunto, verificando o comportamento do pacote como um todo — ainda com mocks de Git e Prefect, mas sem isolar módulos individuais.

### Cenários a cobrir

**Deploy mínimo funcional**

Um `DefaultDeploy` criado com o mínimo obrigatório (`flow_func`, `name`, `tags`) com Git e Prefect mockados deve executar `.deploy()` sem exceções e chamar `deployable.deploy()` com os argumentos corretos.

**Fluxo completo com todos os opcionais**

Um deploy configurado com `extra_env`, `extra_job_variables`, schedule via cron e `parameters` via `override()` deve:
- Passar todos os valores corretamente para o Prefect.
- Exibir o painel de auditoria com todos os valores presentes.
- Não exibir avisos de bypass (pois não foi usado `_override`).

**Fluxo com bypass de env e job_variables**

Um deploy usando `env_override` e `job_variables_override` deve:
- Exibir avisos de bypass no painel de auditoria.
- Passar exatamente os dicts fornecidos ao Prefect, sem merge com base RBR.

**Abort por negação de confirmação — work pool**

Ao instanciar `DefaultDeploy` com `work_pool_name` customizado e `confirm_work_pool_override` mockado para retornar `False`, o `__init__` deve terminar com `SystemExit(0)`.

**Abort por negação de confirmação — schedule avançado**

Ao chamar `.schedule(interval=timedelta(hours=6))` com `confirm_advanced_schedule` mockado para retornar `False`, deve terminar com `SystemExit(0)`.

**Override de nome no deploy**

A mesma instância de deploy chamada com `.deploy(name="prod")` e depois `.deploy(name="staging")` deve passar os nomes corretos em cada chamada ao Prefect mockado.

---

## Seção 13 — Configuração da Suíte

### Estrutura de diretórios recomendada

```
tests/
├── conftest.py                   # fixtures compartilhadas: flow_func mock, subprocess mock
├── test_constants.py             # Seções 1
├── test_messages.py              # Seção 2
├── test_ui.py                    # Seção 3
├── test_github_source_strategy.py # Seção 4
├── test_base_deploy_init.py      # Seção 5
├── test_base_deploy_override.py  # Seção 6
├── test_base_deploy_env_vars.py  # Seção 7
├── test_base_deploy_schedule.py  # Seção 8
├── test_base_deploy_deploy.py    # Seção 9
├── test_subclasses.py            # Seção 10
├── test_public_api.py            # Seção 11
└── test_integration.py           # Seção 12
```

### Fixtures centrais recomendadas em `conftest.py`

**`mock_flow_func`** — uma função Python simples decorada com `@flow` com assinatura controlada (ex: `def my_flow(country: str = "Brazil", limit: int = 10)`), cujo `__file__` é patcheado para um caminho dentro de um repo root fictício.

**`mock_git`** — fixture que substitui `subprocess.run` para retornar valores Git fixos para os três comandos. Deve suportar parametrização para testar cenários de falha.

**`mock_prefect`** — fixture que substitui `GitHubCredentials.load`, `flow_func.from_source` e o objeto `deployable.deploy` retornado. Deve expor o mock de `deployable.deploy` para assertar os argumentos passados.

**`mock_ui`** — fixture que suprime todo o output do `rich` e permite assertar chamadas específicas quando necessário.

### Metas de cobertura

| Módulo | Cobertura de linhas mínima |
|---|---|
| `constants.py` | 100% |
| `_cli/messages.py` | 100% |
| `_cli/ui.py` | 90% |
| `_cli/__init__.py` | 100% |
| `deploy.py` — `GitHubSourceStrategy` | 95% |
| `deploy.py` — `BaseDeploy` | 90% |
| `deploy.py` — `DefaultDeploy`, `ScrapeDeploy` | 100% |
| `__init__.py` | 100% |
| **Total do pacote** | **≥ 90%** |

### Ferramentas

```toml
[dependency-groups]
dev = [
    "pytest>=8.0.0",
    "pytest-mock>=3.14.0",   # para mocker fixture
    "bump2version>=1.0.1",
]
```

A execução dos testes deve ser feita com:

```bash
uv run pytest                         # todos os testes
uv run pytest --cov=rbr_prefect       # com cobertura
uv run pytest tests/test_constants.py # módulo específico
```

---

*Fim do documento TESTING.md*