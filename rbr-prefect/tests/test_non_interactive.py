"""
Testes do modo nao-interativo e dos acknowledgements.

Cobre a regra unica da Secao 12 do REQUIREMENTS.md: se a intencao esta
declarada, roda; se nao esta, pergunta; se nao pode perguntar, falha dizendo o
que declarar.

A fixture autouse `interactive_terminal` (conftest.py) faz o ambiente default de
todo teste ser um terminal interativo sem nada declarado. Os testes abaixo que
exercitam o modo autonomo usam as fixtures `no_terminal` e `non_interactive`.
"""

# standard library
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

# third-party
import pytest

# internal
from rbr_prefect import DefaultDeploy, _interaction
from rbr_prefect._cli.messages import GitCheckMessages
from rbr_prefect.constants import (
    RBRAcknowledgements,
    RBRDependencyMode,
    RBRGitChecks,
    RBRNonInteractive,
    RBRWorkPools,
)
from rbr_prefect.deploy import GitCheckIssue

OTHER_POOL = "algum-pool-que-nao-e-rbr"


def _make_deploy(flow_func, **kwargs):
    """
    Instancia um DefaultDeploy com os obrigatorios preenchidos.

    Passa `entrypoint` explicito (dispensa a resolucao via git no repo fake) e
    dependency_mode=pip_packages (dispensa o check de pyproject.toml). Estes
    testes focam nas confirmacoes, nao em source nem em dependencias.
    """
    kwargs.setdefault("dependency_mode", RBRDependencyMode.PIP_PACKAGES)
    return DefaultDeploy(
        flow_func=flow_func,
        name="test",
        tags=["test"],
        entrypoint="flows/teste_flow.py:teste_flow",
        **kwargs,
    )


def _patch_prefect_calls(flow_func):
    """Mocka as chamadas de rede ao Prefect no final de deploy()."""
    mock_deployable = MagicMock()
    mock_deployable.deploy = MagicMock(return_value=None)
    return (
        patch.object(flow_func, "from_source", return_value=mock_deployable),
        patch("prefect_github.GitHubCredentials.load", return_value=MagicMock()),
    )


# =============================================================================
# TestInteractionResolution
# =============================================================================


