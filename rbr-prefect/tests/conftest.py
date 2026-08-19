# standard library
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, patch

# third-party
import pytest

# internal
from rbr_prefect import _interaction
from rbr_prefect._cli.messages import GitCheckMessages
from rbr_prefect.constants import RBRNonInteractive

FAKE_GITHUB_URL = "https://github.com/some-org/some-repo.git"
FAKE_BRANCH = "main"


@pytest.fixture(autouse=True)
def interactive_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Ambiente default de todos os testes: terminal interativo, nada declarado.

    Espelha o ambiente do dev humano, que e o caminho default do pacote — e o que
    a grande maioria dos testes exercita. Os testes do modo nao-interativo
    declaram explicitamente o contrario, do mesmo jeito que a invocacao real
    precisa declarar.

    Sem esta fixture os testes rodariam sem TTY (pytest nao tem terminal ligado
    ao stdin) e nenhum prompt seria alcancado.

    Tambem neutraliza as env vars e o argv do pacote, para que a sessao de shell
    de quem roda os testes nao vaze para dentro deles — precisamente o vazamento
    de escopo que motivou a flag de argv a ser o caminho primario.
    """
    monkeypatch.delenv(RBRNonInteractive.ENV_NON_INTERACTIVE, raising=False)
    monkeypatch.delenv(RBRNonInteractive.ENV_ACCEPT_GIT_ISSUES, raising=False)
    monkeypatch.delenv(GitCheckMessages.BYPASS_ENV_VAR, raising=False)
    monkeypatch.setattr(_interaction, "_argv", lambda: [])
    monkeypatch.setattr(_interaction, "stdin_is_tty", lambda: True)


@pytest.fixture
def no_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove o terminal interativo, sem declarar o modo nao-interativo."""
    monkeypatch.setattr(_interaction, "stdin_is_tty", lambda: False)


@pytest.fixture
def non_interactive(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ausencia de terminal com o modo nao-interativo declarado via flag."""
    monkeypatch.setattr(_interaction, "stdin_is_tty", lambda: False)
    monkeypatch.setattr(
        _interaction,
        "_argv",
        lambda: [RBRNonInteractive.FLAG_NON_INTERACTIVE],
    )


@pytest.fixture
def fake_repo_root(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def fake_repo_with_requirements(fake_repo_root: Path) -> Path:
    (fake_repo_root / "requirements.txt").write_text("bizdays\nprefect\n")
    return fake_repo_root


@pytest.fixture
def mock_git(fake_repo_root: Path) -> Generator[dict, None, None]:
    def fake_subprocess_run(cmd, **kwargs):
        result = MagicMock()
        result.returncode = 0
        if "--show-toplevel" in cmd:
            result.stdout = str(fake_repo_root) + "\n"
        elif "get-url" in cmd:
            result.stdout = FAKE_GITHUB_URL + "\n"
        elif "--abbrev-ref" in cmd:
            result.stdout = FAKE_BRANCH + "\n"
        else:
            result.stdout = ""
        return result

    with patch("subprocess.run", side_effect=fake_subprocess_run) as mock_run:
        yield {
            "repo_root": fake_repo_root,
            "github_url": FAKE_GITHUB_URL,
            "branch": FAKE_BRANCH,
            "mock_run": mock_run,
        }


@pytest.fixture
def mock_flow_file(mock_git: dict, fake_repo_root: Path) -> Generator[Path, None, None]:
    flow_file = fake_repo_root / "flows" / "teste_flow.py"
    with patch("inspect.getfile", return_value=str(flow_file)):
        yield flow_file


@pytest.fixture
def mock_prefect() -> Generator[MagicMock, None, None]:
    mock_deployable = MagicMock()
    mock_deployable.deploy = MagicMock(return_value=None)
    with (
        patch("prefect_github.GitHubCredentials.load", return_value=MagicMock()),
        patch("rbr_prefect.deploy.GitHubSourceStrategy.build", return_value=MagicMock()),
        patch("rbr_prefect.deploy.BaseDeploy.deploy", return_value=None),
    ):
        yield mock_deployable


@pytest.fixture
def mock_ui() -> Generator[MagicMock, None, None]:
    mock_console = MagicMock()
    with (
        patch("rbr_prefect._cli.ui.Confirm.ask", return_value=True),
        patch("rbr_prefect._cli.ui._console", mock_console),
    ):
        yield mock_console


@pytest.fixture(scope="session")
def flow_func():
    from tests.flows.teste_flow import teste_flow

    return teste_flow
