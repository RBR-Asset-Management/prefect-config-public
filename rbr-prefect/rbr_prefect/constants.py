"""
Constantes de infraestrutura da RBR para deploys Prefect.

Este arquivo é a fonte única da verdade para toda configuração de infraestrutura.
Nenhum valor literal de configuração deve aparecer em outros arquivos do pacote.
"""

import re

_WEEKDAYS_EN_PT: dict[str, str] = {
    "monday": "segunda-feira",
    "tuesday": "terça-feira",
    "wednesday": "quarta-feira",
    "thursday": "quinta-feira",
    "friday": "sexta-feira",
    "saturday": "sábado",
    "sunday": "domingo",
}

_MONTHS_EN_PT: dict[str, str] = {
    "january": "janeiro",
    "february": "fevereiro",
    "march": "março",
    "april": "abril",
    "may": "maio",
    "june": "junho",
    "july": "julho",
    "august": "agosto",
    "september": "setembro",
    "october": "outubro",
    "november": "novembro",
    "december": "dezembro",
}


class RBRPrefectServer:
    """Configurações de conexão com o servidor Prefect da RBR."""

    API_URL = "https://prefect-eve.rbr.local/api"
    SSL_CERT_PATH = "/host-certs/rbr-root-ca.crt"


class RBRDocker:
    """Imagens Docker e configurações de container para deploys."""

    DEFAULT_IMAGE = "prefecthq/prefect:3-python3.12"

    SCRAPE_IMAGE = "10.214.20.79:5000/prefect-rbr-sql-scrape:3-ptyhon3.12"

    SQL_IMAGE = "10.214.20.79:5000/prefect-rbr-sql:3-python3.12"

    CERT_VOLUME = "/home/rbr-admin/certs:/host-certs:ro"


class RBRWorkPools:
    """Nomes dos work pools do Prefect configurados no servidor da RBR."""

    DEFAULT = "default"
    PROCESS = "windows"

    # Work pools RBR conhecidos — nao disparam o prompt de override de work pool.
    KNOWN = (DEFAULT, PROCESS)


class RBRBlocks:
    """Nomes dos blocos do Prefect utilizados nos deploys."""

    GITHUB_CREDENTIALS = "rbr-org-github-finegrained-access-token"
    BASIC_AUTH = "walle-basic-auth"

    # Templates internos - não para uso direto fora desta classe
    _BLOCK_TYPE_BASIC_AUTH = "basic-auth-credentials"
    _AUTH_STRING_FIELD = "token_config.auth_string"
    _HEADER_FIELD = "token_config.header"

    @staticmethod
    def auth_string_template() -> str:
        """
        Retorna a string de template do Prefect para o campo auth_string
        do bloco Basic Auth, no formato esperado pela variável de ambiente
        PREFECT_API_AUTH_STRING.

        Formato gerado:
        {{ prefect.blocks.basic-auth-credentials.walle-basic-auth.token_config.auth_string }}
        """
        return (
            f"{{{{ prefect.blocks"
            f".{RBRBlocks._BLOCK_TYPE_BASIC_AUTH}"
            f".{RBRBlocks.BASIC_AUTH}"
            f".{RBRBlocks._AUTH_STRING_FIELD} }}}}"
        )

    @staticmethod
    def header_template() -> str:
        """
        Retorna a string de template do Prefect para o campo header
        do bloco Basic Auth, no formato esperado pela variável de ambiente
        PREFECT_CLIENT_CUSTOM_HEADERS.

        Formato gerado:
        {{ prefect.blocks.basic-auth-credentials.walle-basic-auth.token_config.header }}
        """
        return (
            f"{{{{ prefect.blocks"
            f".{RBRBlocks._BLOCK_TYPE_BASIC_AUTH}"
            f".{RBRBlocks.BASIC_AUTH}"
            f".{RBRBlocks._HEADER_FIELD} }}}}"
        )


class RBRJobVariables:
    """Configurações fixas de job_variables aplicadas a todos os deploys."""

    AUTO_REMOVE = True
    IMAGE_PULL_POLICY = "IfNotPresent"


class RBRDependencyMode:
    """
    Estrategias de gestao de dependencias Python no ambiente de execucao.

    AUTO_INSTALL injeta PREFECT_RUNNER_AUTO_INSTALL_DEPENDENCIES=true, fazendo o
    runner instalar via `uv` as dependencias declaradas em [project].dependencies
    do pyproject.toml do repositorio, em runtime. Requer que `prefect` conste
    nessas dependencias.

    PIP_PACKAGES injeta EXTRA_PIP_PACKAGES (compatibilidade com requirements.txt)
    processado pelo entrypoint da imagem Docker do Prefect.

    Aplica-se apenas a deploys em imagem Docker — deploys em work pool process
    nao gerenciam dependencias (sao responsabilidade do ambiente do worker).
    """

    AUTO_INSTALL = "auto_install"
    PIP_PACKAGES = "pip_packages"

    ALL = (AUTO_INSTALL, PIP_PACKAGES)

    # Valor injetado na env var de auto-install.
    ENABLED_VALUE = "true"

    # Pacote que deve constar em [project].dependencies para o auto-install funcionar.
    REQUIRED_PACKAGE = "prefect"


class RBRAcknowledgements:
    """
    Ids dos acks de intencao de configuracao, declarados no parametro
    `acknowledge` das classes de deploy.

    Cada id autoriza uma confirmacao especifica, dispensando o prompt
    correspondente no terminal. Sao decisoes sobre o conteudo do deploy —
    permanentes por natureza — e por isso a declaracao mora no codigo, ao lado
    do parametro que ela justifica, onde fica visivel no diff e em code review.

    Acks de estado do repositorio NAO ficam aqui: sao efemeros e se declaram na
    invocacao (ver RBRNonInteractive e RBRGitChecks).
    """

    WORK_POOL_OVERRIDE = "work_pool_override"
    CONCURRENCY_LIMIT = "concurrency_limit"
    ADVANCED_SCHEDULE = "advanced_schedule"

    ALL = (WORK_POOL_OVERRIDE, CONCURRENCY_LIMIT, ADVANCED_SCHEDULE)


