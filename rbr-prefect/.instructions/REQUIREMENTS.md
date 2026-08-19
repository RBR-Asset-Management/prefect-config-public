# Requisitos Técnicos — `rbr-prefect`

> **Leitor primário:** Claude Code. Este documento descreve lógica, invariantes e restrições de arquitetura. O código-fonte é a fonte de verdade para assinaturas e implementações; este documento é a fonte de verdade para *por que* as decisões foram tomadas e *quais contratos* o código deve satisfazer.

---

## Seção 1 — Visão Geral e Estrutura do Pacote

### 1.1 Descrição Geral

`rbr-prefect` é um pacote Python interno da RBR Asset Management que padroniza e simplifica o processo de deploy de flows do Prefect 3. O pacote encapsula toda a configuração de infraestrutura da RBR — credenciais, URLs, imagens Docker, variáveis de ambiente, volumes — eliminando a necessidade de repetir essas configurações em cada repositório de flow.

Cada dev importa o pacote no projeto em que estiver desenvolvendo um flow e utiliza as classes de deploy fornecidas. O arquivo de deploy de cada projeto reside no próprio repositório do flow — não há repositório centralizado de deploys. O pacote é a única peça centralizada; os deploys permanecem distribuídos com seus respectivos flows.

---

### 1.2 Filosofia de Design

**Zero magic strings.** Nenhum valor literal hardcoded fora de arquivos de constantes dedicados. Toda string que representa uma configuração de infraestrutura, uma mensagem exibida ao dev, ou um valor padrão do sistema deve residir em uma classe de constantes — nunca inline no código de lógica.

**Separação estrita de responsabilidades.** Cada arquivo tem uma única responsabilidade. `constants.py` nunca tem lógica. `deploy.py` nunca tem valores literais. `_cli/messages.py` é a única fonte de texto de terminal. `_cli/ui.py` é a única fonte de formatação. A separação é uma restrição de arquitetura, não uma sugestão.

**Configuração na construção, execução explícita.** O objeto de deploy é configurado inteiramente no `__init__`. O método `.deploy()` é o único método com efeito colateral — nenhuma chamada de rede, nenhuma interação com a API do Prefect ocorre antes dele ser chamado explicitamente.

**Detecção automática com override explícito.** Valores que podem ser inferidos automaticamente — URL do repositório GitHub, branch atual, entrypoint do flow — são resolvidos via introspecção Git e de função Python. Todo valor automático pode ser sobrescrito pelo dev com um valor explícito. Quando valores automáticos são utilizados, o pacote os exibe no terminal antes de executar o deploy.

**Subclasses apenas estendem via hooks, nunca reimplementam lógica.** Toda a lógica de construção, validação e execução de um deploy reside em `BaseDeploy`. Subclasses diferenciam-se apenas pelos valores default de parâmetros e pela implementação dos hooks `_build_extra_env()` e `_build_extra_job_variables()`. Reimplementar qualquer método de `BaseDeploy` em uma subclasse é uma violação desta arquitetura.

---

### 1.3 Distribuição

O pacote é distribuído publicamente no PyPI sob o nome `rbr-prefect`. A decisão de distribuição pública é intencional e segura: todos os segredos, tokens e credenciais são referenciados como blocos do Prefect — nunca armazenados no código-fonte. URLs e caminhos de infraestrutura que aparecem no código são locais à rede interna da RBR e não representam risco de segurança por si só.

O nome de importação Python é `rbr_prefect`. A versão corrente é controlada pelo `pyproject.toml` e espelhada em `rbr_prefect/__init__.py` via `bump2version`. Python requerido: `>=3.12`.

---

### 1.4 Dependências do Pacote

As dependências declaradas em `pyproject.toml` são `prefect>=3.0.0`, `prefect-github>=0.4.2`, `cron-builder` e `requirements-detector`. As três últimas são as únicas dependências externas que o pacote introduz além do próprio Prefect. `rich` e `pydantic` são utilizados mas chegam como dependências transitivas do Prefect — não precisam ser declarados. `cron-builder` provê a DSL para construção de expressões cron. `requirements-detector` provê a detecção automática de dependências Python do projeto do dev via `find_requirements()` e `from_requirements_txt()`.

As dependências de desenvolvimento — `bump2version`, `pytest`, `pytest-mock` — são declaradas no grupo `[dependency-groups] dev` e não fazem parte do pacote distribuído.

---

### 1.5 Estrutura de Diretórios

O repositório contém os seguintes componentes relevantes: `rbr_prefect/__init__.py` controla a superfície pública do pacote. `rbr_prefect/constants.py` é a fonte única de verdade para toda configuração de infraestrutura. `rbr_prefect/deploy.py` contém todas as classes de deploy e estratégias de source. `rbr_prefect/_interaction.py` é o módulo privado que resolve o modo de interação e os acks de invocação (Seção 12.4). `rbr_prefect/cron.py` é um módulo wrapper que reexporta a API pública do `cron_builder`. `rbr_prefect/blocks/` contém as definições de blocos customizados do Prefect para a RBR. `rbr_prefect/_cli/` é o submódulo privado de interface de terminal, com `messages.py` para textos e `ui.py` para formatação. O diretório `tests/` contém os testes automatizados e scripts de deploy de teste.

---

### 1.6 Separação de Responsabilidades entre Arquivos

`constants.py` é autorizado a conter valores literais de configuração e é proibido de conter lógica de negócio. A única exceção são os métodos estáticos de `RBRBlocks` que compõem strings de template do Prefect a partir das próprias constantes do arquivo.

`deploy.py` é autorizado a conter lógica e é proibido de conter valores literais — toda string, URL, nome de imagem ou parâmetro de infraestrutura deve vir de `constants.py`.

`_cli/messages.py` é autorizado a conter textos literais de terminal e factories de interpolação, e é proibido de conter lógica de apresentação.

`_cli/ui.py` é autorizado a conter lógica de formatação, prompts e prints com `rich`, e é proibido de conter qualquer texto literal — apenas referências a `messages.py`.

`_interaction.py` é autorizado a ler `sys.argv` e `os.environ` e a responder perguntas sobre o modo de interação. É proibido de imprimir, de importar qualquer coisa de `_cli`, e de tomar decisões de fluxo — não aborta, não prompta e não decide. Toda decisão baseada nas suas respostas é de `deploy.py`.

`cron.py` é exclusivamente um módulo de reexportação. Não contém lógica própria.

---

### 1.7 Fluxo de Uso pelo Dev

O fluxo típico envolve importar a classe de deploy adequada, instanciá-la com `flow_func`, `name` e `tags` obrigatórios, opcionalmente configurar parâmetros via `deploy.parameters = deploy.override(...)` e um schedule via `deploy.schedule(cron)`, e finalizar com `deploy.deploy()`. O dev nunca precisa informar: URL do GitHub, branch, entrypoint, URL da API do Prefect, credenciais de autenticação, imagem Docker, volumes ou variáveis de ambiente de infraestrutura. Tudo isso é resolvido automaticamente pelo pacote.

---

### 1.8 Fluxo de Release do Pacote

O processo de publicação é inteiramente local e sequencial: verificar que `main` está limpo e atualizado, executar `uv run pytest`, executar `bump2version patch|minor|major` (que atualiza a versão em `pyproject.toml` e `__init__.py`, cria commit e tag Git automaticamente), fazer push do commit e da tag, remover `dist/` anterior, executar `uv build`, e finalizar com `uv publish`. As credenciais do PyPI são configuradas via variável de ambiente `UV_PUBLISH_TOKEN` ou `~/.pypirc` — nunca no repositório.

---

## Seção 2 — `constants.py`

### 2.1 Papel e Princípios

`constants.py` é a fonte única da verdade para toda configuração de infraestrutura da RBR. Quando uma configuração de infraestrutura muda — nova imagem Docker, nova URL de API, novo nome de block — apenas `constants.py` precisa ser editado. O diff do PR fica isolado neste arquivo, tornando a revisão trivial e o histórico Git auditável.

O arquivo não possui lógica de negócio, com uma única exceção deliberada: os métodos estáticos de `RBRBlocks` que compõem programaticamente as strings de template do Prefect. Essa exceção existe porque hardcodar essas strings inteiras em `deploy.py` introduziria magic strings longas e frágeis — a composição programática garante que uma mudança no nome do bloco se propague automaticamente para todas as referências.

---

### 2.2 `RBRPrefectServer`

Centraliza os valores de conexão com o servidor Prefect da RBR. `API_URL` contém a URL completa da API Prefect (`https://prefect-eve.rbr.local/api`) e é injetada como variável de ambiente `PREFECT_API_URL` em todos os containers de todos os deploys. `SSL_CERT_PATH` contém o caminho do certificado TLS dentro do container Docker (`/host-certs/rbr-root-ca.crt`) — é um caminho interno ao container, não da máquina host, e corresponde ao ponto de montagem definido em `RBRDocker.CERT_VOLUME`.

