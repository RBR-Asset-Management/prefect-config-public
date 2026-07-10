"""
Classes para disparar deployments de flows Prefect da RBR.

Enquanto `deploy.py` cuida do registro (deploy) de flows no servidor Prefect,
este modulo cuida de *disparar* deployments ja registrados. Hoje expoe
EnvioEmailTrigger, um wrapper tipado sobre `run_deployment` que dispara o flow
de envio de e-mail (Microsoft Graph / Outlook) passando os argumentos corretos e
normalizando anexos (caminhos de arquivo, bytes ou dicts base64) para o formato
esperado pelo flow.
"""

import base64
import binascii
from pathlib import Path
from typing import Any
from uuid import UUID

from prefect.client.schemas.objects import FlowRun
from prefect.deployments import run_deployment

from rbr_prefect._cli import (
    print_trigger_result,
    print_trigger_summary,
)
from rbr_prefect._cli.messages import ValidationMessages
from rbr_prefect.constants import RBREmailFlow

# Formatos aceitos para cada anexo informado pelo dev:
#   - str | Path        -> caminho de um arquivo local (lido e codificado em base64)
#   - tuple[str, bytes] -> (nome_do_arquivo, conteudo_em_bytes)
#   - dict[str, str]    -> {"name": ..., "content": <base64>} ja no formato do flow
AttachmentInput = str | Path | tuple[str, bytes] | dict[str, str]


