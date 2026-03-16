"""
Logica de apresentacao com rich para o terminal.

Este arquivo contem toda a formatacao, cores, paineis e prompts.
Nenhum texto literal aparece aqui - apenas referencias a messages.py.
"""

import sys

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.rule import Rule
from rich.table import Table

from rbr_prefect._cli.messages import (
    ConcurrencyMessages,
    DeployMessages,
    EnvMessages,
    JobVariablesMessages,
    RequirementsMessages,
    ScheduleMessages,
    WorkPoolMessages,
)

_console = Console(file=sys.stdout)


def print_audit_panel(
    resolved: dict,
    overrides: dict,
    env_override_active: bool = False,
    job_variables_override_active: bool = False,
) -> None:
    """
    Exibe o painel de auditoria com todos os valores resolvidos e overrides.

    Parameters
    ----------
    resolved : dict
        Valores resolvidos automaticamente (github_url, branch, entrypoint, etc.)
    overrides : dict
        Overrides aplicados pelo dev (parameters, extra_env, etc.)
    env_override_active : bool
        Se True, exibe aviso de override total do env
    job_variables_override_active : bool
        Se True, exibe aviso de override total de job_variables
    """
    # Tabela de valores resolvidos
    resolved_table = Table(show_header=False, box=None, padding=(0, 2))
    resolved_table.add_column("Campo", style="cyan")
    resolved_table.add_column("Valor", style="white")

    for key, value in resolved.items():
        resolved_table.add_row(key, str(value))

    _console.print()
    _console.print(
        Panel(
            resolved_table,
            title=f"[bold]{DeployMessages.RESOLVED_HEADER}[/bold]",
            border_style="blue",
        )
    )

    # Tabela de overrides (se houver)
    if overrides:
        overrides_table = Table(show_header=False, box=None, padding=(0, 2))
        overrides_table.add_column("Campo", style="yellow")
        overrides_table.add_column("Valor", style="white")

        for key, value in overrides.items():
            overrides_table.add_row(key, str(value))

        _console.print(
            Panel(
                overrides_table,
                title=f"[bold]{DeployMessages.OVERRIDES_HEADER}[/bold]",
                border_style="yellow",
            )
        )

    # Avisos de override total
    if job_variables_override_active:
        _console.print(
            Panel(
                f"[bold red]{JobVariablesMessages.OVERRIDE_WARNING}[/bold red]",
                border_style="red",
            )
        )

    if env_override_active:
        _console.print(
            Panel(
                f"[bold red]{EnvMessages.OVERRIDE_WARNING}[/bold red]",
                border_style="red",
            )
        )


def print_requirements_panel(
    requirements: list[str] | None,
    detection_mode: str | None,
) -> None:
    """
    Exibe o painel de requirements com os pacotes detectados.

    Parameters
    ----------
    requirements : list[str] | None
        Lista de pacotes detectados, ou None quando nao ha requirements.
    detection_mode : str | None
        Descricao de como os requirements foram obtidos (subtitulo do painel).
    """
    if not requirements:
        _console.print(
            Panel(
                RequirementsMessages.NO_REQUIREMENTS,
                title=f"[bold]{RequirementsMessages.PANEL_HEADER}[/bold]",
                border_style="cyan",
            )
        )
        return

    MAX_SHOWN = 5
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Pacote", style="white")

    shown = requirements[:MAX_SHOWN]
    omitted = len(requirements) - MAX_SHOWN

    for pkg in shown:
        table.add_row(pkg)

    if omitted > 0:
        table.add_row(f"[dim]{RequirementsMessages.truncated(omitted)}[/dim]")

    _console.print(
        Panel(
            table,
            title=f"[bold]{RequirementsMessages.PANEL_HEADER}[/bold]",
            subtitle=detection_mode,
            border_style="cyan",
        )
    )


def print_env_panel(env: dict) -> None:
    """
    Exibe o painel de variaveis de ambiente resolvidas.

    Parameters
    ----------
    env : dict
        Dict env final apos merge das tres camadas.
    """
    env_table = Table(show_header=False, box=None, padding=(0, 2))
    env_table.add_column("Variavel", style="green")
    env_table.add_column("Valor", style="white", overflow="fold")

    for key, value in env.items():
        # Truncar valores muito longos para melhor visualizacao
        display_value = str(value)
        if len(display_value) > 60:
            display_value = display_value[:57] + "..."
        env_table.add_row(key, display_value)

    _console.print(
        Panel(
            env_table,
            title=f"[bold]{DeployMessages.ENV_HEADER}[/bold]",
            border_style="green",
        )
    )
    _console.print()


def print_handoff(name: str) -> None:
    """
    Exibe o separador visual de passagem de responsabilidade ao Prefect.

    Esta deve ser a ultima chamada a ui.py antes de deployable.deploy().
    """
    _console.print(DeployMessages.deploy_starting(name))
    _console.print(Rule(DeployMessages.HANDOFF_MESSAGE, style="green"))


def confirm_work_pool_override(pool_name: str) -> bool:
    """
    Exibe aviso e solicita confirmacao para override do work pool.

    Returns
    -------
    bool
        True se confirmado, False se negado.
    """
    _console.print()
    _console.print(WorkPoolMessages.OVERRIDE_WARNING, style="yellow")
    confirmed = Confirm.ask(WorkPoolMessages.override_confirm(pool_name))
    if not confirmed:
        _console.print(WorkPoolMessages.OVERRIDE_ABORTED, style="red")
    return confirmed


def confirm_concurrency_limit() -> bool:
    """
    Exibe aviso e solicita confirmacao para configuracao de concurrency limit.

    Returns
    -------
    bool
        True se confirmado, False se negado.
    """
    _console.print()
    _console.print(ConcurrencyMessages.WARNING, style="yellow")
    confirmed = Confirm.ask(ConcurrencyMessages.CONFIRM)
    if not confirmed:
        _console.print(ConcurrencyMessages.ABORTED, style="red")
    return confirmed


def confirm_advanced_schedule() -> bool:
    """
    Exibe aviso e solicita confirmacao para uso de schedule avancado.

    Returns
    -------
    bool
        True se confirmado, False se negado.
    """
    _console.print()
    _console.print(ScheduleMessages.ADVANCED_WARNING, style="yellow")
    confirmed = Confirm.ask(ScheduleMessages.ADVANCED_CONFIRM)
    if not confirmed:
        _console.print(ScheduleMessages.ABORTED, style="red")
    return confirmed