class TestInteractionResolution:
    """Valida a leitura de argv e env var em _interaction.py."""

    def test_flag_declares_non_interactive(self, monkeypatch):
        monkeypatch.setattr(
            _interaction, "_argv", lambda: [RBRNonInteractive.FLAG_NON_INTERACTIVE]
        )
        assert _interaction.non_interactive_declared() is True

    def test_env_var_declares_non_interactive(self, monkeypatch):
        monkeypatch.setenv(RBRNonInteractive.ENV_NON_INTERACTIVE, "1")
        assert _interaction.non_interactive_declared() is True

    def test_empty_env_var_does_not_declare(self, monkeypatch):
        monkeypatch.setenv(RBRNonInteractive.ENV_NON_INTERACTIVE, "")
        assert _interaction.non_interactive_declared() is False

    def test_nothing_declared_by_default(self):
        assert _interaction.non_interactive_declared() is False

    def test_can_prompt_requires_tty_and_no_declaration(self, monkeypatch):
        assert _interaction.can_prompt() is True

        monkeypatch.setattr(
            _interaction, "_argv", lambda: [RBRNonInteractive.FLAG_NON_INTERACTIVE]
        )
        assert _interaction.can_prompt() is False

    def test_can_prompt_false_without_tty(self, no_terminal):
        assert _interaction.can_prompt() is False

    def test_git_issues_from_flag_with_equals(self, monkeypatch):
        monkeypatch.setattr(
            _interaction,
            "_argv",
            lambda: [
                f"{RBRNonInteractive.FLAG_ACCEPT_GIT_ISSUES}"
                f"={RBRGitChecks.DIRTY_MAIN},{RBRGitChecks.UNPUSHED_MAIN}"
            ],
        )
        assert _interaction.accepted_git_issues() == {
            RBRGitChecks.DIRTY_MAIN,
            RBRGitChecks.UNPUSHED_MAIN,
        }

    def test_git_issues_from_flag_with_space(self, monkeypatch):
        monkeypatch.setattr(
            _interaction,
            "_argv",
            lambda: [
                RBRNonInteractive.FLAG_ACCEPT_GIT_ISSUES,
                RBRGitChecks.DIRTY_MAIN,
            ],
        )
        assert _interaction.accepted_git_issues() == {RBRGitChecks.DIRTY_MAIN}

    def test_git_issues_flag_without_value_does_not_eat_next_flag(self, monkeypatch):
        """
        Flag de ack sem valor seguida por outra flag --rbr- resulta em conjunto
        vazio — nao consome a flag seguinte como se fosse um id.
        """
        monkeypatch.setattr(
            _interaction,
            "_argv",
            lambda: [
                RBRNonInteractive.FLAG_ACCEPT_GIT_ISSUES,
                RBRNonInteractive.FLAG_NON_INTERACTIVE,
            ],
        )
        assert _interaction.accepted_git_issues() == set()
        assert _interaction.non_interactive_declared() is True

    def test_git_issues_from_env_var(self, monkeypatch):
        monkeypatch.setenv(
            RBRNonInteractive.ENV_ACCEPT_GIT_ISSUES, RBRGitChecks.DIRTY_MAIN
        )
        assert _interaction.accepted_git_issues() == {RBRGitChecks.DIRTY_MAIN}

    def test_flag_takes_precedence_over_env_var(self, monkeypatch):
        """
        A flag vence a env var sem uniao entre as fontes. Uniao permitiria que uma
        env var esquecida na sessao do shell ampliasse silenciosamente um ack
        escrito na linha de comando.
        """
        monkeypatch.setenv(
            RBRNonInteractive.ENV_ACCEPT_GIT_ISSUES, RBRGitChecks.UNPUSHED_MAIN
        )
        monkeypatch.setattr(
            _interaction,
            "_argv",
            lambda: [
                f"{RBRNonInteractive.FLAG_ACCEPT_GIT_ISSUES}={RBRGitChecks.DIRTY_MAIN}"
            ],
        )
        assert _interaction.accepted_git_issues() == {RBRGitChecks.DIRTY_MAIN}

    def test_unknown_rbr_flags_are_ignored(self, monkeypatch):
        """Argumentos alheios no argv nao causam erro — o pacote so le --rbr-*."""
        monkeypatch.setattr(
            _interaction,
            "_argv",
            lambda: ["--verbose", "-x", "meu_arquivo.csv", "--dry-run"],
        )
        assert _interaction.non_interactive_declared() is False
        assert _interaction.accepted_git_issues() == set()


# =============================================================================
# TestAcknowledgeValidation
# =============================================================================


