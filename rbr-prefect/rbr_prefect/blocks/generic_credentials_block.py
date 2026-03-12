from pydantic import Field, SecretStr
from prefect.blocks.core import Block


# prefect block register --file ./caminho-arquivo-onde-define-o-bloco.py
class GenericCredentials(Block):
    _block_type_name = "Generic Credentials"
    _block_type_slug = "generic-credentials"
    _description = (
        "Credenciais para autenticação em qualquer lugar que precise apenas de login e senha"
        "Armazena usuário e senha."
    )

    login: str = Field(
        title="Usuário",
        description="Nome de usuário para autenticação. Acesse na key `login`",
        examples=["login"],
    )
    password: SecretStr = Field(
        title="Senha",
        description="Senha do usuário. Acesse na key `password`",
    )
