# standard library
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, patch

# third-party
import pytest

FAKE_GITHUB_URL = "https://github.com/some-org/some-repo.git"
FAKE_BRANCH = "main"


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
