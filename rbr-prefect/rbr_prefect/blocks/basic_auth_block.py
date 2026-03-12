from pydantic import BaseModel, Field, SecretStr
from prefect.blocks.core import Block


class UserCredentials(BaseModel):
    """Credenciais do usuário"""

    username: str = Field(
        title="Usuário",
        description="Nome de usuário para autenticação.",
        examples=["admin"],
    )
    password: SecretStr = Field(
        title="Senha",
        description="Senha do usuário.",
    )


class TokenConfig(BaseModel):
    """Tokens de autenticação"""

    auth_string: SecretStr = Field(
        title="String de Autenticação",
        description=(
            "String de autenticação no formato `<usuario>:<senha>`, "
            "que será codificada em Base64 para compor o header Authorization. "
            "Exemplo: `admin:minha_senha_secreta`."
        ),
        examples=["admin:minha_senha_secreta"],
    )
    header: SecretStr = Field(
        title="Header de Autorização",
        description=(
            "Header HTTP completo no formato JSON, com a string de autenticação "
            "já codificada em Base64. "
            "Para gerar o valor Base64, execute: "
            "`base64('<usuario>:<senha>')` — no terminal: "
            "`echo -n 'admin:minha_senha_secreta' | base64`. "
            "Insira o resultado no formato: "
            '`{"Authorization": "Basic <valor_base64>"}`.'
        ),
        examples=['{"Authorization": "Basic YWRtaW46bWluaGFfc2VuaGFfc2VjcmV0YQ=="}'],
    )


class BasicAuthCredentials(Block):
    _block_type_name = "Basic Auth Credentials"
    _block_type_slug = "basic-auth-credentials"
    _description = (
        "Credenciais para autenticação HTTP Basic Auth. "
        "Armazena usuário, senha, a string `usuario:senha` e o header Authorization "
        "completo com o valor em Base64, pronto para uso em requisições HTTP."
    )

    user_credentials: UserCredentials = Field(
        title="Credenciais do Usuário",
        description="Usuário e senha utilizados na autenticação.",
    )
    token_config: TokenConfig = Field(
        title="Tokens e Headers",
        description=(
            "String de autenticação e header HTTP pré-formatado. "
            "Ambos os valores devem ser preenchidos manualmente pelo usuário."
        ),
    )