---

### 2.3 `RBRDocker`

Centraliza imagens Docker e configurações de container. `DEFAULT_IMAGE` é a imagem oficial do Prefect usada por `DefaultDeploy` e `SQLDeploy`. `SCRAPE_IMAGE` é a imagem customizada da RBR com Playwright instalado, usada por `ScrapeDeploy`. `SQL_IMAGE` é a imagem customizada da RBR com drivers de SQL Server instalados, usada por `SQLDeploy`. `CERT_VOLUME` é o mapeamento de volume no formato `host_path:container_path:mode` que injeta os certificados TLS da RBR dentro do container em modo somente leitura — aplicado a todos os deploys.

---

### 2.4 `RBRWorkPools`

Centraliza os nomes dos work pools. `DEFAULT` é o work pool Docker padrão usado pelas subclasses Docker. `PROCESS` (`"windows"`) é o work pool do tipo process, usado por `ProcessDeploy`. A diferenciação entre tipos de flow Docker (HTTP, scraping, SQL) é feita pela imagem, não pelo work pool — todos usam `DEFAULT`. `KNOWN` é a tupla de pools RBR conhecidos (`DEFAULT`, `PROCESS`): o prompt de confirmação de override só dispara para pools fora dessa tupla. Um work pool alternativo pode ser fornecido em qualquer deploy, mas exige confirmação interativa via prompt.

---

### 2.5 `RBRBlocks`

Centraliza nomes de blocos e fábricas de strings de template do Prefect. `GITHUB_CREDENTIALS` é o nome do bloco `GitHubCredentials` carregado em `GitHubSourceStrategy`. `BASIC_AUTH` é o nome do bloco `BasicAuthCredentials`. Os atributos prefixados com `_` (`_BLOCK_TYPE_BASIC_AUTH`, `_AUTH_STRING_FIELD`, `_HEADER_FIELD`) são internos e usados exclusivamente pelos métodos factory.

`auth_string_template()` e `header_template()` retornam as strings de template do Prefect no formato `{{ prefect.blocks.<tipo>.<nome>.<campo> }}` para as variáveis de ambiente `PREFECT_API_AUTH_STRING` e `PREFECT_CLIENT_CUSTOM_HEADERS` respectivamente. A composição é programática — uma mudança em `BASIC_AUTH` propaga automaticamente para ambas as strings sem edição adicional.

---

### 2.6 `RBRJobVariables`

Centraliza as configurações fixas de `job_variables` aplicadas a todos os deploys. `AUTO_REMOVE = True` garante que containers Docker são removidos após execução. `IMAGE_PULL_POLICY = "IfNotPresent"` evita pull desnecessário quando a imagem já está disponível no worker.

---

### 2.7 `RBRTimeZone`

Centraliza fusos horários utilizados nos schedules. `SAO_PAULO = "America/Sao_Paulo"` é o fuso aplicado a todos os objetos `CronSchedule`, `IntervalSchedule` e `RRuleSchedule` criados por `BaseDeploy.schedule()`. Todos os schedules do pacote operam neste fuso independentemente do que o dev informe.

---

### 2.8 `RBRBaseEnvVariables`

Centraliza os nomes das variáveis de ambiente injetadas na base de todos os containers. Os atributos são strings com os nomes das variáveis: `PREFECT_API_URL`, `PREFECT_API_SSL_CERT_FILE`, `PREFECT_API_AUTH_STRING`, `PREFECT_CLIENT_CUSTOM_HEADERS` e `EXTRA_PIP_PACKAGES`. Esses nomes são referenciados exclusivamente em `BaseDeploy._build_base_env()` — nunca como strings literais em `deploy.py`.

---

### 2.9 Regra de Evolução

Sempre que uma nova configuração de infraestrutura precisar ser introduzida, o atributo deve ser adicionado na classe semântica apropriada em `constants.py` e referenciado nos arquivos de lógica. Nunca introduzir o valor literal diretamente em `deploy.py`, `ui.py` ou qualquer outro arquivo. Se nenhuma classe existente for o lar semântico correto, criar uma nova seguindo o padrão `RBR<Domínio>`.

---

## Seção 3 — `_cli/messages.py` e `_cli/ui.py`

### 3.1 Papel do Submódulo `_cli`

O submódulo `_cli` encapsula toda a interação com o terminal durante o processo de deploy. É totalmente interno ao pacote — o prefixo `_` sinaliza que nenhum de seus membros faz parte da superfície pública. Apenas `deploy.py` o consome, e apenas através do `_cli/__init__.py`, que é a única interface visível para `deploy.py`.

A divisão em dois arquivos é uma restrição arquitetural, não uma sugestão de organização: `messages.py` define o *quê* é exibido; `ui.py` define o *como* é exibido. Nenhum texto literal aparece em `ui.py`. Nenhuma lógica de formatação aparece em `messages.py`.

---

### 3.2 Convenção de `messages.py`

Cada classe de mensagens segue uma convenção de três tipos de membros. Constantes públicas em `UPPER_CASE` são strings sem interpolação, usadas diretamente em `ui.py`. Templates privados em `_UPPER_CASE` são strings com placeholders `{var}`, nunca usados diretamente fora da classe. Métodos factory públicos em `snake_case` recebem os valores de interpolação e retornam a string final — encapsulam o conhecimento dos placeholders para que `ui.py` nunca precise conhecê-los.

---

### 3.3 Classes de Mensagens

`DeployMessages` contém cabeçalhos dos painéis de auditoria (`RESOLVED_HEADER`, `OVERRIDES_HEADER`, `ENV_HEADER`), os labels de cada linha do painel (`LABEL_GITHUB_URL`, `LABEL_BRANCH`, `LABEL_ENTRYPOINT`, `LABEL_NAME`, `LABEL_PARAMETERS`, `LABEL_IMAGE`, `LABEL_REQUIREMENTS`, `LABEL_WORK_POOL`, `LABEL_TAGS`, `LABEL_SCHEDULE`), a mensagem do separador de handoff (`HANDOFF_MESSAGE`), e o factory `deploy_starting(name)`.

`WorkPoolMessages` contém o aviso exibido antes do prompt de override de work pool, a mensagem de abort, e o factory `override_confirm(pool)` para a pergunta de confirmação.

`ConcurrencyMessages` contém o aviso sobre concurrency limit, a mensagem de abort e a pergunta de confirmação.

`EnvMessages` e `JobVariablesMessages` contém cada um um aviso de override total, exibido em vermelho quando o dev usa `env_override` ou `job_variables_override`.

`ScheduleMessages` contém o aviso sobre configurações avançadas de schedule, a pergunta de confirmação e a mensagem de abort.

`ValidationMessages` contém todas as mensagens de erro lançadas como exceções: `TAGS_REQUIRED`, `REQUIREMENTS_PATH_INVALID`, `NAME_REQUIRED`, `OUTSIDE_GIT_REPO`, `NO_REMOTE_ORIGIN`, `ENTRYPOINT_OUTSIDE_REPO`, `SOURCE_FILE_NOT_FOUND`, `ENV_MUTEX`, `JOB_VARIABLES_MUTEX`, `SCHEDULE_REQUIRED`. Os templates com interpolação `_INVALID_PARAM` e `_SCHEDULE_MUTEX` são expostos via factories `invalid_param(param, flow)` e `schedule_mutex()`. O factory `acknowledge_invalid(ids, allowed)` cobre ids de ack desconhecidos (Seção 12.5).

`NonInteractiveMessages` contém os textos do relatório de confirmações pendentes: cabeçalho do painel, texto introdutório, labels da tabela e os factories que montam a instrução literal de cada pendência — `ack_instruction(ack_id)` para os acks de código, `git_instruction(ids)` para o ack escopado de git e `mode_instruction()` para a flag de modo. É a única classe de mensagens que importa de `constants.py`, pois interpola os nomes de flags e env vars de `RBRNonInteractive` nas instruções; a hierarquia `constants` → `messages` permite isso.

---

### 3.4 `_cli/__init__.py`

Expõe apenas as funções de alto nível de `ui.py`: `print_audit_panel`, `print_handoff`, `confirm_work_pool_override`, `confirm_concurrency_limit`, `confirm_advanced_schedule`, `print_pending_acks_panel`, `print_git_check_skipped` e `print_git_issues_accepted`. `messages.py` permanece invisível para fora do submódulo. `deploy.py` importa exclusivamente deste `__init__`, nunca diretamente de `ui.py` ou `messages.py`.

---

### 3.5 Lógica de `ui.py`

`ui.py` usa `rich` para toda a formatação. Uma única instância de `Console` é criada no topo do módulo com `file=sys.stdout` explícito, garantindo flush síncrono antes da passagem de responsabilidade ao Prefect.

