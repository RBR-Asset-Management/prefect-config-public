"""
Classes de deploy para flows Prefect da RBR.

Este arquivo contem toda a logica de construcao, validacao e execucao de deploys.
"""

import dataclasses
import datetime
import importlib.metadata
import inspect
import os
import re
import subprocess
import tomllib
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Callable, Generic, NoReturn, ParamSpec

from prefect.client.schemas.schedules import (
    CronSchedule,
    IntervalSchedule,
    RRuleSchedule,
)
from prefect.runner.storage import GitRepository
from prefect_github import GitHubCredentials

from rbr_prefect import _interaction
from rbr_prefect._cli import (
    confirm_advanced_schedule,
    confirm_concurrency_limit,
    confirm_git_issues,
    confirm_work_pool_override,
    print_audit_panel,
    print_env_panel,
    print_execution_notices,
    print_git_check_panel,
    print_git_check_skipped,
    print_git_issues_accepted,
    confirm_deploy,
    print_handoff,
    print_pending_acks_panel,
    print_requirements_panel,
)
from rbr_prefect._cli.messages import (
    DeployMessages,
    GitCheckMessages,
    NonInteractiveMessages,
    ProcessMessages,
    RequirementsMessages,
    ValidationMessages,
)
from rbr_prefect.constants import (
    RBRAcknowledgements,
    RBRBlocks,
    RBRDependencyMode,
    RBRDocker,
    RBRGitChecks,
    RBRJobVariables,
    RBRNonInteractive,
    RBRPrefectServer,
    RBRWorkPools,
    RBRDateTimeConvention,
    RBRBaseEnvVariables,
)

from rbr_prefect.cron import CronBuilder

from cron_descriptor import get_description, Options, CasingTypeEnum

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


def _requirement_name(spec: str) -> str:
    """
    Extrai o nome normalizado de um pacote a partir de uma especificacao de
    dependencia PEP 508.

    Exemplos: 'prefect>=3.0.0' -> 'prefect'; 'prefect[extra]>=3' -> 'prefect';
    'my_pkg ; python_version >= "3.12"' -> 'my-pkg'.
    """
    name = re.split(r"[<>=!~;\[\(\s]", spec, maxsplit=1)[0]
    return name.strip().lower().replace("_", "-")


@dataclasses.dataclass
class GitCheckIssue:
    # Identificador estavel de maquina (usar constante de RBRGitChecks). E o
    # vocabulario do ack escopado: quem aceita a issue a nomeia por este id.
    id: str
    check: str  # nome do check que falhou (usar constante de messages.py)
    details: str  # descrição legível do problema encontrado


def _ask(prompt_fn: Callable[[], bool]) -> bool | None:
    """
    Faz uma pergunta de confirmacao ao dev, se for possivel faze-la.

    Returns
    -------
    bool | None
        True/False conforme a resposta. None quando a pergunta nao pode ser
        feita — nao ha terminal, o modo autonomo foi declarado, ou o stdin
        acabou em EOF.

    O teste de sys.stdin.isatty() nao e suficiente. Em Windows/Git Bash com o
    stdin redirecionado, e em alguns runners de CI, ele reporta um terminal que
    na pratica nao pode ser lido: a pergunta e impressa e a leitura estoura
    EOFError. O teste autoritativo de "posso perguntar?" e a leitura funcionar
    ou nao, e um EOF leva a mesma conclusao da ausencia de terminal — reportar
    a pendencia em vez de derrubar o processo com traceback.
    """
    if not _interaction.can_prompt():
        return None
    try:
        return prompt_fn()
    except EOFError:
        return None