class TestAcknowledgeValidation:
    """Valida o parametro acknowledge no construtor."""

    def test_valid_ack_accepted(self, mock_git, mock_ui, flow_func):
        deploy = _make_deploy(
            flow_func, acknowledge=[RBRAcknowledgements.CONCURRENCY_LIMIT]
        )
        assert deploy._acknowledge == {RBRAcknowledgements.CONCURRENCY_LIMIT}

    def test_none_means_nothing_declared(self, mock_git, mock_ui, flow_func):
        deploy = _make_deploy(flow_func)
        assert deploy._acknowledge == set()

    def test_empty_list_means_nothing_declared(self, mock_git, mock_ui, flow_func):
        deploy = _make_deploy(flow_func, acknowledge=[])
        assert deploy._acknowledge == set()

    def test_duplicates_normalized(self, mock_git, mock_ui, flow_func):
        deploy = _make_deploy(
            flow_func,
            acknowledge=[
                RBRAcknowledgements.CONCURRENCY_LIMIT,
                RBRAcknowledgements.CONCURRENCY_LIMIT,
            ],
        )
        assert deploy._acknowledge == {RBRAcknowledgements.CONCURRENCY_LIMIT}

    def test_unknown_id_raises_value_error(self, mock_git, mock_ui, flow_func):
        """
        Id desconhecido nao e ignorado. O acknowledge existe para capturar erro de
        digitacao; aceitar um id invalido em silencio faria o deploy prosseguir sem
        a autorizacao que o dev acreditou ter dado.
        """
        with pytest.raises(ValueError) as exc_info:
            _make_deploy(flow_func, acknowledge=["concurrency_limits"])

        assert "concurrency_limits" in str(exc_info.value)
        assert RBRAcknowledgements.CONCURRENCY_LIMIT in str(exc_info.value)

    def test_unneeded_ack_is_not_an_error(self, mock_git, mock_ui, flow_func):
        """Declarar um ack que nao e acionado nao faz nada — nao e erro."""
        deploy = _make_deploy(
            flow_func, acknowledge=[RBRAcknowledgements.ADVANCED_SCHEDULE]
        )
        assert deploy._acknowledge == {RBRAcknowledgements.ADVANCED_SCHEDULE}


# =============================================================================
# TestConfigAcksInteractive
# =============================================================================


class TestConfigAcksInteractive:
    """Com terminal, o ack declarado suprime o prompt; sem ack, prompta."""

    def test_ack_suppresses_work_pool_prompt(self, mock_git, mock_ui, flow_func):
        with patch("rbr_prefect.deploy.confirm_work_pool_override") as mock_confirm:
            _make_deploy(
                flow_func,
                work_pool_name=OTHER_POOL,
                acknowledge=[RBRAcknowledgements.WORK_POOL_OVERRIDE],
            )
        mock_confirm.assert_not_called()

    def test_no_ack_prompts_work_pool(self, mock_git, mock_ui, flow_func):
        with patch(
            "rbr_prefect.deploy.confirm_work_pool_override", return_value=True
        ) as mock_confirm:
            _make_deploy(flow_func, work_pool_name=OTHER_POOL)
        mock_confirm.assert_called_once()

    def test_ack_suppresses_concurrency_prompt(self, mock_git, mock_ui, flow_func):
        with patch("rbr_prefect.deploy.confirm_concurrency_limit") as mock_confirm:
            _make_deploy(
                flow_func,
                concurrency_limit=1,
                acknowledge=[RBRAcknowledgements.CONCURRENCY_LIMIT],
            )
        mock_confirm.assert_not_called()

    def test_ack_is_scoped_to_its_own_decision(self, mock_git, mock_ui, flow_func):
        """
        O ack de work pool nao autoriza o de concurrency. Cada confirmacao exige a
        sua propria declaracao.
        """
        with patch(
            "rbr_prefect.deploy.confirm_concurrency_limit", return_value=True
        ) as mock_confirm:
            _make_deploy(
                flow_func,
                work_pool_name=OTHER_POOL,
                concurrency_limit=1,
                acknowledge=[RBRAcknowledgements.WORK_POOL_OVERRIDE],
            )
        mock_confirm.assert_called_once()

    def test_denied_prompt_still_exits_zero(self, mock_git, mock_ui, flow_func):
        """
        Negacao de prompt continua sendo SystemExit(0) — decisao do usuario, nao
        falta de autorizacao.
        """
        with patch(
            "rbr_prefect.deploy.confirm_concurrency_limit", return_value=False
        ):
            with pytest.raises(SystemExit) as exc_info:
                _make_deploy(flow_func, concurrency_limit=1)
        assert exc_info.value.code == 0

    def test_ack_suppresses_advanced_schedule_prompt(
        self, mock_git, mock_ui, flow_func
    ):
        import datetime

        deploy = _make_deploy(
            flow_func, acknowledge=[RBRAcknowledgements.ADVANCED_SCHEDULE]
        )
        with patch("rbr_prefect.deploy.confirm_advanced_schedule") as mock_confirm:
            deploy.schedule(interval=datetime.timedelta(hours=1))
        mock_confirm.assert_not_called()
        assert deploy._schedule is not None