`print_audit_panel` recebe `resolved: dict`, `overrides: dict`, `env: dict`, `env_override_active: bool` e `job_variables_override_active: bool`. Exibe o painel de valores resolvidos sempre. Exibe o painel de overrides apenas quando `overrides` não estiver vazio. Exibe painéis de aviso em vermelho quando os flags de override total estiverem ativos. Exibe o painel de env resolvido sempre. Valores de env com mais de 60 caracteres são truncados com reticências para não quebrar o layout.

`print_handoff` exibe a mensagem de início do deploy e uma `rich.Rule` horizontal como separador visual. É a última chamada a `ui.py` antes de `deployable.deploy()`.

`confirm_work_pool_override`, `confirm_concurrency_limit` e `confirm_advanced_schedule` exibem o aviso correspondente de `messages.py` e fazem a pergunta de confirmação via `rich.prompt.Confirm.ask`. Retornam `True` se confirmado, `False` se negado. Em caso negativo, exibem a mensagem de abort antes de retornar.

As funções `confirm_*` nunca decidem se devem ser chamadas: essa decisão é de `BaseDeploy` (Seção 12.6). Elas assumem terminal interativo e não consultam `_interaction` — `ui.py` não conhece o conceito de modo. Isso mantém `ui.py` como camada puramente de apresentação e concentra a política em `deploy.py`.

`print_pending_acks_panel` recebe as instruções já resolvidas como strings e as renderiza em um painel vermelho, uma por linha. Não monta texto: as instruções chegam de `NonInteractiveMessages`, preservando R2. `print_git_check_skipped` exibe `GitCheckMessages.SKIPPED` (Seção 12.9). `print_git_issues_accepted` exibe a nota de que as issues listadas foram aceitas na invocação, para que o output registre a autorização junto ao painel de issues.

---

### 3.6 Contrato de Sequência Terminal

Toda interação do `rbr-prefect` com o terminal ocorre dentro de `.deploy()`, antes da chamada a `deployable.deploy()`. A ordem é estrita: validações síncronas via exceção → prompts de confirmação (`work_pool`, `concurrency_limit`, `advanced_schedule`, cada um apenas quando aplicável) → `print_audit_panel` → `print_handoff`. O terminal não é limpo em nenhum momento. Se qualquer prompt de confirmação retornar `False`, o deploy é abortado com `SystemExit(0)` — não uma exceção, pois o abort é uma decisão do usuário, não um erro.

Cada prompt desta sequência só é exibido quando a intenção correspondente **não** foi declarada. Um ack declarado (Seção 12) suprime o prompt correspondente sem alterar a ordem dos demais, e a ausência de terminal converte o prompt em pendência reportada — nunca em prompt executado. A sequência acima permanece válida como a ordem em que as decisões são avaliadas, independentemente de cada uma resultar em prompt, em passagem silenciosa ou em pendência.

---

## Seção 4 — Source Strategy

### 4.1 Motivação

A source strategy é a abstração que responde: de onde o Prefect vai buscar o código do flow na execução? A implementação atual é sempre via GitHub com `flow.from_source()`, mas existe um caso de uso futuro onde o código estará embutido em uma imagem Docker. Para que a adição dessa segunda estratégia não exija alterações nas classes de deploy, a lógica de source é isolada em uma hierarquia própria. As classes de deploy são completamente agnósticas à estratégia — chamam `source_strategy.build()` e `source_strategy.resolve_entrypoint(flow_func)` sem conhecer a implementação.

Toda a hierarquia de source strategy reside em `deploy.py` junto às classes de deploy, pois são conceitos intimamente relacionados e não justificam arquivo separado.

---

### 4.2 `BaseSourceStrategy`

Classe base abstrata que define dois métodos obrigatórios. `build()` constrói e retorna o objeto de source esperado pelo Prefect — um `GitRepository` para `GitHubSourceStrategy`, `None` para `DockerSourceStrategy`. `resolve_entrypoint(flow_func)` retorna o entrypoint no formato `"caminho/relativo/ao/repo/flow_file.py:nome_da_funcao"`. A lógica de resolução do entrypoint é responsabilidade da estratégia porque depende intrinsecamente de onde o código reside.

---

### 4.3 `GitHubSourceStrategy`

Implementação atual e padrão. Detecta automaticamente URL do repositório, branch e raiz do repositório via chamadas `subprocess` ao CLI do `git`. Calcula o entrypoint relativo via `inspect.getfile()` e `pathlib.Path.relative_to()`. Constrói e retorna o objeto `GitRepository` do `prefect-github` com `include_submodules=True`.

O construtor aceita `github_url: str | None` e `branch: str | None`. Quando `None`, os valores são detectados automaticamente na primeira vez que forem necessários. O `_repo_root` é cacheado após a primeira detecção para evitar múltiplas chamadas ao subprocess.

A detecção de `github_url` usa `git remote get-url origin`. A detecção de `branch` usa `git rev-parse --abbrev-ref HEAD`. A detecção de `_repo_root` usa `git rev-parse --show-toplevel`.

**Atenção crítica sobre `resolve_entrypoint`:** A função flow recebida como argumento pode ser um objeto `Flow` do Prefect (resultado do decorador `@flow`), não a função Python diretamente. Para usar `inspect.getfile()` e `.__name__`, é necessário extrair a função subjacente via o atributo `.fn` do objeto `Flow`. A função helper `_get_underlying_function(flow_func)` em `deploy.py` encapsula essa lógica: se `flow_func` possui atributo `.fn`, retorna `flow_func.fn`; caso contrário, retorna `flow_func` sem modificação. `resolve_entrypoint` deve usar `_get_underlying_function` antes de qualquer introspecção.

Adicionalmente, se o arquivo resultante tiver extensão `.pyc`, deve ser normalizado para `.py` antes de tentar `relative_to()`, verificando que o `.py` correspondente existe.

As propriedades `resolved_github_url`, `resolved_branch` e `resolved_repo_root` expõem os valores resolvidos para uso pelo print de auditoria em `BaseDeploy.deploy()`.

**Tratamento de erros:** `_resolve_repo_root` e `_resolve_branch` lançam `RuntimeError` com `ValidationMessages.OUTSIDE_GIT_REPO` quando o subprocess falha. `_resolve_github_url` lança `RuntimeError` com `ValidationMessages.NO_REMOTE_ORIGIN` quando o subprocess falha. `resolve_entrypoint` lança `ValueError` com `ValidationMessages.ENTRYPOINT_OUTSIDE_REPO` quando o arquivo está fora do repositório, e `FileNotFoundError` com `ValidationMessages.SOURCE_FILE_NOT_FOUND` quando o `.py` não existe após normalização de `.pyc`.

---

### 4.4 `DockerSourceStrategy`

Esqueleto futuro. Ambos os métodos lançam `NotImplementedError` com mensagem orientativa. Não contém lógica.

---

### 4.6 Execution Strategy

Espelhando a source strategy, a **execution strategy** responde: *onde e como* o flow executa? Ela concentra as diferenças entre rodar em um container Docker e rodar como subprocesso em um worker do tipo process. Toda a hierarquia reside em `deploy.py`, junto às demais classes.

`BaseExecutionStrategy` é a classe base abstrata com três métodos obrigatórios — `base_job_variables()`, `base_env(requirements_env, dependency_mode)` e `resolve_image(image)` — e dois hooks concretos com default no-op: `validate_dependencies(repo_root, dependency_mode)` e `pre_deploy_notices()`.

`BaseDeploy` **delega** para a estratégia em `_build_base_job_variables()` e `_build_base_env()` — nunca reimplementa essa lógica. As subclasses de deploy diferenciam-se apenas pela estratégia que injetam (parâmetro `execution_strategy`, default `DockerExecutionStrategy`). Isso preserva a regra de que subclasses só fornecem defaults e estendem via hooks.

`DockerExecutionStrategy` é o comportamento padrão: `base_job_variables()` retorna `volumes`/`auto_remove`/`image_pull_policy`; `base_env()` injeta o caminho do certificado TLS dentro do container e gerencia dependências conforme `dependency_mode` (ver Seção 5.6.1); `resolve_image()` retorna a imagem fornecida; `validate_dependencies()` executa o check de pré-condição do auto-install.

`ProcessExecutionStrategy` cobre o worker process: `base_job_variables()` e `base_env()` retornam dict vazio (o worker roda em máquina do domínio RBR — CA já confiável — e já possui `PREFECT_API_URL`); `resolve_image()` retorna `None` (process pool não usa imagem); `pre_deploy_notices()` retorna o aviso de que dependências são responsabilidade do ambiente do worker.

---

### 4.5 Git Pre-Flight Check

