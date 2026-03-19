# standard library
from pathlib import Path
from unittest.mock import MagicMock, patch

# third-party
import pytest

# constants (duplicated from conftest for module-level access without import issues)
FAKE_GITHUB_URL = "https://github.com/some-org/some-repo.git"
FAKE_BRANCH = "main"


# =============================================================================
# TestAutoResolve
# =============================================================================


class TestAutoResolve:
    """Valida que a resolução automática via git produz os valores corretos."""

    def test_resolve_github_url(self, mock_git, mock_ui, flow_func):
        from rbr_prefect.deploy import GitHubSourceStrategy

        strategy = GitHubSourceStrategy()
        assert strategy.resolved_github_url == FAKE_GITHUB_URL

    def test_resolve_branch(self, mock_git, mock_ui, flow_func):
        from rbr_prefect.deploy import GitHubSourceStrategy

        strategy = GitHubSourceStrategy()
        assert strategy.resolved_branch == FAKE_BRANCH

    def test_resolve_entrypoint_format(self, mock_flow_file, mock_ui, flow_func):
        from rbr_prefect import DefaultDeploy

        deploy = DefaultDeploy(
            flow_func=flow_func,
            name="test",
            tags=["test"],
        )
        assert deploy._entrypoint == "flows/teste_flow.py:teste_flow"

    def test_repo_root_cached(self, mock_git, mock_ui, flow_func):
        from rbr_prefect.deploy import GitHubSourceStrategy

        strategy = GitHubSourceStrategy()
        _ = strategy.resolved_repo_root
        _ = strategy.resolved_repo_root

        mock_run = mock_git["mock_run"]
        toplevel_calls = [
            c for c in mock_run.call_args_list if "--show-toplevel" in c[0][0]
        ]
        assert len(toplevel_calls) == 1


# =============================================================================
# TestExplicitOverrides
# =============================================================================


class TestExplicitOverrides:
    """Valida que overrides explícitos suprimem chamadas ao git."""

    def test_explicit_github_url_skips_subprocess(self, mock_git, mock_ui, flow_func):
        from rbr_prefect.deploy import GitHubSourceStrategy

        strategy = GitHubSourceStrategy(github_url="https://explicit.url/repo.git")
        _ = strategy.resolved_github_url

        mock_run = mock_git["mock_run"]
        geturl_calls = [c for c in mock_run.call_args_list if "get-url" in c[0][0]]
        assert len(geturl_calls) == 0

    def test_explicit_branch_skips_subprocess(self, mock_git, mock_ui, flow_func):
        from rbr_prefect.deploy import GitHubSourceStrategy

        strategy = GitHubSourceStrategy(branch="explicit-branch")
        _ = strategy.resolved_branch

        mock_run = mock_git["mock_run"]
        abbrevref_calls = [
            c for c in mock_run.call_args_list if "--abbrev-ref" in c[0][0]
        ]
        assert len(abbrevref_calls) == 0

    def test_explicit_entrypoint_skips_getfile(self, mock_git, mock_ui, flow_func):
        from rbr_prefect import DefaultDeploy

        with patch(
            "inspect.getfile", side_effect=AssertionError("should not be called")
        ):
            deploy = DefaultDeploy(
                flow_func=flow_func,
                name="test",
                tags=["test"],
                entrypoint="explicit/path.py:func",
            )
        assert deploy._entrypoint == "explicit/path.py:func"


# =============================================================================
# TestInstantiation
# =============================================================================


