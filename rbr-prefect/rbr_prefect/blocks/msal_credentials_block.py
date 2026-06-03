from prefect.blocks.core import Block
from pydantic import Field, SecretStr


# prefect block register --file ./caminho-arquivo-onde-define-o-bloco.py
class MSALCredentials(Block):
    _block_type_name = "MSAL Credentials"
    _block_type_slug = "msal-credentials"
    _description = (
        "Credenciais MSAL (Microsoft Authentication Library) para autenticação"
        " app-only contra Microsoft Graph / Azure AD via client-credentials flow."
        " Equivalente programático ao trio `client_id` / `authority` / `secret`"
        " usado em msal.ConfidentialClientApplication(...)."
    )

    client_id: str = Field(
        title="Client ID",
        description="Azure AD app registration client ID (GUID). Acesse na key `client_id`.",
        examples=["00000000-0000-0000-0000-000000000000"],
    )
    authority: str = Field(
        title="Authority URL",
        description=(
            "URL completa do tenant: `https://login.microsoftonline.com/<tenant-id>`."
            " Acesse na key `authority`."
        ),
        examples=[
            "https://login.microsoftonline.com/00000000-0000-0000-0000-000000000000"
        ],
    )
    secret: SecretStr = Field(
        title="Client Secret",
        description="Client secret gerado no Azure AD. Acesse via `secret.get_secret_value()`.",
    )