O git pre-flight check é uma etapa de verificação executada no início de `BaseDeploy.deploy()`, antes de qualquer resolução de env ou job_variables, e antes de qualquer outro output no terminal. Seu objetivo é detectar antecipadamente estados do repositório que causariam o Prefect a buscar um código diferente do que o dev está vendo localmente — uncommitted changes, commits sem push, ou submódulos com SHAs não publicados no remote.

A verificação só é executada quando a `source_strategy` da instância é `GitHubSourceStrategy`. `DockerSourceStrategy` não executa checks de git — a etapa é completamente ignorada nesse caso, sem nenhum output adicional.

A verificação é bypassada quando a variável de ambiente `RBR_SKIP_GIT_CHECK` estiver definida com qualquer valor não-vazio. Quando o bypass está ativo, os checks de subprocess não são executados e `run_git_checks()` não é chamado; é exibida a mensagem `GitCheckMessages.SKIPPED`. Esta env var está **depreciada** em favor do ack escopado — ver Seção 12.9 para o motivo e para o comportamento anterior que foi corrigido.

O método `run_git_checks()` de `GitHubSourceStrategy` executa exatamente 5 checks em sequência. Todos os checks são sempre executados, mesmo que os anteriores tenham encontrado issues — não há short-circuit. O método retorna uma lista de objetos `GitCheckIssue`, cada um com campos `id` (identificador estável de máquina, constante de `RBRGitChecks`), `check` (label da verificação, constante de `GitCheckMessages`) e `details` (descrição legível do problema encontrado). Lista vazia significa que tudo está ok. A separação entre `id` e `check` é o que permite o ack escopado da Seção 12.2 — ver Seção 12.3.

Os 5 checks são: (1) dirty check no repositório principal via `git status --porcelain`; (2) dirty check nos submódulos via `git submodule foreach`; (3) commits não pushed no repositório principal via `git log origin/{branch}..HEAD --oneline`; (4) commits não pushed nos submódulos via `git submodule foreach` com `git log`; (5) verificação de que o SHA pinado de cada submódulo é alcançável a partir de alguma ref remota via `git branch -r --contains {sha}`.

Os checks de submódulos (2, 4 e 5) são silenciosamente omitidos quando o repositório não tem submódulos — a ausência de submódulos é verificada via `git submodule status --recursive`, e quando o output estiver vazio os três checks são pulados sem gerar nenhuma issue. Isso não é um problema — é o comportamento esperado para repositórios sem submódulos.

Falhas de subprocess inesperadas são capturadas como issues do tipo `CHECK_SUBPROCESS_ERROR` e nunca propagadas como exceções. Todos os subprocessos são chamados com `check=False`; quando `returncode != 0`, o stderr é capturado como `details` da issue. Isso garante que o deploy pode prosseguir (com confirmação do usuário) mesmo que algum check não possa ser executado por razões externas.

O resultado da verificação determina o fluxo: lista vazia exibe um painel verde com mensagem de sucesso e o deploy prossegue automaticamente; lista não-vazia exibe um painel vermelho com uma tabela contendo todas as issues encontradas e um prompt de confirmação ao dev. Se o dev negar o prompt, o deploy é abortado com `SystemExit(0)` — não uma exceção, pois é uma decisão do usuário, não um erro do programa.

Com issues encontradas, o prompt só é exibido se os ids das issues não tiverem sido aceitos na invocação. Quando **todos** os ids presentes constam em `_interaction.accepted_git_issues()`, o painel vermelho ainda é exibido — o dev e o agente precisam ver o estado do repositório de qualquer forma — mas nenhuma confirmação é pedida e o deploy prossegue. Quando resta qualquer id não aceito, o comportamento é o da Seção 12: prompt se houver terminal, pendência reportada se não houver. A cobertura é avaliada por id, não por quantidade: aceitar `dirty_main` não autoriza um `unpushed_main` que apareça na mesma execução.

---

## Seção 5 — `BaseDeploy` e `Generic[P]`

### 5.1 Papel e Responsabilidades

`BaseDeploy` é a classe central do pacote. Concentra toda a lógica de construção, validação, resolução de valores e execução de deploy. Nenhuma subclasse reimplementa lógica — subclasses apenas fornecem defaults diferentes para parâmetros e implementam os hooks `_build_extra_env()` e `_build_extra_job_variables()`.

---

### 5.2 `Generic[P]` e Tipagem

`BaseDeploy` é parametrizada pelo `ParamSpec` `P` da função flow fornecida no `__init__`. `P = ParamSpec("P")` é declarado no módulo. A classe é declarada como `BaseDeploy(Generic[P])`. O parâmetro `flow_func` tem tipo `Callable[P, Any]`. O `P` é capturado implicitamente pelo Pylance na instanciação, e a partir daí `override(**kwargs: P.kwargs)` oferece autocomplete com os parâmetros reais da função flow.

---

### 5.3 Parâmetros do Construtor

Os parâmetros obrigatórios são `flow_func: Callable[P, Any]`, `name: str` e `tags: list[str]`. `flow_func` é a função decorada com `@flow`; base para introspecção de entrypoint, parâmetros e tipagem. `name` é o nome do deploy no Prefect, sobrescritável no momento do `.deploy(name=...)`. `tags` requer no mínimo uma tag — lançar `ValueError` com `ValidationMessages.TAGS_REQUIRED` quando a lista estiver vazia.

Os parâmetros de source são `source_strategy: BaseSourceStrategy | None = None`, `github_url: str | None = None`, `branch: str | None = None` e `entrypoint: str | None = None`. Quando `source_strategy` é `None`, instanciar `GitHubSourceStrategy(github_url=github_url, branch=branch)`. Quando `entrypoint` é `None`, chamar `source_strategy.resolve_entrypoint(flow_func)`.

O parâmetro `requirements_source: Path | str | None = None` controla a detecção de dependências Python. Quando `None`, tentativa de detecção automática via `find_requirements(Path.cwd())` do `requirements_detector`. Quando fornecido como `str`, converter para `Path`. Quando fornecido como `Path`, usar `from_requirements_txt(path)` diretamente. Se o path fornecido não existir, lançar `ValueError` com `ValidationMessages.REQUIREMENTS_PATH_INVALID`.

Os parâmetros de infraestrutura são `image: str = RBRDocker.DEFAULT_IMAGE` e `work_pool_name: str = RBRWorkPools.DEFAULT`. Override de `work_pool_name` exige confirmação no `__init__` — via prompt interativo ou via ack declarado (Seção 12.5).

`acknowledge: list[str] | None = None` declara no código quais confirmações de intenção de configuração já estão autorizadas, dispensando o prompt correspondente. Ids aceitos são os de `RBRAcknowledgements`; ids desconhecidos lançam `ValueError`. Ver Seção 12.5.

Os parâmetros de customização de `job_variables` são `extra_job_variables: dict[str, Any] | None = None` e `job_variables_override: dict[str, Any] | None = None`. São mutuamente exclusivos — fornecer ambos lança `ValueError` com `ValidationMessages.JOB_VARIABLES_MUTEX`. O mesmo padrão se aplica ao env: `extra_env: dict[str, str] | None = None` e `env_override: dict[str, str] | None = None` são mutuamente exclusivos via `ValidationMessages.ENV_MUTEX`.

`concurrency_limit: int | None = None` quando fornecido exige confirmação no `__init__` — via prompt interativo ou via ack declarado (Seção 12.5).

---

### 5.4 Sequência de Inicialização

A ordem de operações no `__init__` é estrita e deve ser preservada: (1) validar tags, (2) validar mutex de `job_variables`, (3) validar mutex de `env`, (3b) validar `dependency_mode`, (3c) validar e armazenar `acknowledge`, (4) confirmação para `work_pool_name` não-padrão, (5) confirmação para `concurrency_limit` fornecido, (5b) reportar pendências acumuladas de (4) e (5), (6) instanciar `source_strategy`, (7) resolver `_entrypoint`, (8) extrair parâmetros default via `inspect.signature`, (9) armazenar todos os atributos. Os prompts ocorrem na construção — não no `.deploy()` — para que o dev veja os avisos antes de qualquer processamento adicional.

O passo (3c) precede necessariamente (4) e (5), pois `_resolve_config_ack` consulta `self._acknowledge`. O passo (5b) existe para que as duas confirmações de configuração visíveis no `__init__` sejam reportadas em uma única execução quando ambas estiverem pendentes — sem ele, um agente descobriria uma pendência por execução. `advanced_schedule` não participa deste acúmulo: é avaliado em `.schedule()`, que é uma chamada posterior e separada, e reporta sua própria pendência.

`_extract_default_parameters(flow_func)` usa `_get_underlying_function` antes de chamar `inspect.signature`, e retorna apenas parâmetros que possuem valor default (ignora `inspect.Parameter.empty`). O resultado é o valor inicial de `self._parameters`.

---

### 5.5 Método `override()`