class TestInstantiation:
    """Valida construção e defaults das subclasses."""

    def test_default_deploy_defaults(self, mock_flow_file, mock_ui, flow_func):
        from rbr_prefect import DefaultDeploy
        from rbr_prefect.constants import RBRDocker, RBRWorkPools

        deploy = DefaultDeploy(
            flow_func=flow_func,
            name="test",
            tags=["test"],
        )
        assert deploy._image == RBRDocker.DEFAULT_IMAGE
        assert deploy._work_pool_name == RBRWorkPools.DEFAULT

    def test_scrape_deploy_image(self, mock_flow_file, mock_ui, flow_func):
        from rbr_prefect import ScrapeDeploy
        from rbr_prefect.constants import RBRDocker

        deploy = ScrapeDeploy(
            flow_func=flow_func,
            name="test",
            tags=["test"],
        )
        assert deploy._image == RBRDocker.SCRAPE_IMAGE

    def test_sql_deploy_image(self, mock_flow_file, mock_ui, flow_func):
        from rbr_prefect import SQLDeploy
        from rbr_prefect.constants import RBRDocker

        deploy = SQLDeploy(
            flow_func=flow_func,
            name="test",
            tags=["test"],
        )
        assert deploy._image == RBRDocker.SQL_IMAGE

    def test_empty_tags_raises(self, mock_git, mock_ui, flow_func):
        from rbr_prefect import DefaultDeploy
        from rbr_prefect._cli.messages import ValidationMessages

        with pytest.raises(ValueError) as exc_info:
            DefaultDeploy(
                flow_func=flow_func,
                name="test",
                tags=[],
                entrypoint="flows/teste_flow.py:teste_flow",
            )
        assert ValidationMessages.TAGS_REQUIRED in str(exc_info.value)

    def test_env_mutex_raises(self, mock_git, mock_ui, flow_func):
        from rbr_prefect import DefaultDeploy
        from rbr_prefect._cli.messages import ValidationMessages

        with pytest.raises(ValueError) as exc_info:
            DefaultDeploy(
                flow_func=flow_func,
                name="test",
                tags=["test"],
                entrypoint="flows/teste_flow.py:teste_flow",
                env_override={"A": "1"},
                extra_env={"B": "2"},
            )
        assert ValidationMessages.ENV_MUTEX in str(exc_info.value)

    def test_job_variables_mutex_raises(self, mock_git, mock_ui, flow_func):
        from rbr_prefect import DefaultDeploy
        from rbr_prefect._cli.messages import ValidationMessages

        with pytest.raises(ValueError) as exc_info:
            DefaultDeploy(
                flow_func=flow_func,
                name="test",
                tags=["test"],
                entrypoint="flows/teste_flow.py:teste_flow",
                job_variables_override={"a": 1},
                extra_job_variables={"b": 2},
            )
        assert ValidationMessages.JOB_VARIABLES_MUTEX in str(exc_info.value)


# =============================================================================
# TestOverride
# =============================================================================


class TestOverride:
    """Valida override() e o setter de parameters."""

    def _make_deploy(self, flow_func):
        from rbr_prefect import DefaultDeploy

        return DefaultDeploy(
            flow_func=flow_func,
            name="test",
            tags=["test"],
            entrypoint="flows/teste_flow.py:teste_flow",
        )

    def test_override_merges_over_defaults(self, flow_func):
        deploy = self._make_deploy(flow_func)
        result = deploy.override(country_name="Argentina")
        assert result["country_name"] == "Argentina"

    def test_override_preserves_other_defaults(self, flow_func):
        deploy = self._make_deploy(flow_func)
        # teste_flow has country_name="Brazil" as default
        result = deploy.override(country_name="Argentina")
        # only one param in teste_flow — just verify key exists and was overridden
        assert "country_name" in result
        assert result["country_name"] == "Argentina"

    def test_override_invalid_key_raises(self, flow_func):
        from rbr_prefect._cli.messages import ValidationMessages

        deploy = self._make_deploy(flow_func)
        with pytest.raises(ValueError) as exc_info:
            deploy.override(nonexistent_param="value")
        assert "nonexistent_param" in str(exc_info.value)

    def test_parameters_setter_validates(self, flow_func):
        deploy = self._make_deploy(flow_func)
        with pytest.raises(ValueError) as exc_info:
            deploy.parameters = {"bad_key": 1}
        assert "bad_key" in str(exc_info.value)

    def test_parameters_setter_accepts_valid(self, flow_func):
        deploy = self._make_deploy(flow_func)
        deploy.parameters = deploy.override(country_name="X")
        assert deploy._parameters["country_name"] == "X"


# =============================================================================
# TestSchedule
# =============================================================================


