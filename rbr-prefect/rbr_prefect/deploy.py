"""
Classes de deploy para flows Prefect da RBR.

Este arquivo contem toda a logica de construcao, validacao e execucao de deploys.
"""

import datetime
import importlib.metadata
import inspect
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Callable, Generic, ParamSpec

from prefect.client.schemas.schedules import (
    CronSchedule,
    IntervalSchedule,
    RRuleSchedule,
)
from prefect.runner.storage import GitRepository
from prefect_github import GitHubCredentials

from rbr_prefect._cli import (
    confirm_advanced_schedule,
    confirm_concurrency_limit,
    confirm_work_pool_override,
    print_audit_panel,
    print_handoff,
)
from rbr_prefect._cli.messages import DeployMessages, ValidationMessages
from rbr_prefect.constants import (
    RBRBlocks,
    RBRDocker,
    RBRJobVariables,
    RBRPrefectServer,
    RBRWorkPools,
    RBRTimeZone,
    RBRBaseEnvVariables,
)

from rbr_prefect.cron import CronBuilder

from requirements_detector import find_requirements, RequirementsNotFound
from requirements_detector.detect import from_requirements_txt

P = ParamSpec("P")


def _get_underlying_function(flow_func: Callable) -> Callable:
    """
    Extrai a funcao subjacente de um objeto Flow do Prefect.

    Quando uma funcao e decorada com @flow, ela se torna um objeto Flow.
    Para introspeccao via inspect (getfile, signature), precisamos da
    funcao original, acessivel via .fn.
    """
    if hasattr(flow_func, "fn"):
        return flow_func.fn
    return flow_func


# =============================================================================
# Source Strategies
# =============================================================================


class BaseSourceStrategy(ABC):
    """
    Classe base abstrata que define o contrato para estrategias de source.

    A source strategy responde a pergunta: de onde o Prefect vai buscar
    o codigo do flow no momento da execucao?
    """

    @abstractmethod
    def build(self) -> Any:
        """
        Constroi e retorna o objeto de source esperado pelo Prefect.

        Para GitHubSourceStrategy, retorna um GitRepository.
        Para DockerSourceStrategy, retorna None (codigo ja esta na imagem).
        """
        ...

    @abstractmethod
    def resolve_entrypoint(self, flow_func: Callable) -> str:
        """
        Resolve o entrypoint no formato esperado pelo Prefect:
        'caminho/relativo/ao/repo/flow_file.py:nome_da_funcao'

        A logica de resolucao e responsabilidade da estrategia pois
        depende do contexto de onde o codigo reside.
        """
        ...


