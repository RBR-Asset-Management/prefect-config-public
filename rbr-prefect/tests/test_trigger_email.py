# standard library
import base64
from unittest.mock import MagicMock, patch
from uuid import UUID

# third-party
import pytest

# internal
from rbr_prefect import EnvioEmailTrigger
from rbr_prefect.constants import RBREmailFlow


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_run_deployment():
    """Mocka run_deployment em trigger.py e retorna um FlowRun falso."""
    fake_flow_run = MagicMock()
    fake_flow_run.name = "fake-run"
    fake_flow_run.id = UUID("11111111-1111-1111-1111-111111111111")
    fake_flow_run.state = None
    with patch(
        "rbr_prefect.trigger.run_deployment", return_value=fake_flow_run
    ) as mock:
        yield mock


def _make_trigger(**overrides) -> EnvioEmailTrigger:
    """Cria um EnvioEmailTrigger valido, aceitando overrides pontuais."""
    kwargs = {
        "to": ["dest@rbrasset.com.br"],
        "subject": "Assunto",
        "body_html": "<p>Corpo</p>",
    }
    kwargs.update(overrides)
    return EnvioEmailTrigger(**kwargs)


# =============================================================================
# TestValidacaoObrigatorios
# =============================================================================


class TestValidacaoObrigatorios:
    """Valida os campos obrigatorios do e-mail no __init__."""

    def test_to_vazio_levanta_erro(self):
        with pytest.raises(ValueError):
            _make_trigger(to=[])

    def test_subject_vazio_levanta_erro(self):
        with pytest.raises(ValueError):
            _make_trigger(subject="")

    def test_body_vazio_levanta_erro(self):
        with pytest.raises(ValueError):
            _make_trigger(body_html="")


# =============================================================================
# TestParametros
# =============================================================================


class TestParametros:
    """Valida o mapeamento de parametros para a assinatura do flow."""

    def test_defaults_de_cc_bcc_e_attachments(self):
        trigger = _make_trigger()
        params = trigger.parameters
        assert params["cc"] == []
        assert params["bcc"] == []
        assert params["attachments"] == []

    def test_block_slug_default(self):
        trigger = _make_trigger()
        assert trigger.parameters["block_slug"] == RBREmailFlow.DEFAULT_BLOCK_SLUG

    def test_parametros_espelham_a_entrada(self):
        trigger = _make_trigger(
            to=["a@rbr.com"],
            subject="S",
            body_html="<b>B</b>",
            cc=["c@rbr.com"],
            bcc=["b@rbr.com"],
        )
        params = trigger.parameters
        assert params["to"] == ["a@rbr.com"]
        assert params["subject"] == "S"
        assert params["body_html"] == "<b>B</b>"
        assert params["cc"] == ["c@rbr.com"]
        assert params["bcc"] == ["b@rbr.com"]


# =============================================================================
# TestNormalizacaoAnexos
# =============================================================================


class TestNormalizacaoAnexos:
    """Valida a normalizacao dos tres formatos de anexo aceitos."""

    def test_anexo_via_caminho(self, tmp_path):
        arquivo = tmp_path / "relatorio.txt"
        arquivo.write_bytes(b"conteudo")
        trigger = _make_trigger(attachments=[arquivo])

        anexo = trigger.parameters["attachments"][0]
        assert anexo["name"] == "relatorio.txt"
        assert base64.b64decode(anexo["content"]) == b"conteudo"

    def test_anexo_via_caminho_string(self, tmp_path):
        arquivo = tmp_path / "dados.csv"
        arquivo.write_bytes(b"a,b,c")
        trigger = _make_trigger(attachments=[str(arquivo)])
        assert trigger.parameters["attachments"][0]["name"] == "dados.csv"

    def test_anexo_via_tupla_nome_bytes(self):
        trigger = _make_trigger(attachments=[("memoria.bin", b"\x00\x01\x02")])
        anexo = trigger.parameters["attachments"][0]
        assert anexo["name"] == "memoria.bin"
        assert base64.b64decode(anexo["content"]) == b"\x00\x01\x02"

    def test_anexo_via_dict_base64(self):
        content = base64.b64encode(b"pronto").decode("ascii")
        trigger = _make_trigger(
            attachments=[{"name": "x.txt", "content": content}]
        )
        assert trigger.parameters["attachments"][0]["content"] == content

    def test_formatos_misturados(self, tmp_path):
        arquivo = tmp_path / "f.txt"
        arquivo.write_bytes(b"z")
        trigger = _make_trigger(
            attachments=[
                arquivo,
                ("g.bin", b"\x00"),
                {"name": "h.txt", "content": base64.b64encode(b"h").decode()},
            ]
        )
        assert len(trigger.parameters["attachments"]) == 3

    def test_caminho_inexistente_levanta_erro(self, tmp_path):
        with pytest.raises(ValueError):
            _make_trigger(attachments=[tmp_path / "nao_existe.pdf"])

    def test_diretorio_como_anexo_levanta_erro(self, tmp_path):
        with pytest.raises(ValueError):
            _make_trigger(attachments=[tmp_path])

    def test_dict_sem_chaves_levanta_erro(self):
        with pytest.raises(ValueError):
            _make_trigger(attachments=[{"name": "x.txt"}])

    def test_dict_com_base64_invalido_levanta_erro(self):
        with pytest.raises(ValueError):
            _make_trigger(attachments=[{"name": "x.txt", "content": "!!!nao-b64!!!"}])

    def test_tipo_invalido_levanta_erro(self):
        with pytest.raises(ValueError):
            _make_trigger(attachments=[12345])

    def test_anexo_acima_do_limite_levanta_erro(self, monkeypatch):
        monkeypatch.setattr(RBREmailFlow, "MAX_ATTACHMENT_SIZE", 10)
        with pytest.raises(ValueError):
            _make_trigger(attachments=[("grande.bin", b"x" * 11)])


# =============================================================================
# TestRun
# =============================================================================


class TestRun:
    """Valida o disparo via run_deployment."""

    def test_fire_and_forget_usa_timeout_zero(self, mock_run_deployment):
        trigger = _make_trigger()
        trigger.run(verbose=False)

        _, kwargs = mock_run_deployment.call_args
        assert kwargs["timeout"] == 0

    def test_dispara_pelo_uuid_do_deployment(self, mock_run_deployment):
        trigger = _make_trigger()
        trigger.run(verbose=False)

        _, kwargs = mock_run_deployment.call_args
        assert kwargs["name"] == UUID(RBREmailFlow.DEPLOYMENT_ID)

    def test_envia_parametros_corretos(self, mock_run_deployment):
        trigger = _make_trigger(cc=["c@rbr.com"])
        trigger.run(verbose=False)

        _, kwargs = mock_run_deployment.call_args
        assert kwargs["parameters"] == trigger.parameters

    def test_wait_sem_timeout_aguarda_indefinidamente(self, mock_run_deployment):
        trigger = _make_trigger()
        trigger.run(wait=True, verbose=False)

        _, kwargs = mock_run_deployment.call_args
        assert kwargs["timeout"] is None

    def test_wait_com_timeout_repassa_valor(self, mock_run_deployment):
        trigger = _make_trigger()
        trigger.run(wait=True, timeout=30, verbose=False)

        _, kwargs = mock_run_deployment.call_args
        assert kwargs["timeout"] == 30

    def test_retorna_o_flow_run(self, mock_run_deployment):
        trigger = _make_trigger()
        flow_run = trigger.run(verbose=False)
        assert flow_run is mock_run_deployment.return_value