# =============================================================================
# TestEofBackstop
# =============================================================================


class TestEofBackstop:
    """
    Um terminal que se diz interativo mas nao pode ser lido cai no mesmo caminho
    da ausencia de terminal.

    Este caso nao e hipotetico: em Windows/Git Bash com o stdin redirecionado,
    sys.stdin.isatty() retorna True e a leitura estoura EOFError. Sem este
    backstop, o ambiente de um agente rodando exatamente esse shell voltaria a
    quebrar com traceback — o problema que o modo nao-interativo existe para
    resolver.
    """

    def test_eof_on_config_prompt_becomes_pending(self, mock_git, mock_ui, flow_func):
        def raise_eof():
            raise EOFError("EOF when reading a line")

        with (
            patch(
                "rbr_prefect.deploy.confirm_concurrency_limit", side_effect=raise_eof
            ),
            patch("rbr_prefect.deploy.print_pending_acks_panel") as mock_panel,
        ):
            with pytest.raises(SystemExit) as exc_info:
                _make_deploy(flow_func, concurrency_limit=1)

        assert exc_info.value.code == RBRNonInteractive.EXIT_CODE
        labels = [label for label, _ in mock_panel.call_args[0][0]]
        assert RBRAcknowledgements.CONCURRENCY_LIMIT in labels

    def test_eof_on_final_confirmation_aborts(self, mock_git, mock_ui, flow_func):
        def raise_eof():
            raise EOFError("EOF when reading a line")

        deploy = _make_deploy(flow_func)
        p1, p2 = _patch_prefect_calls(flow_func)

        with (
            patch(
                "rbr_prefect.deploy.GitHubSourceStrategy.run_git_checks",
                return_value=[],
            ),
            patch("rbr_prefect.deploy.print_git_check_panel"),
            patch("rbr_prefect.deploy.confirm_deploy", side_effect=raise_eof),
            patch("rbr_prefect.deploy.print_pending_acks_panel"),
            patch("rbr_prefect.deploy.print_handoff") as mock_handoff,
            p1,
            p2,
        ):
            with pytest.raises(SystemExit) as exc_info:
                deploy.deploy()

        assert exc_info.value.code == RBRNonInteractive.EXIT_CODE
        mock_handoff.assert_not_called()

    def test_eof_on_final_confirmation_proceeds_when_mode_declared(
        self, mock_git, mock_ui, flow_func, monkeypatch
    ):
        """
        Com o modo declarado, o prompt final nem e tentado — nao ha EOF a tratar,
        e o deploy prossegue.
        """
        monkeypatch.setattr(
            _interaction, "_argv", lambda: [RBRNonInteractive.FLAG_NON_INTERACTIVE]
        )
        deploy = _make_deploy(flow_func)
        p1, p2 = _patch_prefect_calls(flow_func)

        with (
            patch(
                "rbr_prefect.deploy.GitHubSourceStrategy.run_git_checks",
                return_value=[],
            ),
            patch("rbr_prefect.deploy.print_git_check_panel"),
            patch("rbr_prefect.deploy.confirm_deploy") as mock_confirm,
            patch("rbr_prefect.deploy.print_handoff") as mock_handoff,
            p1,
            p2,
        ):
            deploy.deploy()

        mock_confirm.assert_not_called()
        mock_handoff.assert_called_once()

    def test_eof_on_git_prompt_becomes_pending(self, mock_git, mock_ui, flow_func):
        def raise_eof():
            raise EOFError("EOF when reading a line")

        issue = GitCheckIssue(
            id=RBRGitChecks.DIRTY_MAIN,
            check=GitCheckMessages.CHECK_DIRTY_MAIN,
            details="M file.py",
        )
        deploy = _make_deploy(flow_func)
        p1, p2 = _patch_prefect_calls(flow_func)

        with (
            patch(
                "rbr_prefect.deploy.GitHubSourceStrategy.run_git_checks",
                return_value=[issue],
            ),
            patch("rbr_prefect.deploy.print_git_check_panel"),
            patch("rbr_prefect.deploy.confirm_git_issues", side_effect=raise_eof),
            patch("rbr_prefect.deploy.print_pending_acks_panel") as mock_panel,
            p1,
            p2,
        ):
            with pytest.raises(SystemExit) as exc_info:
                deploy.deploy()

        assert exc_info.value.code == RBRNonInteractive.EXIT_CODE
        instructions = " ".join(
            instruction for _, instruction in mock_panel.call_args[0][0]
        )
        assert RBRGitChecks.DIRTY_MAIN in instructions