class GitHubSourceStrategy(BaseSourceStrategy):
    """
    Estrategia de source para flows hospedados no GitHub.

    Detecta automaticamente URL do repositorio, branch e entrypoint
    via introspeccao Git, com possibilidade de override explicito.
    """

    def __init__(
        self,
        github_url: str | None = None,
        branch: str | None = None,
    ) -> None:
        """
        Parameters
        ----------
        github_url : str | None
            Override da URL do repositorio GitHub. Se None, detecta via git.
        branch : str | None
            Override do branch. Se None, detecta via git.
        """
        self._github_url_override = github_url
        self._branch_override = branch
        self._repo_root: Path | None = None  # cache apos primeira deteccao

    def build(self) -> GitRepository:
        """Constroi o GitRepository para o Prefect."""
        return GitRepository(
            url=self._resolve_github_url(),
            branch=self._resolve_branch(),
            credentials=GitHubCredentials.load(RBRBlocks.GITHUB_CREDENTIALS),
            include_submodules=True,
        )

    def resolve_entrypoint(self, flow_func: Callable) -> str:
        """Resolve o entrypoint relativo a raiz do repositorio."""
        # Extrair funcao subjacente se for um objeto Flow
        underlying_func = _get_underlying_function(flow_func)

        repo_root = self._resolve_repo_root()
        source_file = Path(inspect.getfile(underlying_func))

        # Normaliza .pyc -> .py ANTES do relative_to
        if source_file.suffix == ".pyc":
            source_file = source_file.with_suffix(".py")
            if not source_file.exists():
                raise FileNotFoundError(ValidationMessages.SOURCE_FILE_NOT_FOUND)

        try:
            relative_path = source_file.relative_to(repo_root)
        except ValueError:
            raise ValueError(ValidationMessages.ENTRYPOINT_OUTSIDE_REPO)

        func_name = underlying_func.__name__

        return f"{relative_path.as_posix()}:{func_name}"

    def _resolve_repo_root(self) -> Path:
        """Detecta a raiz do repositorio Git (com cache)."""
        if self._repo_root is not None:
            return self._repo_root

        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                check=True,
            )
            self._repo_root = Path(result.stdout.strip())
            return self._repo_root
        except subprocess.CalledProcessError:
            raise RuntimeError(ValidationMessages.OUTSIDE_GIT_REPO)

    def _resolve_github_url(self) -> str:
        """Detecta a URL do remote origin ou retorna o override."""
        if self._github_url_override is not None:
            return self._github_url_override

        try:
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            raise RuntimeError(ValidationMessages.NO_REMOTE_ORIGIN)

    def _resolve_branch(self) -> str:
        """Detecta o branch atual ou retorna o override."""
        if self._branch_override is not None:
            return self._branch_override

        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            raise RuntimeError(ValidationMessages.OUTSIDE_GIT_REPO)

    @property
    def resolved_github_url(self) -> str:
        """URL do repositorio GitHub (resolvida ou override)."""
        return self._resolve_github_url()

    @property
    def resolved_branch(self) -> str:
        """Branch atual (resolvido ou override)."""
        return self._resolve_branch()

    @property
    def resolved_repo_root(self) -> Path:
        """Raiz do repositorio Git."""
        return self._resolve_repo_root()


class DockerSourceStrategy(BaseSourceStrategy):
    """
    Estrategia de source para flows cujo codigo esta embutido diretamente
    em uma imagem Docker customizada no registry da RBR.

    ** NAO IMPLEMENTADO - previsto para implementacao futura. **

    Quando implementado, esta estrategia devera:
    - Receber o caminho do entrypoint dentro da imagem como parametro obrigatorio.
    - Retornar None em build() (sem GitRepository necessario).
    - O deploy sera realizado via flow.deploy() diretamente, sem from_source().
    """

    def build(self) -> None:
        raise NotImplementedError(
            "DockerSourceStrategy ainda nao esta implementada. "
            "Use GitHubSourceStrategy para deploys a partir do GitHub."
        )

    def resolve_entrypoint(self, flow_func: Callable) -> str:
        raise NotImplementedError("DockerSourceStrategy ainda nao esta implementada.")


# =============================================================================
# Deploy Classes
# =============================================================================