`override(**kwargs: P.kwargs)` retorna um dicionário resultante do merge dos defaults extraídos com os kwargs fornecidos. Chama `_validate_parameter_keys` antes de retornar. `_validate_parameter_keys` extrai as chaves válidas da assinatura da função flow via `_get_underlying_function` + `inspect.signature`, calcula `invalid_keys = set(overrides.keys()) - valid_keys`, e lança `ValueError` com `ValidationMessages.invalid_param(key, func_name)` para cada chave inválida.

O atributo `parameters` é uma `property` com getter e setter. O setter chama `_validate_parameter_keys` antes de armazenar o valor. O padrão de uso é `deploy.parameters = deploy.override(country_name="Argentina")` — `override()` faz o merge sobre os defaults e o setter valida antes de armazenar.

---

### 5.6 Resolução de Requirements — `_resolve_requirements()`

Este método popula `self._requirements` (lista de strings) e `self._requirements_env` (string com todos os requirements separados por espaço) para uso em `_build_base_env()`. É chamado dentro de `_resolve_env()`, não no `__init__`.

Quando `self._requirements_source` é `None`, tentar `find_requirements(Path.cwd())` do `requirements_detector`. Se lançar `RequirementsNotFound`, não fazer nada — flows sem requirements são válidos. Quando `self._requirements_source` é um `Path` existente, usar `from_requirements_txt(self._requirements_source)`. Os objetos retornados pelo `requirements_detector` são convertidos para string via `str(r)`. A `_requirements_env` é a join dos strings com espaço simples.

A detecção de requirements alimenta o painel informativo em todos os modos; a *injeção* de `EXTRA_PIP_PACKAGES` ocorre apenas no modo `pip_packages` (ver 5.6.1).

---

### 5.6.1 Gestão de Dependências — `dependency_mode`

O parâmetro `dependency_mode: str = RBRDependencyMode.AUTO_INSTALL` (presente em `BaseDeploy` e nas subclasses Docker) controla como as dependências Python chegam ao ambiente de execução. É validado no `__init__` contra `RBRDependencyMode.ALL`, lançando `ValueError` via `ValidationMessages.dependency_mode_invalid()` para valores inválidos.

`AUTO_INSTALL` (default) injeta `PREFECT_RUNNER_AUTO_INSTALL_DEPENDENCIES=true`, fazendo o runner do Prefect instalar via `uv`, em runtime, as dependências de `[project].dependencies` do `pyproject.toml` do repositório clonado. Não injeta `EXTRA_PIP_PACKAGES`. Como o auto-install falha silenciosamente em runtime quando suas pré-condições não são satisfeitas, `DockerExecutionStrategy.validate_dependencies()` faz um **check de pré-condição read-only no `.deploy()`**: lê o `pyproject.toml` da raiz do repositório via `tomllib` e lança `ValueError` (`PYPROJECT_NOT_FOUND` ou `PREFECT_NOT_IN_PYPROJECT`) se o arquivo não existir ou não listar `prefect`. O check espelha exatamente a condição que o Prefect verifica — não há falso positivo.

`PIP_PACKAGES` preserva o comportamento legado: injeta `EXTRA_PIP_PACKAGES` a partir dos requirements detectados (compatível com `requirements.txt`), processado pelo entrypoint da imagem Docker do Prefect. Não injeta a variável de auto-install nem executa o check de pré-condição.

`ProcessDeploy` **não expõe** `dependency_mode` (nem `image`): deploys process não gerenciam dependências — elas devem estar pré-instaladas no ambiente do worker, e a `ProcessExecutionStrategy` exibe um aviso no deploy. Passar `dependency_mode` a `ProcessDeploy` resulta em `TypeError` natural do Python.

**Atenção:** mudar o default para `AUTO_INSTALL` é uma alteração de comportamento dos deploys Docker — incrementa a versão MAJOR. Flows que dependiam da injeção automática de `requirements.txt` devem migrar para `pyproject.toml` (com `prefect`) ou passar `dependency_mode=RBRDependencyMode.PIP_PACKAGES`.

---

### 5.7 Resolução de `job_variables` — `_resolve_job_variables()`

Quando `self._job_variables_override` não é `None`, retornar diretamente sem merge — bypass total. Caso contrário, fazer merge em três camadas: `_build_base_job_variables()` (invariante RBR) → `_build_extra_job_variables()` (hook da subclasse) → `self._extra_job_variables` (adições do dev). Após o merge, injetar `env` como chave separada via `_resolve_env()`. O `env` é sempre resolvido separadamente e injetado por último para garantir que nunca seja sobrescrito acidentalmente por `extra_job_variables`.

`_build_base_job_variables()` em `BaseDeploy` **delega** para `execution_strategy.base_job_variables()`. Na `DockerExecutionStrategy`, retorna o dict com `volumes: [RBRDocker.CERT_VOLUME]`, `auto_remove: RBRJobVariables.AUTO_REMOVE` e `image_pull_policy: RBRJobVariables.IMAGE_PULL_POLICY`; na `ProcessExecutionStrategy`, retorna dict vazio. O método em `BaseDeploy` nunca é sobrescrito pelas subclasses — a variação vem da estratégia injetada.

`_build_extra_job_variables()` em `BaseDeploy` retorna dict vazio. É o hook para subclasses.

---

### 5.8 Resolução de `env` — `_resolve_env()`

Quando `self._env_override` não é `None`, retornar diretamente — bypass total inclusive do env base RBR. Caso contrário, chamar `_resolve_requirements()` e então fazer merge em três camadas: `_build_base_env()` → `_build_extra_env()` → `self._extra_env`. A hierarquia de precedência é crescente: base RBR → subclasse → dev.

`_build_base_env()` em `BaseDeploy` **delega** para `execution_strategy.base_env(self._requirements_env, self._dependency_mode)`. A `DockerExecutionStrategy` injeta o caminho do certificado TLS e, conforme `dependency_mode`, a variável de auto-install ou `EXTRA_PIP_PACKAGES` (ver 5.6.1); a `ProcessExecutionStrategy` retorna dict vazio. O método em `BaseDeploy` nunca é sobrescrito pelas subclasses.

`_build_extra_env()` em `BaseDeploy` retorna dict vazio. É o hook para subclasses.

---

### 5.9 Descrição Automática — `_build_description()`

Gera a descrição do deploy combinando: nome da função flow, URL do repositório GitHub, branch, entrypoint, URL direta ao arquivo no GitHub no formato `{github_url_sem_git}/blob/{branch}/{file_path}`, e versão do pacote `rbr-prefect` via `importlib.metadata.version("rbr-prefect")`. A versão na descrição é de rastreabilidade — permite saber ao inspecionar um deploy no Prefect UI qual versão da lógica foi usada.

---

### 5.10 Invariante de Efeitos Colaterais

Apenas `.deploy()` tem efeitos colaterais. O `__init__` não faz chamadas de rede (prompts de terminal são interações locais). `.schedule()` apenas armazena o objeto de schedule em `self._schedule`. `GitHubCredentials.load()` é chamado apenas dentro de `.deploy()` quando `source_strategy.build()` é invocado. `_resolve_env()` e `_resolve_job_variables()` são chamados dentro de `.deploy()`, não na construção.

---

## Seção 6 — Subclasses de Deploy

### 6.1 Princípio de Design das Subclasses

As subclasses `DefaultDeploy`, `SQLDeploy` e `ScrapeDeploy` herdam integralmente de `BaseDeploy[P]`. Cada uma replica a assinatura completa do `__init__` de `BaseDeploy` alterando apenas os valores default dos parâmetros que divergem, e delega integralmente para `super().__init__()`. O valor semântico das subclasses é de nomeação e descoberta — o dev lê `ScrapeDeploy` e entende o contexto de uso sem consultar defaults.

Nenhuma subclasse reimplementa `_resolve_job_variables`, `_resolve_env`, `override`, `schedule` ou `deploy`. A única extensão permitida é via hooks `_build_extra_env()` e `_build_extra_job_variables()`.

---

### 6.2 `DefaultDeploy`

Deploy padrão para flows de coleta de dados via HTTP, processamento e transformação. O único diferencial em relação a `BaseDeploy` é que `image` tem default `RBRDocker.DEFAULT_IMAGE` explicitamente declarado na assinatura. Não sobrescreve nenhum hook.

---

### 6.3 `SQLDeploy`

Deploy para flows que precisam de drivers de conexão com SQL Server. O único diferencial em relação a `DefaultDeploy` é que `image` tem default `RBRDocker.SQL_IMAGE`. Não sobrescreve nenhum hook. É adequado para flows que buscam ou submetem dados ao banco RBR.

---

### 6.4 `ScrapeDeploy`