# =============================================================================
# TestConfigAcksWithoutTerminal
# =============================================================================


class TestConfigAcksWithoutTerminal:
    """Sem terminal, a confirmacao nao declarada vira pendencia reportada."""

    def test_missing_ack_exits_with_code_two(
        self, mock_git, mock_ui, flow_func, no_terminal
    ):
        with patch("rbr_prefect.deploy.print_pending_acks_panel"):
            with pytest.raises(SystemExit) as exc_info:
                _make_deploy(flow_func, concurrency_limit=1)
        assert exc_info.value.code == RBRNonInteractive.EXIT_CODE

    def test_prompt_never_called_without_terminal(
        self, mock_git, mock_ui, flow_func, no_terminal
    ):
        """
        Sem terminal o prompt nao e tentado — e o que evita o EOFError/travamento
        que bloqueava o uso autonomo.
        """
        with (
            patch("rbr_prefect.deploy.confirm_concurrency_limit") as mock_confirm,
            patch("rbr_prefect.deploy.print_pending_acks_panel"),
        ):
            with pytest.raises(SystemExit):
                _make_deploy(flow_func, concurrency_limit=1)
        mock_confirm.assert_not_called()

    def test_both_config_acks_reported_together(
        self, mock_git, mock_ui, flow_func, no_terminal
    ):
        """
        As duas confirmacoes visiveis no __init__ sao reportadas na mesma execucao.
        Sem isso um agente descobriria uma pendencia por execucao.
        """
        with patch("rbr_prefect.deploy.print_pending_acks_panel") as mock_panel:
            with pytest.raises(SystemExit):
                _make_deploy(
                    flow_func, work_pool_name=OTHER_POOL, concurrency_limit=1
                )

        reported = mock_panel.call_args[0][0]
        labels = [label for label, _ in reported]
        assert RBRAcknowledgements.WORK_POOL_OVERRIDE in labels
        assert RBRAcknowledgements.CONCURRENCY_LIMIT in labels

    def test_report_includes_mode_instruction_when_not_declared(
        self, mock_git, mock_ui, flow_func, no_terminal
    ):
        """
        Sem declaracao de modo, a instrucao da flag de modo entra no relatorio —
        senao o agente resolveria os acks e ainda travaria na revisao final.
        """
        with patch("rbr_prefect.deploy.print_pending_acks_panel") as mock_panel:
            with pytest.raises(SystemExit):
                _make_deploy(flow_func, concurrency_limit=1)

        instructions = " ".join(
            instruction for _, instruction in mock_panel.call_args[0][0]
        )
        assert RBRNonInteractive.FLAG_NON_INTERACTIVE in instructions

    def test_report_omits_mode_instruction_when_declared(
        self, mock_git, mock_ui, flow_func, non_interactive
    ):
        with patch("rbr_prefect.deploy.print_pending_acks_panel") as mock_panel:
            with pytest.raises(SystemExit):
                _make_deploy(flow_func, concurrency_limit=1)

        labels = [label for label, _ in mock_panel.call_args[0][0]]
        assert labels == [RBRAcknowledgements.CONCURRENCY_LIMIT]

    def test_declared_ack_runs_without_terminal(
        self, mock_git, mock_ui, flow_func, non_interactive
    ):
        """O caminho autonomo completo do __init__: ack declarado, nada a perguntar."""
        deploy = _make_deploy(
            flow_func,
            concurrency_limit=1,
            acknowledge=[RBRAcknowledgements.CONCURRENCY_LIMIT],
        )
        assert deploy._concurrency_limit == 1

    def test_advanced_schedule_pending_without_terminal(
        self, mock_git, mock_ui, flow_func, no_terminal
    ):
        import datetime

        deploy = _make_deploy(flow_func)
        with patch("rbr_prefect.deploy.print_pending_acks_panel") as mock_panel:
            with pytest.raises(SystemExit) as exc_info:
                deploy.schedule(interval=datetime.timedelta(hours=1))

        assert exc_info.value.code == RBRNonInteractive.EXIT_CODE
        labels = [label for label, _ in mock_panel.call_args[0][0]]
        assert RBRAcknowledgements.ADVANCED_SCHEDULE in labels