class BaseDeploy(Generic[P]):
    """
    Classe base para deploys de flows Prefect da RBR.

    Concentra toda a logica de construcao, validacao e execucao de deploys.
    Subclasses apenas fornecem defaults diferentes e podem sobrescrever
    os hooks _build_extra_env() e _build_extra_job_variables().
    """

    def __init__(
        self,
        # --- Obrigatorios ---
        flow_func: Callable[P, Any],
        name: str,
        tags: list[str],
        # --- Source (override opcional) ---
        source_strategy: BaseSourceStrategy | None = None,
        github_url: str | None = None,
        branch: str | None = None,
        entrypoint: str | None = None,
        # --- Python Requirements ---
        requirements_source: Path | str | None = None,
        # --- Imagem Docker ---
        image: str = RBRDocker.DEFAULT_IMAGE,
        # --- Work pool ---
        work_pool_name: str = RBRWorkPools.DEFAULT,
        # --- job_variables customizados ---
        extra_job_variables: dict[str, Any] | None = None,
        job_variables_override: dict[str, Any] | None = None,
        # --- env customizado ---
        extra_env: dict[str, str] | None = None,
        env_override: dict[str, str] | None = None,
        # --- Concurrency (uso incomum) ---
        concurrency_limit: int | None = None,
    ) -> None:
        # 1. Validar tags
        if not tags:
            raise ValueError(ValidationMessages.TAGS_REQUIRED)

        # 2. Validar mutualmente exclusivos: job_variables
        if job_variables_override is not None and extra_job_variables is not None:
            raise ValueError(ValidationMessages.JOB_VARIABLES_MUTEX)

        # 3. Validar mutualmente exclusivos: env
        if env_override is not None and extra_env is not None:
            raise ValueError(ValidationMessages.ENV_MUTEX)

        # 4. Prompt de confirmacao se work_pool != default
        if work_pool_name != RBRWorkPools.DEFAULT:
            if not confirm_work_pool_override(work_pool_name):
                raise SystemExit(0)

        # 5. Prompt de confirmacao se concurrency_limit fornecido
        if concurrency_limit is not None:
            if not confirm_concurrency_limit():
                raise SystemExit(0)

        # 6. Instanciar source_strategy
        if source_strategy is not None:
            self._source_strategy = source_strategy
        else:
            self._source_strategy = GitHubSourceStrategy(
                github_url=github_url,
                branch=branch,
            )

        # 7. Resolver entrypoint
        self._entrypoint = entrypoint or self._source_strategy.resolve_entrypoint(
            flow_func
        )

        # 8. Resolver parameters defaults via inspect.signature
        self._parameters = self._extract_default_parameters(flow_func)

        # 9. Armazenar atributos
        self._flow_func = flow_func
        self._name = name
        self._tags = tags
        self._image = image
        self._requirements_source = requirements_source
        self._work_pool_name = work_pool_name
        self._extra_job_variables = extra_job_variables or {}
        self._job_variables_override = job_variables_override
        self._extra_env = extra_env or {}
        self._env_override = env_override
        self._concurrency_limit = concurrency_limit

        self._schedule: Any = None

        self._requirements: list[str] | None = None
        self._requirements_env: str | None = None

    def _extract_default_parameters(self, flow_func: Callable) -> dict[str, Any]:
        """Extrai parametros com valor default da assinatura da funcao."""
        underlying_func = _get_underlying_function(flow_func)
        sig = inspect.signature(underlying_func)
        return {
            name: param.default
            for name, param in sig.parameters.items()
            if param.default is not inspect.Parameter.empty
        }

    def _validate_parameter_keys(self, overrides: dict[str, Any]) -> None:
        """Valida que todas as chaves de override existem na assinatura do flow."""
        underlying_func = _get_underlying_function(self._flow_func)
        sig = inspect.signature(underlying_func)
        valid_keys = set(sig.parameters.keys())
        invalid_keys = set(overrides.keys()) - valid_keys
        if invalid_keys:
            for key in invalid_keys:
                raise ValueError(
                    ValidationMessages.invalid_param(key, underlying_func.__name__)
                )

    @property
    def parameters(self) -> dict[str, Any]:
        """Parametros atuais do deploy."""
        return self._parameters

    @parameters.setter
    def parameters(self, value: dict[str, Any]) -> None:
        """Define os parametros do deploy com validacao."""
        self._validate_parameter_keys(value)
        self._parameters = value

    def override(self, **kwargs: P.kwargs) -> dict[str, Any]:
        """
        Retorna um dicionario de parametros para sobrescrever os defaults do flow.

        Aceita exatamente os mesmos argumentos nomeados que a funcao flow,
        com autocomplete completo no Pylance.

        Usage:
            deploy.parameters = deploy.override(country_name="Argentina")

        Os parametros fornecidos sao validados contra a assinatura real
        da funcao flow - typos geram ValueError imediatamente.
        """
        overrides = dict(**kwargs)
        self._validate_parameter_keys(overrides)
        return {**self._parameters, **overrides}

    # -------------------------------------------------------------------------
    # Job Variables Resolution
    # -------------------------------------------------------------------------

    def _build_base_job_variables(self) -> dict[str, Any]:
        """Constroi o dict base de job_variables (invariante RBR)."""
        return {
            "volumes": [RBRDocker.CERT_VOLUME],
            "auto_remove": RBRJobVariables.AUTO_REMOVE,
            "image_pull_policy": RBRJobVariables.IMAGE_PULL_POLICY,
        }

    def _build_extra_job_variables(self) -> dict[str, Any]:
        """Hook para subclasses adicionarem job_variables especificos."""
        return {}

    def _resolve_job_variables(self) -> dict[str, Any]:
        """Resolve o dict final de job_variables."""
        if self._job_variables_override is not None:
            # Bypass total
            return self._job_variables_override

        base = self._build_base_job_variables()
        extras = self._build_extra_job_variables()
        user = self._extra_job_variables

        merged = {**base, **extras, **user}

        # env e sempre resolvido separadamente e injetado por ultimo
        merged["env"] = self._resolve_env()

        return merged

    # -------------------------------------------------------------------------
    # Requirements Resolution
    # -------------------------------------------------------------------------

    def _resolve_requirements(self):

        requirements = None
        requirements_env = None

        if self._requirements_source is None:
            cwd = Path.cwd()
            try:
                requirements = find_requirements(cwd)
            except RequirementsNotFound:
                pass

        else:
            if type(self._requirements_source) is str:
                self._requirements_source = Path(str)

            if not self._requirements_source.exists():
                raise ValueError(ValidationMessages.REQUIREMENTS_PATH_INVALID)
            else:
                requirements = from_requirements_txt(self._requirements_source)

        if requirements:
            requirements = [str(r) for r in requirements]
            requirements_env = " ".join(requirements)

            self._requirements = requirements
            self._requirements_env = requirements_env

    # -------------------------------------------------------------------------
    # Env Resolution
    # -------------------------------------------------------------------------

    def _build_base_env(self) -> dict[str, str]:
        """Constroi o dict base de env (variáveis RBR)."""
        base_env = {
            RBRBaseEnvVariables.PREFECT_API_URL: RBRPrefectServer.API_URL,
            RBRBaseEnvVariables.PREFECT_API_SSL_CERT_FILE: RBRPrefectServer.SSL_CERT_PATH,
            RBRBaseEnvVariables.PREFECT_API_AUTH_STRING: RBRBlocks.auth_string_template(),
            RBRBaseEnvVariables.PREFECT_CLIENT_CUSTOM_HEADERS: RBRBlocks.header_template(),
        }

        if self._requirements:
            base_env[RBRBaseEnvVariables.EXTRA_PIP_PACKAGES] = self._requirements_env

        return base_env

    def _build_extra_env(self) -> dict[str, str]:
        """Hook para subclasses adicionarem variaveis de ambiente especificas."""
        return {}

    def _resolve_env(self) -> dict[str, str]:
        """Resolve o dict final de env."""
        if self._env_override is not None:
            # Bypass total inclusive do env base RBR
            return self._env_override

        self._resolve_requirements()

        base = self._build_base_env()
        subclass = self._build_extra_env()
        user = self._extra_env

        return {**base, **subclass, **user}

    # -------------------------------------------------------------------------
    # Description
    # -------------------------------------------------------------------------

    def _build_description(self) -> str:
        """Gera a descricao automatica do deploy."""
        strategy = self._source_strategy
        file_path = self._entrypoint.split(":")[0]
        github_url = strategy.resolved_github_url.removesuffix(".git")
        branch = strategy.resolved_branch

        file_url = f"{github_url}/blob/{branch}/{file_path}"

        try:
            version = importlib.metadata.version("rbr-prefect")
        except importlib.metadata.PackageNotFoundError:
            version = "dev"

        return (
            f"Flow: {self._flow_func.__name__}\n"
            f"Repositorio: {strategy.resolved_github_url}\n"
            f"Branch: {branch}\n"
            f"Entrypoint: {self._entrypoint}\n"
            f"Arquivo: {file_url}\n"
            f"Pacote rbr-prefect: {version}"
        )

    # -------------------------------------------------------------------------
    # Schedule
    # -------------------------------------------------------------------------

    def schedule(
        self,
        cron: CronBuilder | str | None = None,
        *,
        interval: datetime.timedelta | None = None,
        rrule: str | None = None,
    ) -> "BaseDeploy[P]":
        """
        Configura a agenda de execucao automatica do flow.
        Utilize rbr_prefect.cron para montar a expressão Cron
        que define a recorrência da execução.

        Exemplos:
        ```python
        from rbr_prefect.cron import CronBuilder

        # todo dia da semana às 4:00
        cron = CronBuilder().on_weekdays().at_hour(4)

        # todo dia 1 do mês as 23:00
        cron = CronBuilder().on_day_of_month(1).at_hour(23)

        # todo dia da semana a cada 30 minutos
        cron = CronBuilder().on_weekdays().every_minutes(30)

        # passa e expressão cron para o deploy
        meu_deploy.schedule(cron)

        # executa o deploy no prefect
        meu_deploy.deploy()

        ```
        rbr_prefect.cron é baseado em no pacote cron-builder.
        Acesse a documentação completa e mais exemplos em: [cron-builder](https://pypi.org/project/cron-builder/)

        Parameters
        ----------
        cron
            Expressao de agendamento construida com o pacote cron-builder.
            Interface principal e recomendada para agendamentos regulares.
            Exemplo: every().weekday.at("09:00")
        interval
            Intervalo de execucao como timedelta. Configuracao avancada -
            exige confirmacao via prompt no terminal.
        rrule
            String no formato iCalendar RRULE. Configuracao avancada -
            exige confirmacao via prompt no terminal.

        Returns
        -------
        self - permite encadeamento com .deploy().
        """
        # Validar exclusividade mutua
        provided = sum(
            [
                cron is not None,
                interval is not None,
                rrule is not None,
            ]
        )
        if provided == 0:
            raise ValueError(ValidationMessages.SCHEDULE_REQUIRED)
        if provided > 1:
            raise ValueError(ValidationMessages.schedule_mutex())

        # Prompt de confirmacao para configuracoes avancadas
        if interval is not None or rrule is not None:
            if not confirm_advanced_schedule():
                raise SystemExit(0)

        # Construir o schedule apropriado
        if cron is not None:
            # Extrair string cron do objeto cron-builder

            if type(cron) is type(CronBuilder()):
                cron_string = str(cron)

            elif type(cron) is str:
                cron_string = cron
            else:
                msg = f"Parâmetro cron deve ser do tipo {type(CronBuilder)} ou {type(str)}. Recebido {(type(cron))}"
                raise TypeError(msg)

            self._schedule = CronSchedule(
                cron=cron_string,
                timezone=RBRTimeZone.SAO_PAULO,
            )

        if interval is not None:
            self._schedule = IntervalSchedule(
                interval=interval, timezone=RBRTimeZone.SAO_PAULO
            )

        if rrule is not None:
            self._schedule = RRuleSchedule(
                rrule=rrule,
                timezone=RBRTimeZone.SAO_PAULO,
            )

        return self

    # -------------------------------------------------------------------------
    # Deploy Execution
    # -------------------------------------------------------------------------
    def deploy(self, name: str | None = None) -> None:
        """
        Executa o deploy do flow no servidor Prefect da RBR.

        Este e o unico metodo com efeitos colaterais do pacote.
        Nenhuma chamada de rede ocorre antes deste metodo ser invocado.

        Parameters
        ----------
        name
            Override opcional do nome do deploy. Quando fornecido, sobrescreve
            o name definido na construcao.
        """
        deploy_name = name or self._name
        deploy_description = self._build_description()

        # Resolver valores automáticos
        env = self._resolve_env()
        job_variables = self._resolve_job_variables()

        # Constroi mensagem requirements
        msg_requirements = (
            str(self._requirements_source) if self._requirements_source else "Auto"
        )

        # Preparar dados para o painel de auditoria
        resolved = {
            DeployMessages.LABEL_GITHUB_URL: self._source_strategy.resolved_github_url,
            DeployMessages.LABEL_BRANCH: self._source_strategy.resolved_branch,
            DeployMessages.LABEL_ENTRYPOINT: self._entrypoint,
            DeployMessages.LABEL_NAME: deploy_name,
            DeployMessages.LABEL_REQUIREMENTS: msg_requirements,
            DeployMessages.LABEL_IMAGE: self._image,
            DeployMessages.LABEL_WORK_POOL: self._work_pool_name,
            DeployMessages.LABEL_TAGS: self._tags,
        }

        if self._schedule is not None:
            resolved[DeployMessages.LABEL_SCHEDULE] = str(self._schedule)

        # Overrides aplicados pelo dev
        overrides = {}
        if self._parameters:
            overrides[DeployMessages.LABEL_PARAMETERS] = self._parameters
        if self._requirements_source:
            overrides[DeployMessages.LABEL_REQUIREMENTS] = self._requirements_source

        # Exibir painel de auditoria
        print_audit_panel(
            resolved=resolved,
            overrides=overrides,
            env=env,
            env_override_active=self._env_override is not None,
            job_variables_override_active=self._job_variables_override is not None,
        )

        # Exibir separador de passagem de responsabilidade
        print_handoff(deploy_name)

        # Construir o deployable via from_source
        deployable = self._flow_func.from_source(
            source=self._source_strategy.build(),
            entrypoint=self._entrypoint,
        )

        # Executar o deploy via API do Prefect
        deployable.deploy(
            name=deploy_name,
            work_pool_name=self._work_pool_name,
            image=self._image,
            build=False,
            push=False,
            job_variables=job_variables,
            parameters=self._parameters,
            description=deploy_description,
            tags=self._tags,
            schedules=[self._schedule] if self._schedule else [],
            concurrency_limit=self._concurrency_limit,
        )