Deploy para flows que utilizam Playwright para automação de navegador. Diferencia-se em um aspecto: `image` tem default `RBRDocker.SCRAPE_IMAGE`. Importante: `_build_extra_env()` retorna o mesmo dict que os outros deploys. O dev que usa `ScrapeDeploy` não precisa conhecer nem fornecer essas variáveis — são responsabilidade da classe.

---

### 6.4.1 `ProcessDeploy`

Deploy para flows que rodam em um worker do tipo **process** — o worker executa o flow como subprocesso no próprio ambiente Python, sem container Docker. Mantém a `GitHubSourceStrategy` (código continua vindo do GitHub) mas injeta `ProcessExecutionStrategy`. Diferencia-se das subclasses Docker por: usar default `work_pool_name=RBRWorkPools.PROCESS`; **não expor** os parâmetros `image` e `dependency_mode` (dependências são responsabilidade do worker); resolver `image` como `None`; e exibir um aviso no deploy via `pre_deploy_notices()`. Por injetar uma `execution_strategy` diferente — e não reimplementar lógica — permanece em conformidade com o princípio de design das subclasses.

---

### 6.5 Adição de Futuras Subclasses

O padrão é: herdar de `BaseDeploy[P]`, replicar a assinatura completa do `__init__` alterando apenas valores default, delegar integralmente para `super().__init__()`, sobrescrever hooks se necessário, nunca reimplementar lógica de `BaseDeploy`. A tabela comparativa das subclasses existentes: `DefaultDeploy` usa `DEFAULT_IMAGE`, sem hooks extras; `SQLDeploy` usa `SQL_IMAGE`, sem hooks extras; `ScrapeDeploy` usa `SCRAPE_IMAGE`, sobrescreve `_build_extra_env()` com variáveis do Playwright.

---

## Seção 7 — `cron.py` e Builder Pattern

### 7.1 `cron.py` — Módulo Wrapper

`cron.py` é exclusivamente um módulo de reexportação. Importa `CronBuilder`, `Weekday` e `Month` do pacote `cron_builder` e os reexporta via `__all__`. Não contém lógica própria. O propósito é dar ao dev um ponto de importação estável dentro do namespace `rbr_prefect` (`from rbr_prefect.cron import CronBuilder`) sem acoplamento direto ao nome do pacote externo.

A API do `cron_builder` para os casos de uso mais comuns: `CronBuilder().on_weekdays().at_hour(9)` para dias úteis às 9h, `CronBuilder().on_day_of_month(1).at_hour(23)` para dia 1 do mês às 23h, `CronBuilder().on_weekdays().every_minutes(30)` para a cada 30 minutos em dias úteis. O objeto resultante é convertido para string cron via `str(cron_builder_instance)`.

---

### 7.2 Método `.schedule()`

`.schedule()` aceita `cron: CronBuilder | str | None = None` como parâmetro posicional, e `interval: datetime.timedelta | None = None` e `rrule: str | None = None` como keyword-only. Retorna `self` para encadeamento.

Exatamente um dos três parâmetros deve ser fornecido. Nenhum lança `ValueError` com `ValidationMessages.SCHEDULE_REQUIRED`. Mais de um lança `ValueError` com `ValidationMessages.schedule_mutex()`. `interval` e `rrule` são configurações avançadas e exigem confirmação interativa via `confirm_advanced_schedule()`. `cron` não exige confirmação — é a interface padrão.

Para `cron`, o objeto deve ser do tipo `CronBuilder` (convertido para string via `str(cron)`) ou `str` (usado diretamente). Qualquer outro tipo lança `TypeError`. O objeto `CronSchedule` é criado com a string cron e `timezone=RBRTimeZone.SAO_PAULO`.

Para `interval`, criar `IntervalSchedule(interval=interval, timezone=RBRTimeZone.SAO_PAULO)`. Para `rrule`, criar `RRuleSchedule(rrule=rrule, timezone=RBRTimeZone.SAO_PAULO)`. Os imports são de `prefect.client.schemas.schedules`.

---

### 7.3 Método `.deploy()`

`.deploy(name: str | None = None)` é o único método com efeitos colaterais do pacote. `name` sobrescreve o nome definido na construção quando fornecido.

A sequência interna é estrita. Primeiro, resolver `env` via `_resolve_env()` e `job_variables` via `_resolve_job_variables()` — ambos chamados uma única vez e armazenados em variáveis locais. Segundo, construir o dict `resolved` com os valores automaticamente detectados para o painel de auditoria. Terceiro, construir o dict `overrides` com os valores explicitamente fornecidos pelo dev (parâmetros não-padrão, `requirements_source` explícito). Quarto, chamar `print_audit_panel(resolved, overrides, env, env_override_active, job_variables_override_active)`. Quinto, chamar `print_handoff(deploy_name)`. Sexto, construir `deployable` via `self._flow_func.from_source(source=self._source_strategy.build(), entrypoint=self._entrypoint)`. Sétimo, chamar `deployable.deploy(...)` com todos os parâmetros resolvidos.

O `deployable.deploy()` recebe: `name=deploy_name`, `work_pool_name=self._work_pool_name`, `image=self._image`, `build=False`, `push=False`, `job_variables=job_variables`, `parameters=self._parameters`, `description=self._build_description()`, `tags=self._tags`, `schedules=[self._schedule] if self._schedule else []`, `concurrency_limit=self._concurrency_limit`.

`build=False` e `push=False` são sempre fixos — a responsabilidade de build e push da imagem é externa ao pacote. As imagens são gerenciadas no registry da RBR independentemente.

---

## Seção 8 — `__init__.py` e Superfície Pública

### 8.1 Topo do Pacote

`rbr_prefect/__init__.py` exporta `DefaultDeploy`, `SQLDeploy` e `ScrapeDeploy` importados de `rbr_prefect.deploy`, e `__version__` como string. O `__all__` lista esses quatro nomes. `BaseDeploy`, `GitHubSourceStrategy` e `DockerSourceStrategy` não são exportados no topo mas são importáveis via `rbr_prefect.deploy` para uso avançado.

`__version__` em `__init__.py` é sincronizado com `pyproject.toml` via `bump2version`. A versão também é acessível via `importlib.metadata.version("rbr-prefect")` sem importar o pacote — padrão usado em `_build_description()`. Ambas as formas devem sempre retornar o mesmo valor; a sincronização é garantida pela configuração do `bump2version`.

---

### 8.2 Dois Níveis de Acesso

O pacote diferencia deliberadamente dois níveis de acesso. Acesso direto via `from rbr_prefect import DefaultDeploy` — zero fricção para o caso de uso principal. Acesso por submódulo via `from rbr_prefect.constants import RBRDocker` — requer import explícito adicional, comunicando que o dev está acessando detalhes de infraestrutura.

As classes de `constants.py` não são reexportadas em `__init__.py`. Quando um dev importa uma constante, está tomando uma decisão consciente de referenciar um valor de infraestrutura para fazer um override explícito. O import adicional torna essa intenção visível no código.

---

### 8.3 Submódulo `_cli` é Totalmente Privado

O prefixo `_` no nome do diretório é a sinalização convencional de que o conteúdo não faz parte da API pública. Imports de `rbr_prefect._cli` por código externo ao pacote são proibidos. `deploy.py` importa de `rbr_prefect._cli` (o `__init__.py` do submódulo) — nunca de `rbr_prefect._cli.ui` ou `rbr_prefect._cli.messages` diretamente.

---

## Seção 9 — Blocks

### 9.1 Papel dos Blocks

O subdiretório `rbr_prefect/blocks/` contém definições de blocos customizados do Prefect para a RBR. Esses blocos são registrados no servidor Prefect via `prefect block register` e carregados em flows via `Block.load(nome)`. O `blocks/__init__.py` exporta todos os blocos publicamente: `BasicAuthCredentials`, `GenericCredentials`, `MongoDBCredentials` e `DBCredentials`.

---

### 9.2 `BasicAuthCredentials`

Bloco para autenticação HTTP Basic Auth. Armazena credenciais em dois modelos aninhados: `UserCredentials` (com `username: str` e `password: SecretStr`) e `TokenConfig` (com `auth_string: SecretStr` no formato `usuario:senha` e `header: SecretStr` com o JSON do header Authorization já codificado em Base64). O dev preenche todos os campos manualmente — o bloco armazena os valores pré-calculados, não os calcula.

---

### 9.3 `GenericCredentials`

Bloco simplificado para autenticação com login e senha em qualquer sistema. Campos: `login: str` e `password: SecretStr`.

---

### 9.4 `DBCredentials`

Substituto para o bloco `DatabaseCredentials` do `prefect-sqlalchemy` (tornado obsoleto). Armazena credenciais e parâmetros de conexão para bancos relacionais via SQLAlchemy, mas **não** cria engines nem gerencia conexões. Organizado em quatro modelos aninhados que geram seções visuais na Prefect UI: `SQLAlchemyConnection` (driver, host, porta), `SQLAlchemyDatabase` (nome do banco), `SQLAlchemyAuth` (username, password), `SQLAlchemyAdvanced` (url de override, query dict, connect_args dict).