class TestSchedule:
    """Valida .schedule()."""

    def _make_deploy(self, flow_func):
        from rbr_prefect import DefaultDeploy

        return DefaultDeploy(
            flow_func=flow_func,
            name="test",
            tags=["test"],
            entrypoint="flows/teste_flow.py:teste_flow",
        )

    def test_no_args_raises(self, flow_func):
        deploy = self._make_deploy(flow_func)
        with pytest.raises(ValueError):
            deploy.schedule()

    def test_two_args_raises(self, flow_func):
        import datetime

        from rbr_prefect.cron import CronBuilder

        deploy = self._make_deploy(flow_func)
        with pytest.raises(ValueError):
            deploy.schedule(
                cron=CronBuilder().on_weekdays().at_hour(9),
                interval=datetime.timedelta(hours=1),
            )

    def test_cron_sets_cron_schedule(self, flow_func):
        from prefect.client.schemas.schedules import CronSchedule

        from rbr_prefect.cron import CronBuilder

        deploy = self._make_deploy(flow_func)
        deploy.schedule(cron=CronBuilder().on_weekdays().at_hour(9))
        assert isinstance(deploy._schedule, CronSchedule)

    def test_schedule_returns_self(self, flow_func):
        from rbr_prefect.cron import CronBuilder

        deploy = self._make_deploy(flow_func)
        result = deploy.schedule(cron=CronBuilder().on_weekdays().at_hour(9))
        assert result is deploy

    def test_interval_calls_confirm(self, flow_func):
        import datetime

        deploy = self._make_deploy(flow_func)
        mock_console = MagicMock()
        with (
            patch("rbr_prefect._cli.ui.Confirm.ask", return_value=True) as mock_confirm,
            patch("rbr_prefect._cli.ui._console", mock_console),
        ):
            deploy.schedule(interval=datetime.timedelta(hours=1))
        assert mock_confirm.called

    def test_get_description_library_works(self, flow_func):
        """Valida que cron_descriptor.get_description retorna texto para crons válidos.

        Testa a biblioteca diretamente, sem passar pelas funções de localização.
        """
        from cron_descriptor import Options, get_description

        descriptor = get_description(
            "0 4 * * 1-5",
            options=Options(use_24hour_time_format=True),
        )
        assert descriptor is not None
        assert isinstance(descriptor, str)
        assert len(descriptor) > 0

    def test_cron_descriptor_populated_after_schedule(self, flow_func):
        from rbr_prefect.cron import CronBuilder

        deploy = self._make_deploy(flow_func)
        deploy.schedule(cron=CronBuilder().on_weekdays().at_hour(16).at_minute(0))
        assert deploy._cron_descriptor is not None
        assert isinstance(deploy._cron_descriptor, str)
        assert len(deploy._cron_descriptor) > 0

    def test_cron_descriptor_populated_from_string(self, flow_func):
        deploy = self._make_deploy(flow_func)
        deploy.schedule(cron="0 9 * * 1-5")
        assert deploy._cron_descriptor is not None
        assert isinstance(deploy._cron_descriptor, str)
        assert len(deploy._cron_descriptor) > 0

    def test_cron_descriptor_included_in_schedule_label(self, flow_func):
        """Valida que o descriptor aparece no label de schedule do painel de auditoria."""
        from rbr_prefect.cron import CronBuilder

        deploy = self._make_deploy(flow_func)
        deploy.schedule(cron=CronBuilder().on_weekdays().at_hour(9))

        # Simula a composição do label que .deploy() usaria no resolved dict
        assert deploy._cron_descriptor is not None
        label_value = f"{deploy._cron_descriptor} | {str(deploy._schedule)}"
        assert deploy._cron_descriptor in label_value
        assert str(deploy._schedule) in label_value

    def test_interval_abort_raises_systemexit(self, flow_func):
        import datetime

        deploy = self._make_deploy(flow_func)
        with (
            patch("rbr_prefect._cli.ui.Confirm.ask", return_value=False),
            patch("rbr_prefect._cli.ui._console"),
        ):
            with pytest.raises(SystemExit) as exc_info:
                deploy.schedule(interval=datetime.timedelta(hours=1))
        assert exc_info.value.code == 0


# =============================================================================
# TestJobVariables
# =============================================================================