class DefaultDeploy(BaseDeploy[P]):
    """
    Deploy padrao para flows da RBR.

    Utiliza a imagem oficial do Prefect (prefecthq/prefect:3-python3.12)
    e o work pool padrao. Adequado para flows de coleta de dados via HTTP,
    processamento, transformacao e qualquer flow que nao requeira um
    navegador headless ou dependencias especiais alem do Prefect.
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
        requirements_source: Path | str | None = None,
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
            requirements_source=requirements_source,
            work_pool_name=work_pool_name,
            extra_job_variables=extra_job_variables,
            job_variables_override=job_variables_override,
            extra_env=extra_env,
            env_override=env_override,
            concurrency_limit=concurrency_limit,
        )


class SQLDeploy(BaseDeploy[P]):
    """
    Deploy para flows que precisam de drivers de conexão com SQL Server.

    Utiliza a imagem RBR derivada do Prefect (prefecthq/prefect:3-python3.12)
    com os drivers de conexão ao SQL Server instalados e o work pool padrao.
    Adequado para flows que precisam buscar ou submeter dados ao db RBR.
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
        image: str = RBRDocker.SQL_IMAGE,
        requirements_source: Path | str | None = None,
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
            requirements_source=requirements_source,
            work_pool_name=work_pool_name,
            extra_job_variables=extra_job_variables,
            job_variables_override=job_variables_override,
            extra_env=extra_env,
            env_override=env_override,
            concurrency_limit=concurrency_limit,
        )


class ScrapeDeploy(BaseDeploy[P]):
    """
    Deploy para flows de scraping que utilizam Playwright.

    Utiliza a imagem customizada da RBR baseada no Prefect com Playwright
    para Python 3.12 pre-instalado. Injeta automaticamente as variaveis
    de ambiente necessarias para o funcionamento do Playwright em ambiente
    containerizado (sem display, modo headless).

    Adequado para flows que automatizam interacoes com portais web como
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
        image: str = RBRDocker.SCRAPE_IMAGE,
        requirements_source: Path | str | None = None,
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
            requirements_source=requirements_source,
            work_pool_name=work_pool_name,
            extra_job_variables=extra_job_variables,
            job_variables_override=job_variables_override,
            extra_env=extra_env,
            env_override=env_override,
            concurrency_limit=concurrency_limit,
        )

    def _build_extra_env(self) -> dict[str, str]:
        """Adiciona variaveis de ambiente do Playwright."""
        return {
            "PLAYWRIGHT_BROWSERS_PATH": RBRDocker.PLAYWRIGHT_BROWSERS_PATH,
            "DISPLAY": RBRDocker.PLAYWRIGHT_DISPLAY,
        }