class RBRGitChecks:
    """
    Ids estaveis dos checks do git pre-flight.

    Estes ids sao o vocabulario do ack escopado de estado: quem aceita uma issue
    de git precisa nomea-la por id na invocacao. Sao identificadores de maquina
    e parte do contrato de invocacao — os labels em portugues exibidos ao dev
    vivem em GitCheckMessages. Cada GitCheckIssue carrega os dois.

    Renomear qualquer valor aqui quebra acks existentes em uso.
    """

    DIRTY_MAIN = "dirty_main"
    DIRTY_SUBMODULES = "dirty_submodules"
    UNPUSHED_MAIN = "unpushed_main"
    UNPUSHED_SUBMODULES = "unpushed_submodules"
    SUBMODULE_PINS = "submodule_pins"
    SUBPROCESS_ERROR = "subprocess_error"

    ALL = (
        DIRTY_MAIN,
        DIRTY_SUBMODULES,
        UNPUSHED_MAIN,
        UNPUSHED_SUBMODULES,
        SUBMODULE_PINS,
        SUBPROCESS_ERROR,
    )


class RBRNonInteractive:
    """
    Contrato de invocacao do modo nao-interativo.

    As flags de sys.argv sao o caminho primario e as env vars um fallback. O
    motivo e ambiental: em PowerShell nao existe prefixo inline de variavel de
    ambiente, entao uma env var definida para um deploy persiste pelo resto da
    sessao do shell e vaza para os deploys seguintes. A flag e efemera por
    construcao, que e o requisito de um ack de estado.

    O prefixo --rbr- delimita o que o pacote le de sys.argv, permitindo que o
    script de deploy tenha seu proprio argparse sem colisao.
    """

    FLAG_PREFIX = "--rbr-"

    FLAG_NON_INTERACTIVE = "--rbr-non-interactive"
    FLAG_ACCEPT_GIT_ISSUES = "--rbr-accept-git-issues"

    ENV_NON_INTERACTIVE = "RBR_PREFECT_NON_INTERACTIVE"
    ENV_ACCEPT_GIT_ISSUES = "RBR_PREFECT_ACCEPT_GIT_ISSUES"

    ID_SEPARATOR = ","

    # Codigo de saida quando o pacote se recusa a prosseguir por falta de
    # autorizacao. Distinto do SystemExit(0) de negacao de prompt: 0 significa
    # que uma pessoa respondeu nao, 2 significa que falta uma declaracao.
    EXIT_CODE = 2


class RBRDateTimeConvention:
    TIMEZONE = "America/Sao_Paulo"
    CRON_DESCRIPTOR_LOCALE = "pt_PT"

    @staticmethod
    def _localize_weekdays(text: str) -> str:
        """Substitui nomes de dias da semana em inglês pelo equivalente em pt-BR."""
        for en, pt in _WEEKDAYS_EN_PT.items():
            text = re.sub(rf"\b{en}\b", pt, text, flags=re.IGNORECASE)
        return text

    @staticmethod
    def _localize_months(text: str) -> str:
        """Substitui nomes de meses em inglês pelo equivalente em pt-BR."""
        for en, pt in _MONTHS_EN_PT.items():
            text = re.sub(rf"\b{en}\b", pt, text, flags=re.IGNORECASE)
        return text


class RBRBaseEnvVariables:
    PREFECT_API_URL = "PREFECT_API_URL"
    PREFECT_API_SSL_CERT_FILE = "PREFECT_API_SSL_CERT_FILE"
    PREFECT_API_AUTH_STRING = "PREFECT_API_AUTH_STRING"
    PREFECT_CLIENT_CUSTOM_HEADERS = "PREFECT_CLIENT_CUSTOM_HEADERS"
    EXTRA_PIP_PACKAGES = "EXTRA_PIP_PACKAGES"
    PREFECT_RUNNER_AUTO_INSTALL_DEPENDENCIES = "PREFECT_RUNNER_AUTO_INSTALL_DEPENDENCIES"


class RBREmailFlow:
    """
    Identificadores do deployment de envio de e-mail via Microsoft Graph (Outlook).

    O flow correspondente vive no repositorio `fluxo-envio-email-comitech`
    (pacote `envio_email_outlook`, funcao `enviar_email`) e envia e-mails a partir
    da caixa de integracao configurada no bloco de credenciais MSAL. Este deployment
    e disparado por outros fluxos/scripts da RBR via EnvioEmailTrigger.
    """

    # ID do deployment registrado no servidor Prefect da RBR. run_deployment aceita
    # o UUID diretamente, o que e mais robusto que a referencia "flow/deployment".
    # ATENCAO: atualizar apos cada novo deploy do flow (o ID muda quando o nome do
    # flow muda, pois passa a ser um novo flow no servidor Prefect).
    DEPLOYMENT_ID = "73986bd5-0d33-419e-b302-054b6cb6c2cc"

    # Referencia textual "flow name/deployment name" (fallback/documentacao).
    DEPLOYMENT_REFERENCE = "Envio e-mail comitech/enviar-email-outlook"

    # Slug default do bloco MSALCredentials usado pelo flow para autenticar no Graph.
    DEFAULT_BLOCK_SLUG = "msal-app-credentials"

    # Limite de tamanho por anexo imposto pelo flow (25 MB, via Microsoft Graph).
    MAX_ATTACHMENT_SIZE = 25 * 1024 * 1024