O método público `get_url()` retorna uma `sqlalchemy.engine.URL` pronta para uso. Quando `advanced.url` está preenchido, usa diretamente via `make_url`. Quando não está, constrói via `URL.create()` com os campos individuais — `driver` e `database` são obrigatórios neste caso. Fornecer `advanced.url` e campos individuais simultaneamente lança `ValueError`. `get_url_string(hide_password=True)` retorna a URL como string com senha opcionalmente ocultada. `is_async()` indica se o driver é assíncrono via verificação contra `AsyncDriver` enum.

---

### 9.5 `MongoDBCredentials`

Credenciais e parâmetros de conexão para MongoDB via MongoEngine. Organizado em três modelos aninhados: `MongoDBConnection` (host, porta), `MongoDBAuth` (username, password, authentication_source, authentication_mechanism), `MongoDBAdvanced` (replicaset, tls, uuid_representation). O método `get_connect_kwargs()` retorna o dict de parâmetros pronto para `mongoengine.connect()`.

---

## Seção 10 — Distribuição e Versionamento

### 10.1 Ferramentas e Fluxo

O processo de publicação é local e manual, sem CI/CD. As ferramentas são `bump2version` (atualiza versão em `pyproject.toml` e `rbr_prefect/__init__.py`, cria commit Git e tag automaticamente), `uv build` (constrói `.whl` e `.tar.gz` em `dist/`) e `uv publish` (publica no PyPI).

A configuração do `bump2version` reside no `pyproject.toml` com dois targets de arquivo: `pyproject.toml` buscando `version = "{current_version}"` e `rbr_prefect/__init__.py` buscando `__version__ = "{current_version}"`. Ambos são atualizados atomicamente em um único commit.

---

### 10.2 Critérios de Versionamento

O pacote segue Semantic Versioning estritamente. `patch` para correção de bugs sem impacto na interface pública ou atualização de constante de infraestrutura sem mudança de interface. `minor` para nova funcionalidade compatível com versões anteriores — nova subclasse, novo parâmetro opcional, novo bloco. `major` para mudanças que quebram compatibilidade — renomear classe, remover parâmetro, alterar comportamento de método existente. Mudanças em `constants.py` que alterem valores de configuração são `patch` apenas se a interface das classes de deploy não mudar.

---

### 10.3 Verificação Pós-Publicação

Após `uv publish`, verificar disponibilidade via `pip index versions rbr-prefect` e instalar em ambiente limpo para smoke test via `python -c "import rbr_prefect; print(rbr_prefect.__version__)"`.

---

### 10.4 Instalação pelos Devs

Devs adicionam o pacote via `uv add rbr-prefect` ou `pip install rbr-prefect`. É recomendado fixar versão mínima no `pyproject.toml` do projeto de flow com `rbr-prefect>=<versao_atual>` para garantir reproducibilidade.

---

## Seção 11 — Testes

### 11.1 Critério de Aceite

O critério de aceite para v0.1.0 é a execução bem-sucedida do script `tests/simple-flow-source-gh/deploy_flow_country_rbr.py` contra o servidor Prefect real em `prefect-eve.rbr.local`. Esse script instancia `DefaultDeploy` com o `flow_country` e executa `.deploy()` — o deploy deve aparecer registrado na UI do Prefect com todos os valores de infraestrutura corretos.

### 11.2 Estrutura de Testes

Os testes automatizados em `tests/` cobrem validações síncronas do `__init__` (tags vazias, mutex de env/job_variables, parâmetros inválidos), a resolução de requirements com e sem `requirements_source`, a resolução de `job_variables` e `env` nas três camadas de merge, e a integração do `cron.py` com `BaseDeploy.schedule()`. Testes de integração contra o servidor Prefect real são manuais via os scripts em `tests/simple-flow-source-gh/`.
---

## Seção 12 — Modo Não-Interativo e Acknowledgements

### 12.1 Motivação e Princípio

Os prompts de confirmação do pacote são um recurso deliberado: o `rbr-prefect` acompanha o dev passo a passo e pergunta antes de aceitar uma configuração incomum ou um estado de repositório arriscado. O problema é que um prompt só pode ser respondido por quem está em um terminal interativo — o que impede o uso do pacote por agentes de IA e por qualquer automação (CI, cron, pipeline).

A solução **não** é uma flag global que aprova tudo. O prompt não é um obstáculo a ser removido: ele é o *fallback* para quando a intenção não foi declarada. Declarar a intenção é o que dispensa a pergunta.

O princípio que governa toda esta seção é uma regra única, aplicada a cada decisão individualmente:

> **Se a intenção está declarada, roda. Se não está, pergunta. Se não pode perguntar, falha dizendo exatamente o que declarar.**

Isso preserva integralmente a experiência do dev humano — quem não declara nada continua sendo acompanhado prompt a prompt, como antes — e ao mesmo tempo torna o deploy executável de forma autônoma, sem nunca inferir uma autorização que ninguém deu.

### 12.2 Dois Tipos de Decisão, Dois Lugares de Declaração

As confirmações do pacote não são todas da mesma natureza, e por isso não se declaram no mesmo lugar.

**Intenção de configuração** — `work_pool_override`, `concurrency_limit` e `advanced_schedule`. São decisões sobre o *conteúdo do deploy*, permanentes por natureza: se o flow precisa de `concurrency_limit=1`, precisa em toda execução do script. A declaração é permanente e mora **no código**, no parâmetro `acknowledge` do construtor, ao lado do parâmetro que ela justifica. Fica no diff, é revisável em code review, e persiste junto com a configuração que autoriza.

**Estado do mundo** — as issues do git pre-flight check. Não são uma decisão sobre o deploy; são um fato sobre o repositório no instante da execução, e mudam a cada deploy. A declaração é efêmera e mora **na invocação** (flag de `sys.argv` ou variável de ambiente), nunca no código. A razão é concreta: um ack de estado commitado no script desligaria a verificação permanentemente para todos os deploys futuros daquele flow — exatamente o oposto do que a verificação existe para fazer.

O ack de estado é ainda **escopado por id**: quem aceita precisa nomear quais issues aceitou. Se um check de outra classe passar a falhar, o deploy falha mesmo com o ack presente, porque essa issue não foi vista por ninguém. Esta é a diferença essencial em relação a um bypass: `RBR_SKIP_GIT_CHECK` não roda os checks; o ack escopado roda todos e exige que o resultado seja nomeado.

A confirmação final (`confirm_deploy`) não recebe ack próprio. Ela não carrega informação nova — apenas oferece um momento de revisão dos painéis já impressos. A própria declaração de modo não-interativo é o que a dispensa.

### 12.3 Constantes

Três classes de dados puros em `constants.py` sustentam o modelo. Nenhuma contém lógica.

`RBRAcknowledgements` define os ids dos acks de intenção de configuração: `WORK_POOL_OVERRIDE = "work_pool_override"`, `CONCURRENCY_LIMIT = "concurrency_limit"`, `ADVANCED_SCHEDULE = "advanced_schedule"`, e a tupla `ALL` com os três. São valores públicos — o dev os digita no parâmetro `acknowledge`, seja como string literal ou via a constante.

`RBRGitChecks` define os ids estáveis dos checks do git pre-flight: `DIRTY_MAIN`, `DIRTY_SUBMODULES`, `UNPUSHED_MAIN`, `UNPUSHED_SUBMODULES`, `SUBMODULE_PINS`, `SUBPROCESS_ERROR`, e a tupla `ALL`. A separação em relação a `GitCheckMessages` é deliberada e segue R1/R2: o **id** é um identificador de máquina, parte do contrato de invocação, e mora em `constants.py`; o **label** é texto exibido ao dev, em português, e mora em `messages.py`. Cada `GitCheckIssue` carrega os dois.

`RBRNonInteractive` define o contrato de invocação: `FLAG_NON_INTERACTIVE = "--rbr-non-interactive"`, `FLAG_ACCEPT_GIT_ISSUES = "--rbr-accept-git-issues"`, `ENV_NON_INTERACTIVE = "RBR_PREFECT_NON_INTERACTIVE"`, `ENV_ACCEPT_GIT_ISSUES = "RBR_PREFECT_ACCEPT_GIT_ISSUES"`, o prefixo `FLAG_PREFIX = "--rbr-"`, o separador `ID_SEPARATOR = ","` e `EXIT_CODE = 2`.

### 12.4 `_interaction.py` — Resolução do Modo