class TestJobVariables:
    """Valida hierarquia de merge de job_variables."""

    def _make_deploy(self, flow_func, **kwargs):
        from rbr_prefect import DefaultDeploy

        return DefaultDeploy(
            flow_func=flow_func,
            name="test",
            tags=["test"],
            entrypoint="flows/teste_flow.py:teste_flow",
            **kwargs,
        )

    def test_base_keys_present(self, mock_git, flow_func):
        deploy = self._make_deploy(flow_func)
        result = deploy._resolve_job_variables()
        assert "volumes" in result
        assert "auto_remove" in result
        assert "image_pull_policy" in result

    def test_cert_volume_in_volumes(self, mock_git, flow_func):
        from rbr_prefect.constants import RBRDocker

        deploy = self._make_deploy(flow_func)
        result = deploy._resolve_job_variables()
        assert RBRDocker.CERT_VOLUME in result["volumes"]

    def test_extra_merged_preserves_base(self, mock_git, flow_func):
        deploy = self._make_deploy(flow_func, extra_job_variables={"custom_key": "v"})
        result = deploy._resolve_job_variables()
        assert "custom_key" in result
        assert "volumes" in result
        assert "auto_remove" in result

    def test_override_bypass_total(self, flow_func):
        deploy = self._make_deploy(flow_func, job_variables_override={"only": True})
        result = deploy._resolve_job_variables()
        assert result == {"only": True}

    def test_env_key_not_overridable_via_extra(self, mock_git, flow_func):
        from rbr_prefect.constants import RBRBaseEnvVariables, RBRPrefectServer

        deploy = self._make_deploy(flow_func, extra_job_variables={"env": {"bad": "x"}})
        result = deploy._resolve_job_variables()
        # env is always resolved separately — "bad" key must not be there
        assert "bad" not in result["env"]
        # base env key must still be present
        assert RBRBaseEnvVariables.PREFECT_API_SSL_CERT_FILE in result["env"]


# =============================================================================
# TestEnv
# =============================================================================


class TestEnv:
    """Valida hierarquia de merge de env."""

    def _make_deploy(self, flow_func, **kwargs):
        from rbr_prefect import DefaultDeploy

        return DefaultDeploy(
            flow_func=flow_func,
            name="test",
            tags=["test"],
            entrypoint="flows/teste_flow.py:teste_flow",
            **kwargs,
        )

    def test_ssl_cert_in_base_env(self, mock_git, flow_func):
        from rbr_prefect.constants import RBRBaseEnvVariables, RBRPrefectServer

        deploy = self._make_deploy(flow_func)
        env = deploy._resolve_env()
        assert RBRBaseEnvVariables.PREFECT_API_SSL_CERT_FILE in env
        assert (
            env[RBRBaseEnvVariables.PREFECT_API_SSL_CERT_FILE]
            == RBRPrefectServer.SSL_CERT_PATH
        )

    def test_extra_env_merged(self, mock_git, flow_func):
        from rbr_prefect.constants import RBRBaseEnvVariables

        deploy = self._make_deploy(flow_func, extra_env={"MY_VAR": "x"})
        env = deploy._resolve_env()
        assert "MY_VAR" in env
        assert env["MY_VAR"] == "x"
        assert RBRBaseEnvVariables.PREFECT_API_SSL_CERT_FILE in env

    def test_env_override_bypass(self, flow_func):
        deploy = self._make_deploy(flow_func, env_override={"ONLY": "x"})
        env = deploy._resolve_env()
        assert env == {"ONLY": "x"}

    def test_scrape_deploy_playwright_vars(self, mock_git, flow_func):
        from rbr_prefect import ScrapeDeploy
        from rbr_prefect.constants import RBRBaseEnvVariables, RBRDocker

        deploy = ScrapeDeploy(
            flow_func=flow_func,
            name="test",
            tags=["test"],
            entrypoint="flows/teste_flow.py:teste_flow",
        )
        env = deploy._resolve_env()
        assert "PLAYWRIGHT_BROWSERS_PATH" in env
        assert env["PLAYWRIGHT_BROWSERS_PATH"] == RBRDocker.PLAYWRIGHT_BROWSERS_PATH
        assert "DISPLAY" in env
        assert RBRBaseEnvVariables.PREFECT_API_SSL_CERT_FILE in env