# =============================================================================
# TestFinalConfirmation
# =============================================================================


class TestFinalConfirmation:
    """A revisao final nao tem ack proprio — a declaracao de modo a dispensa."""

    def test_prompted_with_terminal(self, mock_git, mock_ui, flow_func):
        deploy = _make_deploy(flow_func)
        p1, p2 = _patch_prefect_calls(flow_func)

        with (
            patch(
                "rbr_prefect.deploy.GitHubSourceStrategy.run_git_checks",
                return_value=[],
            ),
            patch("rbr_prefect.deploy.print_git_check_panel"),
            patch("rbr_prefect.deploy.confirm_deploy", return_value=True) as mock_confirm,
            p1,
            p2,
        ):
            deploy.deploy()

        mock_confirm.assert_called_once()

    def test_skipped_when_mode_declared(
        self, mock_git, mock_ui, flow_func, non_interactive
    ):
        deploy = _make_deploy(flow_func)
        p1, p2 = _patch_prefect_calls(flow_func)

        with (
            patch(
                "rbr_prefect.deploy.GitHubSourceStrategy.run_git_checks",
                return_value=[],
            ),
            patch("rbr_prefect.deploy.print_git_check_panel"),
            patch("rbr_prefect.deploy.confirm_deploy") as mock_confirm,
            patch("rbr_prefect.deploy.print_handoff") as mock_handoff,
            p1,
            p2,
        ):
            deploy.deploy()

        mock_confirm.assert_not_called()
        mock_handoff.assert_called_once()

    def test_aborts_without_terminal_and_without_declaration(
        self, mock_git, mock_ui, flow_func, no_terminal
    ):
        """
        Ausencia de TTY evita o travamento; ela nunca autoriza. Sem declaracao de
        modo o deploy falha, mesmo sem nenhuma outra pendencia.
        """
        deploy = _make_deploy(flow_func)
        p1, p2 = _patch_prefect_calls(flow_func)

        with (
            patch(
                "rbr_prefect.deploy.GitHubSourceStrategy.run_git_checks",
                return_value=[],
            ),
            patch("rbr_prefect.deploy.print_git_check_panel"),
            patch("rbr_prefect.deploy.print_pending_acks_panel") as mock_panel,
            patch("rbr_prefect.deploy.print_handoff") as mock_handoff,
            p1,
            p2,
        ):
            with pytest.raises(SystemExit) as exc_info:
                deploy.deploy()

        assert exc_info.value.code == RBRNonInteractive.EXIT_CODE
        mock_handoff.assert_not_called()
        instructions = " ".join(
            instruction for _, instruction in mock_panel.call_args[0][0]
        )
        assert RBRNonInteractive.FLAG_NON_INTERACTIVE in instructions


