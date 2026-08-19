"""
Resolucao do modo de interacao e dos acks declarados na invocacao.

Este modulo responde perguntas — nunca decide, nunca imprime, nunca aborta.
Toda decisao de fluxo baseada nas suas respostas pertence ao deploy.py.

O principio que ele serve: se a intencao esta declarada, roda; se nao esta,
pergunta; se nao pode perguntar, falha dizendo o que declarar. Este modulo
responde apenas as duas primeiras metades — o que foi declarado, e se e
possivel perguntar.
"""

import os
import sys

from rbr_prefect.constants import RBRNonInteractive


def _argv() -> list[str]:
    """
    Retorna os argumentos da invocacao, sem o nome do programa.

    Isolado em uma funcao para permitir monkeypatch nos testes sem mexer no
    sys.argv real do processo de teste.
    """
    return sys.argv[1:]


def _flag_present(flag: str) -> bool:
    """
    Verifica presenca de uma flag booleana no argv.

    Aceita tanto a forma nua (--rbr-flag) quanto a forma com valor
    (--rbr-flag=1), para tolerar como um agente ou script possa escrever.
    """
    for arg in _argv():
        if arg == flag or arg.startswith(f"{flag}="):
            return True
    return False


def _flag_value(flag: str) -> str | None:
    """
    Extrai o valor de uma flag do argv.

    Aceita as formas `--rbr-flag=valor` e `--rbr-flag valor`. Na forma
    separada, o token seguinte so e consumido se nao for ele mesmo uma flag
    --rbr-, evitando engolir a flag seguinte quando o valor foi omitido.

    Retorna None quando a flag nao esta presente, e "" quando esta presente sem
    valor — a distincao importa: ausencia significa "nao declarado", presente e
    vazia significa "declarado como conjunto vazio".
    """
    args = _argv()
    for index, arg in enumerate(args):
        if arg.startswith(f"{flag}="):
            return arg.split("=", 1)[1]
        if arg == flag:
            following = args[index + 1] if index + 1 < len(args) else None
            if following is None or following.startswith(
                RBRNonInteractive.FLAG_PREFIX
            ):
                return ""
            return following
    return None


def _split_ids(raw: str) -> set[str]:
    """Separa uma lista de ids em texto, descartando entradas vazias."""
    return {
        part.strip()
        for part in raw.split(RBRNonInteractive.ID_SEPARATOR)
        if part.strip()
    }


def non_interactive_declared() -> bool:
    """
    Indica se o modo nao-interativo foi declarado explicitamente.

    A declaracao e sempre explicita: a mera ausencia de terminal nao habilita o
    modo autonomo. Se habilitasse, qualquer contexto sem TTY — CI, cron, saida
    redirecionada — passaria a pular a revisao final silenciosamente, que e o
    comportamento de uma flag global concedida por acidente.
    """
    if _flag_present(RBRNonInteractive.FLAG_NON_INTERACTIVE):
        return True
    return bool(os.environ.get(RBRNonInteractive.ENV_NON_INTERACTIVE))


def stdin_is_tty() -> bool:
    """
    Indica se ha um terminal interativo ligado ao stdin.

    Tolera stdin ausente ou substituido (isatty pode nao existir), caso em que
    assume ausencia de terminal — o lado seguro, que leva a reportar pendencias
    em vez de tentar promptar.
    """
    try:
        return bool(sys.stdin.isatty())
    except (AttributeError, ValueError):
        return False


def can_prompt() -> bool:
    """
    Indica se o pacote pode fazer uma pergunta ao dev.

    Unica funcao consultada pelo deploy.py para escolher entre promptar e
    reportar pendencia.
    """
    return stdin_is_tty() and not non_interactive_declared()


def accepted_git_issues() -> set[str]:
    """
    Retorna os ids de issues de git aceitos na invocacao.

    A flag de argv tem precedencia sobre a env var: quando presente, a env var e
    integralmente ignorada, sem uniao entre as fontes. Uniao permitiria que uma
    env var esquecida na sessao do shell ampliasse silenciosamente um ack
    escrito na linha de comando.
    """
    from_flag = _flag_value(RBRNonInteractive.FLAG_ACCEPT_GIT_ISSUES)
    if from_flag is not None:
        return _split_ids(from_flag)
    return _split_ids(os.environ.get(RBRNonInteractive.ENV_ACCEPT_GIT_ISSUES, ""))