class EnvioEmailTrigger:
    """
    Dispara o fluxo de envio de e-mail (Microsoft Graph / Outlook) da RBR.

    Wrapper tipado sobre `prefect.deployments.run_deployment` que valida os
    argumentos, normaliza os anexos para o formato esperado pelo flow e dispara
    o deployment de envio de e-mail identificado por `RBREmailFlow.DEPLOYMENT_ID`.

    Toda validacao e a leitura/codificacao dos anexos ocorrem na construcao
    (`__init__`) — falhando cedo, sem tocar a rede. A unica chamada com efeitos
    colaterais (acesso a API do Prefect) e o metodo `run()`.

    Anexos aceitam tres formatos, misturaveis na mesma lista:

    - Caminho de arquivo (`str` ou `Path`): o arquivo e lido do disco e
      codificado em base64; o nome do anexo e o nome do arquivo.
    - Tupla `(nome, bytes)`: util para conteudo gerado em memoria.
    - Dict `{"name": str, "content": <base64>}`: ja no formato do flow, para
      quem prefere codificar o base64 manualmente.

    Usage
    -----
        from rbr_prefect import EnvioEmailTrigger

        trigger = EnvioEmailTrigger(
            to=["fulano@rbrasset.com.br"],
            subject="Relatorio diario",
            body_html="<p>Segue em anexo o relatorio.</p>",
            cc=["gestor@rbrasset.com.br"],
            attachments=[
                "relatorio.pdf",               # caminho -> base64 automatico
                ("dados.csv", meu_csv_bytes),  # nome + bytes
            ],
        )

        # Dispara e retorna imediatamente (fire-and-forget):
        flow_run = trigger.run()

        # Ou aguarda a conclusao do envio:
        flow_run = trigger.run(wait=True)
    """

    def __init__(
        self,
        to: list[str],
        subject: str,
        body_html: str,
        cc: list[str] | None = None,
        bcc: list[str] | None = None,
        attachments: list[AttachmentInput] | None = None,
        block_slug: str = RBREmailFlow.DEFAULT_BLOCK_SLUG,
    ) -> None:
        # 1. Validar campos obrigatorios
        if not to:
            raise ValueError(ValidationMessages.EMAIL_TO_REQUIRED)
        if not subject:
            raise ValueError(ValidationMessages.EMAIL_SUBJECT_REQUIRED)
        if not body_html:
            raise ValueError(ValidationMessages.EMAIL_BODY_REQUIRED)

        # 2. Armazenar atributos
        self._to = to
        self._subject = subject
        self._body_html = body_html
        self._cc = cc or []
        self._bcc = bcc or []
        self._block_slug = block_slug

        # 3. Normalizar anexos (le arquivos e codifica base64 — fail-early)
        self._attachments = self._normalize_attachments(attachments or [])

    # -------------------------------------------------------------------------
    # Normalizacao de anexos
    # -------------------------------------------------------------------------

    def _normalize_attachments(
        self, attachments: list[AttachmentInput]
    ) -> list[dict[str, str]]:
        """Converte cada anexo informado para o formato {'name', 'content'}."""
        return [
            self._normalize_attachment(item, index)
            for index, item in enumerate(attachments)
        ]

    def _normalize_attachment(
        self, item: AttachmentInput, index: int
    ) -> dict[str, str]:
        """Normaliza um unico anexo, despachando conforme o tipo informado."""
        if isinstance(item, dict):
            return self._normalize_dict_attachment(item, index)
        if isinstance(item, tuple):
            return self._normalize_tuple_attachment(item, index)
        if isinstance(item, (str, Path)):
            return self._normalize_path_attachment(item, index)
        raise ValueError(
            ValidationMessages.attachment_invalid_type(index, type(item).__name__)
        )

    def _normalize_path_attachment(
        self, item: str | Path, index: int
    ) -> dict[str, str]:
        """Le um arquivo do disco e o codifica em base64."""
        path = Path(item)
        if not path.exists():
            raise ValueError(ValidationMessages.attachment_not_found(index, str(path)))
        if not path.is_file():
            raise ValueError(ValidationMessages.attachment_not_file(index, str(path)))
        return self._encode_attachment(path.name, path.read_bytes(), index)

    def _normalize_tuple_attachment(
        self, item: tuple, index: int
    ) -> dict[str, str]:
        """Normaliza uma tupla (nome, bytes)."""
        if (
            len(item) != 2
            or not isinstance(item[0], str)
            or not item[0]
            or not isinstance(item[1], (bytes, bytearray))
        ):
            raise ValueError(
                ValidationMessages.attachment_invalid_type(index, type(item).__name__)
            )
        name, raw = item
        return self._encode_attachment(name, bytes(raw), index)

    def _normalize_dict_attachment(
        self, item: dict, index: int
    ) -> dict[str, str]:
        """Valida um dict {'name', 'content'} ja em base64 vindo do dev."""
        name = item.get("name")
        content = item.get("content")
        if not isinstance(name, str) or not name or not isinstance(content, str):
            raise ValueError(ValidationMessages.attachment_dict_keys(index))

        # Decodifica apenas para validar o base64 e conferir o tamanho; o content
        # original e preservado (o flow normaliza base64url/padding no envio).
        try:
            raw = base64.b64decode(content)
        except (binascii.Error, ValueError):
            raise ValueError(
                ValidationMessages.attachment_invalid_b64(index, name)
            ) from None

        self._check_size(name, len(raw), index)
        return {"name": name, "content": content}

    def _encode_attachment(
        self, name: str, raw: bytes, index: int
    ) -> dict[str, str]:
        """Confere o tamanho e codifica os bytes em base64."""
        self._check_size(name, len(raw), index)
        content = base64.b64encode(raw).decode("ascii")
        return {"name": name, "content": content}

    def _check_size(self, name: str, size_bytes: int, index: int) -> None:
        """Garante que o anexo respeita o limite de tamanho do flow."""
        if size_bytes > RBREmailFlow.MAX_ATTACHMENT_SIZE:
            megabyte = 1024 * 1024
            raise ValueError(
                ValidationMessages.attachment_too_large(
                    index,
                    name,
                    size_bytes / megabyte,
                    RBREmailFlow.MAX_ATTACHMENT_SIZE / megabyte,
                )
            )

    # -------------------------------------------------------------------------
    # Propriedades
    # -------------------------------------------------------------------------

    @property
    def parameters(self) -> dict[str, Any]:
        """
        Parametros que serao enviados ao deployment do flow de e-mail.

        Espelha exatamente a assinatura do flow `enviar_email`.
        """
        return {
            "to": self._to,
            "subject": self._subject,
            "body_html": self._body_html,
            "cc": self._cc,
            "bcc": self._bcc,
            "attachments": self._attachments,
            "block_slug": self._block_slug,
        }

    # -------------------------------------------------------------------------
    # Disparo (unico metodo com efeitos colaterais)
    # -------------------------------------------------------------------------

    def run(
        self,
        wait: bool = False,
        timeout: float | None = None,
        poll_interval: float = 5.0,
        flow_run_name: str | None = None,
        tags: list[str] | None = None,
        as_subflow: bool = True,
        verbose: bool = True,
    ) -> FlowRun:
        """
        Dispara o deployment de envio de e-mail no servidor Prefect da RBR.

        Este e o unico metodo com efeitos colaterais da classe — nenhuma
        chamada de rede ocorre antes dele.

        Parameters
        ----------
        wait : bool
            Se False (default), dispara e retorna imediatamente (fire-and-forget).
            Se True, aguarda o flow terminar e o FlowRun retornado ja trara o
            estado final.
        timeout : float | None
            Usado apenas quando `wait=True`. Segundos maximos de espera pela
            conclusao; None aguarda indefinidamente. Ignorado quando `wait=False`.
        poll_interval : float
            Intervalo em segundos entre verificacoes de estado quando `wait=True`.
        flow_run_name : str | None
            Nome customizado opcional para o flow run criado.
        tags : list[str] | None
            Tags opcionais aplicadas ao flow run.
        as_subflow : bool
            Quando disparado de dentro de outro flow, vincula o run como subflow
            na UI do Prefect (default True).
        verbose : bool
            Quando True (default), exibe paineis-resumo do disparo e do resultado.
            Desligue para disparos silenciosos (ex.: dentro de outros flows).

        Returns
        -------
        FlowRun
            O flow run criado. Quando `wait=False`, retorna sem estado final
            (o envio ocorre de forma assincrona no worker).
        """
        if verbose:
            print_trigger_summary(
                recipients=self._to,
                subject=self._subject,
                cc=self._cc,
                bcc=self._bcc,
                attachments_count=len(self._attachments),
                wait=wait,
            )

        # timeout=0 faz run_deployment retornar imediatamente (fire-and-forget).
        effective_timeout = timeout if wait else 0

        flow_run = run_deployment(
            name=UUID(RBREmailFlow.DEPLOYMENT_ID),
            parameters=self.parameters,
            timeout=effective_timeout,
            poll_interval=poll_interval,
            flow_run_name=flow_run_name,
            tags=tags,
            as_subflow=as_subflow,
        )

        if verbose:
            print_trigger_result(
                flow_run_name=flow_run.name,
                flow_run_id=str(flow_run.id),
                state_name=flow_run.state.name if flow_run.state else None,
            )

        return flow_run