Um novo módulo privado `rbr_prefect/_interaction.py` resolve o modo de interação e os acks de invocação. Depende exclusivamente de `constants.py`, não importa nada de `_cli` e não contém nenhuma decisão de fluxo — apenas responde perguntas. A hierarquia de dependências do pacote passa a ser: `constants` → `messages` → `ui` → `deploy`, com `_interaction` dependendo apenas de `constants` e sendo consumido por `deploy`.

O módulo lê `sys.argv` e `os.environ`; ambas são leituras, portanto não violam R3.

`non_interactive_declared()` retorna `True` quando a flag `--rbr-non-interactive` está presente em `sys.argv` ou quando a env var correspondente está definida com valor não-vazio.

`can_prompt()` retorna `True` apenas quando `sys.stdin.isatty()` e o modo não-interativo **não** foi declarado. É a única função consultada por `deploy.py` para decidir entre tentar perguntar e reportar.

`can_prompt()` é uma heurística, não uma garantia — ver Seção 12.4.1.

### 12.4.1 `isatty()` Não é Suficiente — o Backstop de `EOFError`

`sys.stdin.isatty()` mente em ambientes reais dos devs da RBR. Verificado em Windows com Git Bash e o stdin redirecionado (`python script.py < /dev/null`): `isatty()` retorna `True`, o prompt é impresso, e a leitura estoura `EOFError`. O mesmo padrão aparece em alguns runners de CI.

Se o pacote confiasse apenas em `isatty()`, o ambiente de um agente rodando exatamente esse shell voltaria a quebrar com traceback — o problema que esta seção inteira existe para resolver.

Por isso `deploy.py` nunca chama uma função `confirm_*` diretamente. Toda pergunta passa por `_ask(prompt_fn)`, que retorna `True`/`False` conforme a resposta e `None` quando a pergunta não pôde ser feita — seja porque `can_prompt()` já era falso, seja porque a leitura estourou `EOFError`. Um `EOFError` leva exatamente à mesma conclusão da ausência de terminal: reportar a pendência.

O teste autoritativo de "posso perguntar?" é a leitura funcionar ou não. `can_prompt()` serve para evitar imprimir um prompt que já se sabe inútil; `_ask` garante a correção quando `can_prompt()` errou. Ambos são necessários: sem o primeiro, todo deploy autônomo imprimiria prompts órfãos; sem o segundo, o pacote quebraria nos ambientes onde `isatty()` mente.

Consequência visual aceita: quando `isatty()` mente, a linha do prompt aparece no output antes do relatório de pendências. É ruído inevitável — o pacote não pode saber que a leitura falharia antes de tentar.

`accepted_git_issues()` retorna o conjunto de ids aceitos na invocação. `sys.argv` tem precedência sobre a env var — quando a flag está presente, a env var é integralmente ignorada, sem união entre as fontes.

A leitura de `sys.argv` é deliberadamente tolerante: o módulo procura apenas argumentos com o prefixo `--rbr-`, aceita as formas `--flag=valor` e `--flag valor`, e nunca valida, consome ou reclama do restante do `argv`. Isso permite que um script de deploy tenha seu próprio `argparse` sem colisão. O prefixo `--rbr-` não é cosmético: é o que garante essa convivência.

O motivo de a flag de `argv` ser o caminho primário e a env var apenas fallback é ambiental. Os devs da RBR rodam em Windows/PowerShell, onde não existe prefixo inline de variável de ambiente (`VAR=x cmd` é bashismo). Via env var, o ack seria definido com `$env:RBR_PREFECT_ACCEPT_GIT_ISSUES = "..."` e **persistiria pelo resto da sessão do shell**, vazando silenciosamente para todos os deploys seguintes — precisamente o vazamento de escopo que o ack escopado existe para evitar. A flag de `argv` é efêmera por construção.

### 12.5 Parâmetro `acknowledge`

`BaseDeploy.__init__` e as quatro subclasses públicas recebem `acknowledge: list[str] | None = None`. `None` e lista vazia são equivalentes: nenhuma intenção declarada.

Ids desconhecidos lançam `ValueError` com `ValidationMessages.acknowledge_invalid(...)`, listando os valores aceitos. Isto é intencional e não é um detalhe: o `acknowledge` existe para capturar erro de digitação e alucinação de agente, e um id silenciosamente ignorado destruiria essa propriedade. Ids repetidos são aceitos sem erro (normalizados para conjunto).

Declarar um ack que não é necessário — por exemplo `acknowledge=["concurrency_limit"]` sem passar `concurrency_limit` — não é erro. O ack autoriza uma confirmação; se ela não é acionada, nada acontece.

### 12.6 Resolução de uma Confirmação de Configuração

`BaseDeploy._resolve_config_ack(ack_id, prompt_fn)` concentra a regra da Seção 12.1 para os três acks de configuração. Retorna uma lista: vazia quando a confirmação está autorizada, ou `[ack_id]` quando está pendente.

A ordem de avaliação é estrita. Primeiro, se `ack_id` está em `self._acknowledge`, retorna lista vazia sem imprimir nada — a intenção está declarada, não há o que perguntar. Senão, chama `_ask(prompt_fn)` (Seção 12.4.1): `True` retorna lista vazia; `False` aborta com `SystemExit(0)` (decisão do usuário, comportamento idêntico ao anterior); `None` — não foi possível perguntar — retorna `[ack_id]` como pendente, sem abortar. O chamador acumula as pendências e reporta todas de uma vez.

`self._acknowledge` precisa estar populado antes da primeira chamada, o que fixa sua posição na sequência de inicialização (Seção 5.4).

### 12.7 Relatório de Pendências e Códigos de Saída

Quando há pendências, `_abort_pending(ack_ids, git_issue_ids)` imprime o painel de confirmações pendentes e encerra com `SystemExit(RBRNonInteractive.EXIT_CODE)`.

O código de saída `2` é deliberadamente diferente do `SystemExit(0)` usado nos aborts por negação de prompt, e a distinção é semântica: `0` significa que uma pessoa viu a pergunta e respondeu não — o programa fez seu trabalho. `2` significa que o programa se recusou a prosseguir porque uma autorização necessária não existe. Um agente precisa distinguir os dois casos: no primeiro não há nada a corrigir, no segundo há uma ação concreta.

O painel lista uma linha por pendência, cada uma com a instrução literal de como declará-la — o texto exato a acrescentar no construtor ou na linha de comando. Quando o modo não-interativo não foi declarado explicitamente, a instrução do modo é incluída como pendência também, de forma que uma única execução entrega ao agente todas as declarações que faltam em vez de uma por vez.

O relatório é o mecanismo que faz o agente ler o estado do repositório — não por obrigação artificial, mas porque é o único caminho para o exit 0. Nenhum handshake de token é usado: seria contornável com um pipe e não garantiria compreensão. O que o modelo garante é **especificidade e rastreabilidade**, não compreensão.

### 12.8 Ausência de Terminal Sem Declaração de Modo

Quando não é possível perguntar (sem `isatty()`, ou com `EOFError` na leitura — Seção 12.4.1) e sem declaração explícita de modo não-interativo, o pacote não prossegue. Ele falha com o relatório de pendências, incluindo a instrução da flag de modo.

A impossibilidade de perguntar serve para **não travar nem quebrar**, nunca para autorizar. Se ela sozinha habilitasse o modo autônomo, qualquer contexto sem TTY — CI, cron, saída redirecionada — passaria a pular a revisão final silenciosamente, que é exatamente o comportamento de uma flag global concedida por acidente. O modo autônomo é sempre declarado, nunca inferido.

Consequência prática: em modo não-interativo declarado, `confirm_deploy` não é chamado; os painéis de auditoria, requirements, avisos de execução e env são impressos normalmente e o deploy prossegue. O output permanece integralmente legível — é o relatório que o agente consome.

### 12.9 `RBR_SKIP_GIT_CHECK` — Depreciado

A env var `RBR_SKIP_GIT_CHECK` (Seção 4.5) continua funcional por compatibilidade, mas está depreciada em favor do ack escopado, que é estritamente superior: roda os cinco checks e exige que o resultado seja nomeado, em vez de não rodar nada.

O comportamento anterior de exibir o painel verde de sucesso quando o bypass está ativo é corrigido. Aquele painel afirma "Repositório limpo — código sincronizado com o remote", uma afirmação que o pacote não verificou. Para um humano é ruído; para um agente que lê o stdout é desinformação direta. Passa a ser exibido `GitCheckMessages.SKIPPED`, constante que já existia em `messages.py` sem uso.

### 12.10 Compatibilidade

Nenhum script de deploy existente quebra. Quem roda em terminal e não declara nada recebe exatamente os mesmos prompts, na mesma ordem, com o mesmo texto. O parâmetro `acknowledge` é opcional com default `None`, e as flags de invocação são opcionais.

O único comportamento alterado para um script existente é o do bypass de git check (Seção 12.9), que passa a exibir uma mensagem honesta em vez do painel verde — correção de bug, não breaking change.