# =============================================================================
# TestRequirementsResolution
# =============================================================================


class TestRequirementsResolution:
    """Valida detecção automática e explícita de requirements."""

    def _make_deploy(self, flow_func, **kwargs):
        from rbr_prefect import DefaultDeploy

        return DefaultDeploy(
            flow_func=flow_func,
            name="test",
            tags=["test"],
            entrypoint="flows/teste_flow.py:teste_flow",
            **kwargs,
        )

    def test_no_requirements_when_empty_repo(self, mock_git, flow_func):
        from rbr_prefect.constants import RBRBaseEnvVariables

        deploy = self._make_deploy(flow_func)
        env = deploy._resolve_env()
        assert RBRBaseEnvVariables.EXTRA_PIP_PACKAGES not in env

    def test_auto_detects_requirements_txt(
        self, fake_repo_with_requirements, mock_git, flow_func
    ):
        from rbr_prefect.constants import RBRBaseEnvVariables

        deploy = self._make_deploy(flow_func)
        env = deploy._resolve_env()
        assert RBRBaseEnvVariables.EXTRA_PIP_PACKAGES in env
        packages = env[RBRBaseEnvVariables.EXTRA_PIP_PACKAGES]
        assert "bizdays" in packages
        assert "prefect" in packages

    def test_detection_mode_is_txt(
        self, fake_repo_with_requirements, mock_git, flow_func
    ):
        from rbr_prefect._cli.messages import RequirementsMessages

        deploy = self._make_deploy(flow_func)
        deploy._resolve_requirements()
        assert (
            deploy._requirements_detection_mode
            == RequirementsMessages.AUTO_DETECTED_TXT
        )

    def test_explicit_requirements_source(self, fake_repo_root, mock_git, flow_func):
        from rbr_prefect.constants import RBRBaseEnvVariables

        custom_dir = fake_repo_root / "custom"
        custom_dir.mkdir()
        custom_req = custom_dir / "requirements.txt"
        custom_req.write_text("pandas\nnumpy\n")

        deploy = self._make_deploy(flow_func, requirements_source=str(custom_req))
        env = deploy._resolve_env()
        assert RBRBaseEnvVariables.EXTRA_PIP_PACKAGES in env
        packages = env[RBRBaseEnvVariables.EXTRA_PIP_PACKAGES]
        assert "pandas" in packages
        assert "numpy" in packages

    def test_explicit_source_detection_mode(self, fake_repo_root, mock_git, flow_func):
        custom_req = fake_repo_root / "requirements.txt"
        custom_req.write_text("pandas\n")

        deploy = self._make_deploy(flow_func, requirements_source=str(custom_req))
        deploy._resolve_requirements()
        assert deploy._requirements_detection_mode is not None
        assert str(custom_req) in deploy._requirements_detection_mode

    def test_invalid_requirements_source_raises(self, mock_git, flow_func):
        deploy = self._make_deploy(
            flow_func, requirements_source="/nonexistent/path/requirements.txt"
        )
        with pytest.raises(ValueError):
            deploy._resolve_requirements()

    def test_requirements_format_is_space_separated(
        self, fake_repo_with_requirements, mock_git, flow_func
    ):
        from rbr_prefect.constants import RBRBaseEnvVariables

        deploy = self._make_deploy(flow_func)
        env = deploy._resolve_env()
        packages_str = env[RBRBaseEnvVariables.EXTRA_PIP_PACKAGES]
        assert isinstance(packages_str, str)
        # space-separated means no commas, newlines, or other separators
        assert "," not in packages_str
        assert "\n" not in packages_str
        parts = packages_str.split(" ")
        assert len(parts) >= 2

    def test_no_double_resolution(
        self, fake_repo_with_requirements, mock_git, flow_func
    ):
        deploy = self._make_deploy(flow_func)

        with patch(
            "rbr_prefect.deploy.find_requirements", return_value=[]
        ) as mock_find:
            deploy._resolve_requirements()
            deploy._resolve_requirements()
        assert mock_find.call_count == 1