def _abort_pending(
    ack_ids: list[str] | None = None,
    git_issue_ids: list[str] | None = None,
) -> NoReturn:
    """
    Reporta as confirmacoes pendentes e encerra sem executar o deploy.

    Chamado quando nao ha terminal para perguntar e a intencao nao foi
    declarada. O relatorio traz a instrucao literal de cada pendencia, de forma
    que uma unica execucao entregue todas as declaracoes que faltam.

    Encerra com RBRNonInteractive.EXIT_CODE (2), deliberadamente distinto do
    SystemExit(0) de negacao de prompt: 0 significa que uma pessoa respondeu
    nao e nao ha o que corrigir; 2 significa que falta uma autorizacao e ha uma
    acao concreta a tomar.
    """
    instructions: list[tuple[str, str]] = []

    # A instrucao de modo vem primeiro e so quando o modo nao foi declarado —
    # sem ela o agente resolveria os acks e ainda travaria na revisao final.
    if not _interaction.non_interactive_declared():
        instructions.append(
            (
                NonInteractiveMessages.LABEL_MODE,
                NonInteractiveMessages.mode_instruction(),
            )
        )

    for ack_id in ack_ids or []:
        instructions.append(
            (ack_id, NonInteractiveMessages.ack_instruction(ack_id))
        )

    if git_issue_ids:
        ids = RBRNonInteractive.ID_SEPARATOR.join(sorted(set(git_issue_ids)))
        instructions.append(
            (
                NonInteractiveMessages.LABEL_GIT_ISSUES,
                NonInteractiveMessages.git_instruction(ids),
            )
        )

    print_pending_acks_panel(instructions)
    raise SystemExit(RBRNonInteractive.EXIT_CODE)


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

    def run_git_checks(self) -> list[GitCheckIssue]:
        """
        Executa 5 verificações de estado do repositório Git.

        Retorna lista de GitCheckIssue com os problemas encontrados.
        Lista vazia indica repositório limpo e sincronizado.
        Nunca propaga exceções — falhas de subprocess viram issues.
        """
        issues: list[GitCheckIssue] = []
        repo_root = str(self._resolve_repo_root())
        branch = self._resolve_branch()

        # Check 1 — Dirty check no repo principal
        result = subprocess.run(
            ["git", "-C", repo_root, "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            issues.append(
                GitCheckIssue(
                    id=RBRGitChecks.SUBPROCESS_ERROR,
                    check=GitCheckMessages.CHECK_SUBPROCESS_ERROR,
                    details=result.stderr,
                )
            )
        elif result.stdout.strip():
            issues.append(
                GitCheckIssue(
                    id=RBRGitChecks.DIRTY_MAIN,
                    check=GitCheckMessages.CHECK_DIRTY_MAIN,
                    details=result.stdout.strip(),
                )
            )

        # Verificar se há submódulos
        submodule_status = subprocess.run(
            ["git", "-C", repo_root, "submodule", "status", "--recursive"],
            capture_output=True,
            text=True,
            check=False,
        )
        has_submodules = submodule_status.returncode == 0 and bool(
            submodule_status.stdout.strip()
        )

        # Check 2 — Dirty check nos submódulos
        if has_submodules:
            result = subprocess.run(
                [
                    "git",
                    "-C",
                    repo_root,
                    "submodule",
                    "foreach",
                    "--quiet",
                    "--recursive",
                    "git status --porcelain",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                issues.append(
                    GitCheckIssue(
                        id=RBRGitChecks.SUBPROCESS_ERROR,
                        check=GitCheckMessages.CHECK_SUBPROCESS_ERROR,
                        details=result.stderr,
                    )
                )
            elif result.stdout.strip():
                issues.append(
                    GitCheckIssue(
                        id=RBRGitChecks.DIRTY_SUBMODULES,
                        check=GitCheckMessages.CHECK_DIRTY_SUBMODULES,
                        details=result.stdout.strip(),
                    )
                )

        # Check 3 — Commits não pushed no repo principal
        result = subprocess.run(
            [
                "git",
                "-C",
                repo_root,
                "log",
                f"origin/{branch}..HEAD",
                "--oneline",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            issues.append(
                GitCheckIssue(
                    id=RBRGitChecks.SUBPROCESS_ERROR,
                    check=GitCheckMessages.CHECK_SUBPROCESS_ERROR,
                    details=result.stderr,
                )
            )
        elif result.stdout.strip():
            issues.append(
                GitCheckIssue(
                    id=RBRGitChecks.UNPUSHED_MAIN,
                    check=GitCheckMessages.CHECK_UNPUSHED_MAIN,
                    details=result.stdout.strip(),
                )
            )

        # Check 4 — Commits não pushed nos submódulos
        if has_submodules:
            result = subprocess.run(
                [
                    "git",
                    "-C",
                    repo_root,
                    "submodule",
                    "foreach",
                    "--quiet",
                    "--recursive",
                    "git log origin/$(git rev-parse --abbrev-ref HEAD)..HEAD --oneline",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                issues.append(
                    GitCheckIssue(
                        id=RBRGitChecks.SUBPROCESS_ERROR,
                        check=GitCheckMessages.CHECK_SUBPROCESS_ERROR,
                        details=result.stderr,
                    )
                )
            elif result.stdout.strip():
                issues.append(
                    GitCheckIssue(
                        id=RBRGitChecks.UNPUSHED_SUBMODULES,
                        check=GitCheckMessages.CHECK_UNPUSHED_SUBMODULES,
                        details=result.stdout.strip(),
                    )
                )

        # Check 5 — Commit pinado de cada submódulo existe no remote
        if has_submodules:
            missing_pins: list[str] = []
            for line in submodule_status.stdout.splitlines():
                line = line.strip()
                if not line:
                    continue
                # formato: [ +-U]<sha> <path> (<describe>)
                parts = line.split()
                if len(parts) < 2:
                    continue
                sha = parts[0].lstrip("+-U")
                path = parts[1]
                submodule_abs = str(Path(repo_root) / path)

                pin_result = subprocess.run(
                    ["git", "-C", submodule_abs, "branch", "-r", "--contains", sha],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if pin_result.returncode != 0:
                    issues.append(
                        GitCheckIssue(
                            id=RBRGitChecks.SUBPROCESS_ERROR,
                            check=GitCheckMessages.CHECK_SUBPROCESS_ERROR,
                            details=pin_result.stderr,
                        )
                    )
                elif not pin_result.stdout.strip():
                    missing_pins.append(
                        f"{path}: commit {sha[:8]} não encontrado em nenhuma ref remota"
                    )

            if missing_pins:
                issues.append(
                    GitCheckIssue(
                        id=RBRGitChecks.SUBMODULE_PINS,
                        check=GitCheckMessages.CHECK_SUBMODULE_PINS,
                        details="\n".join(missing_pins),
                    )
                )

        return issues

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
# Execution Strategies
# =============================================================================


class BaseExecutionStrategy(ABC):
    """
    Classe base abstrata que define o contrato para estrategias de execucao.

    A execution strategy responde a pergunta: ONDE e COMO o flow executa?
    Concentra as diferencas entre rodar em um container Docker e rodar como
    subprocesso em um worker process: job_variables base, env base, imagem e
    validacao de dependencias.

    BaseDeploy delega para a estrategia — nunca reimplementa essa logica. As
    subclasses de deploy diferenciam-se apenas pela estrategia que injetam.
    """

    @abstractmethod
    def base_job_variables(self) -> dict[str, Any]:
        """Retorna o dict base de job_variables (invariante do ambiente)."""
        ...

    @abstractmethod
    def base_env(
        self, requirements_env: str | None, dependency_mode: str
    ) -> dict[str, str]:
        """Retorna o dict base de variaveis de ambiente do ambiente de execucao."""
        ...

    @abstractmethod
    def resolve_image(self, image: str | None) -> str | None:
        """
        Resolve a imagem a usar no deploy. Docker retorna a imagem fornecida;
        process retorna None (nao usa imagem).
        """
        ...

    def validate_dependencies(self, repo_root: Path, dependency_mode: str) -> None:
        """
        Hook de validacao de dependencias antes do deploy. Default: no-op.

        Sobrescrito por DockerExecutionStrategy para garantir as pre-condicoes
        do auto-install via uv.
        """
        return None

    def pre_deploy_notices(self) -> list[str]:
        """Avisos a exibir no terminal durante o deploy. Default: nenhum."""
        return []


class DockerExecutionStrategy(BaseExecutionStrategy):
    """
    Estrategia de execucao em container Docker (comportamento padrao da RBR).

    Monta os job_variables de container (volume de certificados, auto_remove,
    image_pull_policy), injeta o caminho do certificado TLS dentro do container
    e gerencia dependencias via auto-install (uv) ou EXTRA_PIP_PACKAGES.
    """

    def base_job_variables(self) -> dict[str, Any]:
        return {
            "volumes": [RBRDocker.CERT_VOLUME],
            "auto_remove": RBRJobVariables.AUTO_REMOVE,
            "image_pull_policy": RBRJobVariables.IMAGE_PULL_POLICY,
        }

    def base_env(
        self, requirements_env: str | None, dependency_mode: str
    ) -> dict[str, str]:
        env = {
            RBRBaseEnvVariables.PREFECT_API_SSL_CERT_FILE: RBRPrefectServer.SSL_CERT_PATH,
        }

        if dependency_mode == RBRDependencyMode.AUTO_INSTALL:
            env[RBRBaseEnvVariables.PREFECT_RUNNER_AUTO_INSTALL_DEPENDENCIES] = (
                RBRDependencyMode.ENABLED_VALUE
            )
        elif dependency_mode == RBRDependencyMode.PIP_PACKAGES:
            if requirements_env:
                env[RBRBaseEnvVariables.EXTRA_PIP_PACKAGES] = requirements_env

        return env

    def resolve_image(self, image: str | None) -> str | None:
        return image

    def validate_dependencies(self, repo_root: Path, dependency_mode: str) -> None:
        """
        Garante as pre-condicoes do auto-install: o repositorio deve ter um
        pyproject.toml com 'prefect' em [project].dependencies. Caso contrario o
        auto-install falharia silenciosamente em runtime — entao falhamos cedo,
        no deploy, com mensagem orientativa.

        E read-only (apenas le o pyproject.toml local) — respeita a invariante
        de efeitos colaterais.
        """
        if dependency_mode != RBRDependencyMode.AUTO_INSTALL:
            return

        pyproject = repo_root / "pyproject.toml"
        if not pyproject.exists():
            raise ValueError(
                f"{ValidationMessages.PYPROJECT_NOT_FOUND} ({pyproject})"
            )

        with open(pyproject, "rb") as fh:
            data = tomllib.load(fh)

        dependencies = data.get("project", {}).get("dependencies", []) or []
        names = {_requirement_name(str(dep)) for dep in dependencies}
        if RBRDependencyMode.REQUIRED_PACKAGE not in names:
            raise ValueError(ValidationMessages.PREFECT_NOT_IN_PYPROJECT)


class ProcessExecutionStrategy(BaseExecutionStrategy):
    """
    Estrategia de execucao em worker do tipo process.

    O worker executa o flow como subprocesso no proprio ambiente Python, sem
    container. Nao ha imagem, volumes nem certificado a injetar (o worker roda
    em maquina do dominio RBR, que ja confia na CA, e ja possui PREFECT_API_URL
    no ambiente). Dependencias sao responsabilidade do ambiente do worker — esta
    estrategia nao as gerencia e avisa o dev no deploy.
    """

    def base_job_variables(self) -> dict[str, Any]:
        return {}

    def base_env(
        self, requirements_env: str | None, dependency_mode: str
    ) -> dict[str, str]:
        return {}

    def resolve_image(self, image: str | None) -> None:
        return None

    def pre_deploy_notices(self) -> list[str]:
        return [ProcessMessages.WORKER_DEPS_WARNING]


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
        # --- Execution (override opcional) ---
        execution_strategy: BaseExecutionStrategy | None = None,
        # --- Python Requirements ---
        requirements_source: Path | str | None = None,
        dependency_mode: str = RBRDependencyMode.AUTO_INSTALL,
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
        # --- Confirmacoes de intencao declaradas no codigo ---
        acknowledge: list[str] | None = None,
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

        # 3b. Validar dependency_mode
        if dependency_mode not in RBRDependencyMode.ALL:
            raise ValueError(
                ValidationMessages.dependency_mode_invalid(
                    dependency_mode, ", ".join(RBRDependencyMode.ALL)
                )
            )

        # 3c. Validar e armazenar acknowledge — precede (4) e (5), que o consultam
        self._acknowledge = self._validate_acknowledge(acknowledge)

        # 4/5. Confirmacoes de intencao de configuracao. Cada uma e dispensada
        # pelo ack declarado, perguntada quando ha terminal, ou acumulada como
        # pendencia quando nao ha — nunca inferida.
        pending: list[str] = []

        # 4. Work pool que nao e um pool RBR conhecido
        if work_pool_name not in RBRWorkPools.KNOWN:
            pending += self._resolve_config_ack(
                RBRAcknowledgements.WORK_POOL_OVERRIDE,
                lambda: confirm_work_pool_override(work_pool_name),
            )

        # 5. Concurrency limit fornecido
        if concurrency_limit is not None:
            pending += self._resolve_config_ack(
                RBRAcknowledgements.CONCURRENCY_LIMIT,
                confirm_concurrency_limit,
            )

        # 5b. Reportar as duas pendencias juntas — sem isto, um agente
        # descobriria uma por execucao.
        if pending:
            _abort_pending(ack_ids=pending)

        # 6. Instanciar source_strategy
        if source_strategy is not None:
            self._source_strategy = source_strategy
        else:
            self._source_strategy = GitHubSourceStrategy(
                github_url=github_url,
                branch=branch,
            )

        # 6b. Instanciar execution_strategy (default: Docker)
        if execution_strategy is not None:
            self._execution_strategy = execution_strategy
        else:
            self._execution_strategy = DockerExecutionStrategy()

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
        # Normalizar requirements_source: str → Path na construcao
        if isinstance(requirements_source, str):
            self._requirements_source: Path | None = Path(requirements_source)
        else:
            self._requirements_source = requirements_source
        self._dependency_mode = dependency_mode
        self._work_pool_name = work_pool_name
        self._extra_job_variables = extra_job_variables or {}
        self._job_variables_override = job_variables_override
        self._extra_env = extra_env or {}
        self._env_override = env_override
        self._concurrency_limit = concurrency_limit

        self._schedule: Any = None
        self._cron_descriptor: str | None = None

        self._requirements: list[str] | None = None
        self._requirements_env: str | None = None
        self._requirements_resolved: bool = False
        self._requirements_detection_mode: str | None = None

    def _validate_acknowledge(self, acknowledge: list[str] | None) -> set[str]:
        """
        Valida os ids de acknowledge e retorna o conjunto normalizado.

        Ids desconhecidos lancam ValueError em vez de serem ignorados. O
        acknowledge existe para capturar erro de digitacao e alucinacao de
        agente; aceitar um id invalido em silencio destruiria essa propriedade —
        o deploy prosseguiria sem a autorizacao que o dev acreditou ter dado.
        """
        if not acknowledge:
            return set()

        declared = set(acknowledge)
        invalid = declared - set(RBRAcknowledgements.ALL)
        if invalid:
            raise ValueError(
                ValidationMessages.acknowledge_invalid(
                    ", ".join(sorted(invalid)),
                    ", ".join(RBRAcknowledgements.ALL),
                )
            )
        return declared

    def _resolve_config_ack(
        self, ack_id: str, prompt_fn: Callable[[], bool]
    ) -> list[str]:
        """
        Resolve uma confirmacao de intencao de configuracao.

        Aplica a regra unica do pacote: se a intencao esta declarada, roda; se
        nao esta, pergunta; se nao pode perguntar, devolve a pendencia para o
        chamador reportar.

        Returns
        -------
        list[str]
            Lista vazia quando a confirmacao esta autorizada — por ack declarado
            ou por prompt confirmado. [ack_id] quando esta pendente por ausencia
            de terminal.

        Raises
        ------
        SystemExit
            Codigo 0 quando o dev nega o prompt. E uma decisao do usuario, nao
            um erro do programa — e nao uma pendencia, pois nada falta declarar.
        """
        if ack_id in self._acknowledge:
            return []

        answer = _ask(prompt_fn)
        if answer is None:
            return [ack_id]
        if answer:
            return []
        raise SystemExit(0)

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
        """Delega o dict base de job_variables para a execution strategy."""
        return self._execution_strategy.base_job_variables()

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

    def _resolve_requirements(self) -> None:
        # Guard contra resolucao dupla
        if self._requirements_resolved:
            return

        repo_root = self._source_strategy.resolved_repo_root
        requirements = None

        if self._requirements_source is None:
            try:
                requirements = find_requirements(repo_root)
                # Determinar qual arquivo foi usado para deteccao
                if (repo_root / "pyproject.toml").exists():
                    self._requirements_detection_mode = (
                        RequirementsMessages.AUTO_DETECTED_PYPROJECT
                    )
                elif (repo_root / "requirements.txt").exists():
                    self._requirements_detection_mode = (
                        RequirementsMessages.AUTO_DETECTED_TXT
                    )
                else:
                    self._requirements_detection_mode = (
                        RequirementsMessages.AUTO_DETECTED_PYPROJECT
                    )
            except RequirementsNotFound:
                self._requirements_detection_mode = None

        else:
            # Resolver path relativo em relacao ao repo_root
            source_path = self._requirements_source
            if not source_path.is_absolute():
                source_path = repo_root / source_path

            if not source_path.exists():
                raise ValueError(
                    ValidationMessages.REQUIREMENTS_PATH_INVALID + f" ({source_path})"
                )

            requirements = from_requirements_txt(source_path)
            self._requirements_detection_mode = RequirementsMessages.explicit_file(
                str(source_path)
            )

        if requirements:
            str_requirements = [str(r) for r in requirements]
            self._requirements = str_requirements
            self._requirements_env = " ".join(str_requirements)

        self._requirements_resolved = True

    # -------------------------------------------------------------------------
    # Env Resolution
    # -------------------------------------------------------------------------

    def _build_base_env(self) -> dict[str, str]:
        """Delega o dict base de env para a execution strategy."""
        return self._execution_strategy.base_env(
            self._requirements_env, self._dependency_mode
        )

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
        cron = CronBuilder().on_weekdays().at_hour(4).at_minute(0)

        # todo dia 1 do mês as 23:00
        cron = CronBuilder().on_day_of_month(1).at_hour(23).at_minute(0)

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
        provided = sum([
            cron is not None,
            interval is not None,
            rrule is not None,
        ])
        if provided == 0:
            raise ValueError(ValidationMessages.SCHEDULE_REQUIRED)
        if provided > 1:
            raise ValueError(ValidationMessages.schedule_mutex())

        # Confirmacao para configuracoes avancadas. Nao participa do acumulo do
        # __init__: .schedule() e uma chamada posterior e separada, e reporta a
        # propria pendencia.
        if interval is not None or rrule is not None:
            pending = self._resolve_config_ack(
                RBRAcknowledgements.ADVANCED_SCHEDULE,
                confirm_advanced_schedule,
            )
            if pending:
                _abort_pending(ack_ids=pending)

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
                timezone=RBRDateTimeConvention.TIMEZONE,
            )
            try:
                raw_descriptor = get_description(
                    cron_string,
                    options=Options(
                        casing_type=CasingTypeEnum.LowerCase,
                        use_24hour_time_format=True,
                        locale_code=RBRDateTimeConvention.CRON_DESCRIPTOR_LOCALE,
                    ),
                )
                descriptor = RBRDateTimeConvention._localize_weekdays(raw_descriptor)
                descriptor = RBRDateTimeConvention._localize_months(descriptor)
                descriptor = descriptor.capitalize()
                self._cron_descriptor = descriptor

            except Exception:
                # Fallback silencioso: descricao legivel ausente, mas o cron_string
                # continua sendo aplicado corretamente no deploy.
                self._cron_descriptor = None

        if interval is not None:
            self._schedule = IntervalSchedule(
                interval=interval, timezone=RBRDateTimeConvention.TIMEZONE
            )

        if rrule is not None:
            self._schedule = RRuleSchedule(
                rrule=rrule,
                timezone=RBRDateTimeConvention.TIMEZONE,
            )

        return self

    def _resolve_git_issues_ack(self, git_issues: list[GitCheckIssue]) -> None:
        """
        Resolve a autorizacao das issues do git pre-flight check.

        Aplica a mesma regra dos acks de configuracao, com uma diferenca
        essencial: a autorizacao e escopada por id e vem da invocacao, nunca do
        codigo. Um ack de estado commitado no script desligaria a verificacao
        permanentemente para todos os deploys futuros daquele flow.

        A cobertura e avaliada por id, nao por quantidade: aceitar 'dirty_main'
        nao autoriza um 'unpushed_main' que apareca na mesma execucao. E isso que
        distingue o ack escopado de um bypass — quem aceita precisa ter visto e
        nomeado cada classe de problema.

        Raises
        ------
        SystemExit
            Codigo 0 quando o dev nega o prompt. RBRNonInteractive.EXIT_CODE
            quando restam issues nao aceitas e nao ha terminal para perguntar.
        """
        accepted = _interaction.accepted_git_issues()
        unaccepted = [issue.id for issue in git_issues if issue.id not in accepted]

        if not unaccepted:
            # Todas cobertas pelo ack da invocacao. O painel vermelho de issues
            # ja foi exibido — o estado do repo precisa ser visto de qualquer
            # forma — e aqui apenas se registra a autorizacao ao lado dele.
            ids = RBRNonInteractive.ID_SEPARATOR.join(
                sorted({issue.id for issue in git_issues})
            )
            print_git_issues_accepted(ids)
            return

        answer = _ask(confirm_git_issues)
        if answer is None:
            _abort_pending(git_issue_ids=unaccepted)
        elif not answer:
            raise SystemExit(0)

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

        # Git pre-flight check (apenas para GitHubSourceStrategy)
        if isinstance(self._source_strategy, GitHubSourceStrategy):
            if os.environ.get(GitCheckMessages.BYPASS_ENV_VAR):
                # Bypass depreciado. Exibe a mensagem de "ignorado", nao o painel
                # verde de sucesso: afirmar que o repo esta limpo sem ter
                # verificado e desinformacao para quem le o stdout.
                print_git_check_skipped()
            else:
                git_issues = self._source_strategy.run_git_checks()
                print_git_check_panel(git_issues)
                if git_issues:
                    self._resolve_git_issues_ack(git_issues)

            # Dependency pre-flight: AUTO_INSTALL exige pyproject.toml com 'prefect'.
            # Falha cedo (read-only) em vez de quebrar silenciosamente em runtime.
            self._execution_strategy.validate_dependencies(
                self._source_strategy.resolved_repo_root,
                self._dependency_mode,
            )

        # Resolver valores automáticos
        env = self._resolve_env()
        job_variables = self._resolve_job_variables()
        image = self._execution_strategy.resolve_image(self._image)

        # Preparar dados para o painel de auditoria
        resolved = {
            DeployMessages.LABEL_GITHUB_URL: self._source_strategy.resolved_github_url,
            DeployMessages.LABEL_BRANCH: self._source_strategy.resolved_branch,
            DeployMessages.LABEL_ENTRYPOINT: self._entrypoint,
            DeployMessages.LABEL_NAME: deploy_name,
        }
        # Imagem so e exibida quando a estrategia a utiliza (process retorna None)
        if image is not None:
            resolved[DeployMessages.LABEL_IMAGE] = image
        resolved[DeployMessages.LABEL_WORK_POOL] = self._work_pool_name
        resolved[DeployMessages.LABEL_TAGS] = self._tags

        if self._schedule is not None:
            resolved[DeployMessages.LABEL_SCHEDULE] = (
                f"{self._cron_descriptor} ({str(self._schedule)})"
                if self._cron_descriptor
                else str(self._schedule)
            )

        # Overrides aplicados pelo dev
        overrides = {}
        if self._parameters:
            overrides[DeployMessages.LABEL_PARAMETERS] = self._parameters

        # Exibir painel de auditoria (valores resolvidos + overrides + avisos)
        print_audit_panel(
            resolved=resolved,
            overrides=overrides,
            env_override_active=self._env_override is not None,
            job_variables_override_active=self._job_variables_override is not None,
        )

        # Exibir painel de requirements (entre valores resolvidos e env)
        print_requirements_panel(self._requirements, self._requirements_detection_mode)

        # Exibir avisos da execution strategy (ex.: deps no worker para process)
        print_execution_notices(self._execution_strategy.pre_deploy_notices())

        # Exibir painel de env resolvido
        print_env_panel(env)

        # Confirmacao do dev apos revisao dos valores resolvidos. Nao tem ack
        # proprio: nao carrega informacao nova, apenas oferece um momento de
        # revisao dos paineis acima. A declaracao de modo e o que a dispensa.
        answer = _ask(confirm_deploy)
        if answer is None:
            # Sem poder perguntar. Se o modo autonomo foi declarado, prossegue —
            # a declaracao dispensa a revisao. Se nao foi, falha: a
            # impossibilidade de perguntar evita o travamento, nunca autoriza.
            if not _interaction.non_interactive_declared():
                _abort_pending()
        elif not answer:
            raise SystemExit(0)

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
            image=image,
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
        dependency_mode: str = RBRDependencyMode.AUTO_INSTALL,
        work_pool_name: str = RBRWorkPools.DEFAULT,
        extra_job_variables: dict[str, Any] | None = None,
        job_variables_override: dict[str, Any] | None = None,
        extra_env: dict[str, str] | None = None,
        env_override: dict[str, str] | None = None,
        concurrency_limit: int | None = None,
        acknowledge: list[str] | None = None,
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
            dependency_mode=dependency_mode,
            work_pool_name=work_pool_name,
            extra_job_variables=extra_job_variables,
            job_variables_override=job_variables_override,
            extra_env=extra_env,
            env_override=env_override,
            concurrency_limit=concurrency_limit,
            acknowledge=acknowledge,
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
        dependency_mode: str = RBRDependencyMode.AUTO_INSTALL,
        work_pool_name: str = RBRWorkPools.DEFAULT,
        extra_job_variables: dict[str, Any] | None = None,
        job_variables_override: dict[str, Any] | None = None,
        extra_env: dict[str, str] | None = None,
        env_override: dict[str, str] | None = None,
        concurrency_limit: int | None = None,
        acknowledge: list[str] | None = None,
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
            dependency_mode=dependency_mode,
            work_pool_name=work_pool_name,
            extra_job_variables=extra_job_variables,
            job_variables_override=job_variables_override,
            extra_env=extra_env,
            env_override=env_override,
            concurrency_limit=concurrency_limit,
            acknowledge=acknowledge,
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
        dependency_mode: str = RBRDependencyMode.AUTO_INSTALL,
        work_pool_name: str = RBRWorkPools.DEFAULT,
        extra_job_variables: dict[str, Any] | None = None,
        job_variables_override: dict[str, Any] | None = None,
        extra_env: dict[str, str] | None = None,
        env_override: dict[str, str] | None = None,
        concurrency_limit: int | None = None,
        acknowledge: list[str] | None = None,
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
            dependency_mode=dependency_mode,
            work_pool_name=work_pool_name,
            extra_job_variables=extra_job_variables,
            job_variables_override=job_variables_override,
            extra_env=extra_env,
            env_override=env_override,
            concurrency_limit=concurrency_limit,
            acknowledge=acknowledge,
        )


class ProcessDeploy(BaseDeploy[P]):
    """
    Deploy para flows que rodam em um worker do tipo process.

    O worker executa o flow como subprocesso no proprio ambiente Python, sem
    container Docker. O codigo continua sendo buscado do GitHub (mesma source
    strategy dos demais deploys).

    Diferente dos deploys Docker, ProcessDeploy NAO gerencia dependencias
    Python — elas devem estar pre-instaladas no ambiente do worker. Por isso a
    classe nao expoe os parametros `image` nem `dependency_mode`, e exibe um
    aviso no deploy. Tambem nao injeta certificado TLS nem PREFECT_API_URL: o
    worker roda em maquina do dominio RBR (CA ja confiavel) e ja esta conectado
    ao servidor Prefect.

    Por padrao usa o work pool process da RBR (RBRWorkPools.PROCESS).
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
        requirements_source: Path | str | None = None,
        work_pool_name: str = RBRWorkPools.PROCESS,
        extra_job_variables: dict[str, Any] | None = None,
        job_variables_override: dict[str, Any] | None = None,
        extra_env: dict[str, str] | None = None,
        env_override: dict[str, str] | None = None,
        concurrency_limit: int | None = None,
        acknowledge: list[str] | None = None,
    ) -> None:
        super().__init__(
            flow_func=flow_func,
            name=name,
            tags=tags,
            source_strategy=source_strategy,
            github_url=github_url,
            branch=branch,
            entrypoint=entrypoint,
            execution_strategy=ProcessExecutionStrategy(),
            requirements_source=requirements_source,
            work_pool_name=work_pool_name,
            extra_job_variables=extra_job_variables,
            job_variables_override=job_variables_override,
            extra_env=extra_env,
            env_override=env_override,
            concurrency_limit=concurrency_limit,
            acknowledge=acknowledge,
        )