# =============================================================================
# TestGitIssuesAck
# =============================================================================


class TestGitIssuesAck:
    """O ack de estado do git e escopado por id e vem da invocacao."""

    @staticmethod
    def _issue(check_id: str, label: str) -> GitCheckIssue:
        return GitCheckIssue(id=check_id, check=label, details="detalhe")

    @staticmethod
    def _base_patches(flow_func, issues):
        """
        Patches comuns a todo deploy destes testes.

        Retornados como lista para entrarem em um ExitStack — a forma
        parentizada do `with` nao aceita desempacotamento.
        """
        p1, p2 = _patch_prefect_calls(flow_func)
        return [
            patch(
                "rbr_prefect.deploy.GitHubSourceStrategy.run_git_checks",
                return_value=issues,
            ),
            patch("rbr_prefect.deploy.print_git_check_panel"),
            p1,
            p2,
        ]

    def test_accepted_id_skips_prompt(self, mock_git, mock_ui, flow_func, monkeypatch):
        monkeypatch.setattr(
            _interaction,
            "_argv",
            lambda: [
                f"{RBRNonInteractive.FLAG_ACCEPT_GIT_ISSUES}={RBRGitChecks.DIRTY_MAIN}"
            ],
        )
        issues = [
            self._issue(RBRGitChecks.DIRTY_MAIN, GitCheckMessages.CHECK_DIRTY_MAIN)
        ]
        deploy = _make_deploy(flow_func)

        with ExitStack() as stack:
            for ctx in self._base_patches(flow_func, issues):
                stack.enter_context(ctx)
            mock_confirm = stack.enter_context(
                patch("rbr_prefect.deploy.confirm_git_issues")
            )
            mock_accepted = stack.enter_context(
                patch("rbr_prefect.deploy.print_git_issues_accepted")
            )
            deploy.deploy()

        mock_confirm.assert_not_called()
        mock_accepted.assert_called_once()

    def test_unaccepted_id_still_prompts_with_terminal(
        self, mock_git, mock_ui, flow_func, monkeypatch
    ):
        """
        Aceitar dirty_main nao autoriza um unpushed_main que apareca na mesma
        execucao. A cobertura e por id, nao por quantidade.
        """
        monkeypatch.setattr(
            _interaction,
            "_argv",
            lambda: [
                f"{RBRNonInteractive.FLAG_ACCEPT_GIT_ISSUES}={RBRGitChecks.DIRTY_MAIN}"
            ],
        )
        issues = [
            self._issue(RBRGitChecks.DIRTY_MAIN, GitCheckMessages.CHECK_DIRTY_MAIN),
            self._issue(
                RBRGitChecks.UNPUSHED_MAIN, GitCheckMessages.CHECK_UNPUSHED_MAIN
            ),
        ]
        deploy = _make_deploy(flow_func)

        with ExitStack() as stack:
            for ctx in self._base_patches(flow_func, issues):
                stack.enter_context(ctx)
            mock_confirm = stack.enter_context(
                patch("rbr_prefect.deploy.confirm_git_issues", return_value=True)
            )
            deploy.deploy()

        mock_confirm.assert_called_once()

    def test_unaccepted_id_reports_only_the_unaccepted(
        self, mock_git, mock_ui, flow_func, monkeypatch, non_interactive
    ):
        monkeypatch.setenv(
            RBRNonInteractive.ENV_ACCEPT_GIT_ISSUES, RBRGitChecks.DIRTY_MAIN
        )
        issues = [
            self._issue(RBRGitChecks.DIRTY_MAIN, GitCheckMessages.CHECK_DIRTY_MAIN),
            self._issue(
                RBRGitChecks.UNPUSHED_MAIN, GitCheckMessages.CHECK_UNPUSHED_MAIN
            ),
        ]
        deploy = _make_deploy(flow_func)

        with ExitStack() as stack:
            for ctx in self._base_patches(flow_func, issues):
                stack.enter_context(ctx)
            mock_panel = stack.enter_context(
                patch("rbr_prefect.deploy.print_pending_acks_panel")
            )
            with pytest.raises(SystemExit) as exc_info:
                deploy.deploy()

        assert exc_info.value.code == RBRNonInteractive.EXIT_CODE
        instructions = " ".join(
            instruction for _, instruction in mock_panel.call_args[0][0]
        )
        assert RBRGitChecks.UNPUSHED_MAIN in instructions
        assert RBRGitChecks.DIRTY_MAIN not in instructions

    def test_all_accepted_runs_without_terminal(
        self, mock_git, mock_ui, flow_func, monkeypatch
    ):
        """Caminho autonomo completo: modo declarado e todas as issues nomeadas."""
        monkeypatch.setattr(_interaction, "stdin_is_tty", lambda: False)
        monkeypatch.setattr(
            _interaction,
            "_argv",
            lambda: [
                RBRNonInteractive.FLAG_NON_INTERACTIVE,
                f"{RBRNonInteractive.FLAG_ACCEPT_GIT_ISSUES}={RBRGitChecks.DIRTY_MAIN}",
            ],
        )
        issues = [
            self._issue(RBRGitChecks.DIRTY_MAIN, GitCheckMessages.CHECK_DIRTY_MAIN)
        ]
        deploy = _make_deploy(flow_func)

        with ExitStack() as stack:
            for ctx in self._base_patches(flow_func, issues):
                stack.enter_context(ctx)
            stack.enter_context(patch("rbr_prefect.deploy.print_git_issues_accepted"))
            mock_handoff = stack.enter_context(
                patch("rbr_prefect.deploy.print_handoff")
            )
            deploy.deploy()

        mock_handoff.assert_called_once()

    def test_no_issues_needs_no_ack(
        self, mock_git, mock_ui, flow_func, non_interactive
    ):
        deploy = _make_deploy(flow_func)

        with ExitStack() as stack:
            for ctx in self._base_patches(flow_func, []):
                stack.enter_context(ctx)
            mock_confirm = stack.enter_context(
                patch("rbr_prefect.deploy.confirm_git_issues")
            )
            mock_handoff = stack.enter_context(
                patch("rbr_prefect.deploy.print_handoff")
            )
            deploy.deploy()

        mock_confirm.assert_not_called()
        mock_handoff.assert_called_once()


