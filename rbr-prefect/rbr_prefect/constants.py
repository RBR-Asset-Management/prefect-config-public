"""
Constantes de infraestrutura da RBR para deploys Prefect.

Este arquivo é a fonte única da verdade para toda configuração de infraestrutura.
Nenhum valor literal de configuração deve aparecer em outros arquivos do pacote.
"""


class RBRPrefectServer:
    """Configurações de conexão com o servidor Prefect da RBR."""

    API_URL = "https://prefect-eve.rbr.local/api"
    SSL_CERT_PATH = "/host-certs/rbr-root-ca.crt"


class RBRDocker:
    """Imagens Docker e configurações de container para deploys."""

    DEFAULT_IMAGE = "prefecthq/prefect:3-python3.12"
    SCRAPE_IMAGE = "rbr-custom/prefect-playwright:3-python3.12"
    CERT_VOLUME = "/home/rbr-admin/certs:/host-certs:ro"

    # Variáveis de ambiente do Playwright para ScrapeDeploy
    PLAYWRIGHT_BROWSERS_PATH = "/ms-playwright"
    PLAYWRIGHT_DISPLAY = ""


class RBRWorkPools:
    """Nomes dos work pools do Prefect configurados no servidor da RBR."""

    DEFAULT = "default"


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