# =============================================================================
# TestGitCheckIds
# =============================================================================


class TestGitCheckIds:
    """Os ids dos checks sao o vocabulario do ack — precisam existir e ser estaveis."""

    def test_every_issue_carries_a_known_id(self, mock_git, fake_repo_root):
        """
        Todo GitCheckIssue produzido por run_git_checks carrega um id de
        RBRGitChecks. Um id fora da lista tornaria a issue impossivel de aceitar.
        """
        from rbr_prefect.deploy import GitHubSourceStrategy

        def failing_run(cmd, **kwargs):
            result = MagicMock()
            if "--show-toplevel" in cmd:
                result.returncode = 0
                result.stdout = str(fake_repo_root) + "\n"
            elif "--abbrev-ref" in cmd:
                result.returncode = 0
                result.stdout = "main\n"
            else:
                result.returncode = 1
                result.stdout = ""
                result.stderr = "boom"
            return result

        strategy = GitHubSourceStrategy()
        with patch("subprocess.run", side_effect=failing_run):
            issues = strategy.run_git_checks()

        assert issues
        for issue in issues:
            assert issue.id in RBRGitChecks.ALL

    def test_default_work_pool_needs_no_ack(self, mock_git, mock_ui, flow_func):
        """Sanidade: os pools RBR conhecidos nao acionam confirmacao alguma."""
        with patch("rbr_prefect.deploy.confirm_work_pool_override") as mock_confirm:
            _make_deploy(flow_func, work_pool_name=RBRWorkPools.DEFAULT)
        mock_confirm.assert_not_called()
