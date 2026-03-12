from typing import Literal

from pydantic import BaseModel, Field, SecretStr
from prefect.blocks.core import Block


class MongoDBConnection(BaseModel):
    """Endereço e porta do servidor MongoDB."""

    host: str = Field(
        title="Host",
        description=(
            "Endereço do servidor MongoDB. Aceita hostname simples (`mongo.exemplo.com`) "
            "ou URI completa no formato MongoDB (`mongodb://usuario:senha@host:porta/db?opcoes`). "
            "Quando uma URI é fornecida, os parâmetros de usuário, senha e banco presentes "
            "nela têm precedência sobre os campos individuais deste bloco."
        ),
        examples=[
            "mongo.exemplo.com",
            "mongodb://usuario:senha@mongo.exemplo.com:27017/meu_db",
        ],
    )
    port: int = Field(
        default=27017,
        title="Porta",
        description="Porta TCP do servidor MongoDB. Padrão: `27017`.",
        examples=[27017],
        ge=1,
        le=65535,
    )


class MongoDBAuth(BaseModel):
    """Credenciais de acesso ao MongoDB."""

    username: str | None = Field(
        default=None,
        title="Usuário",
        description=(
            "Nome de usuário para autenticação. "
            "Deixe em branco para conexões sem autenticação."
        ),
        examples=["mongo_user"],
    )
    password: SecretStr | None = Field(
        default=None,
        title="Senha",
        description=(
            "Senha do usuário. "
            "Armazenada de forma segura como `SecretStr` — "
            "use `.get_secret_value()` ao passar para o driver."
        ),
    )
    authentication_source: str = Field(
        default="admin",
        title="Banco de Autenticação (authSource)",
        description=(
            "Banco de dados usado para validar as credenciais. "
            "Normalmente `admin` para instâncias standalone. "
            "Em Atlas ou implantações onde o usuário é criado no banco de dados da aplicação, "
            "informe o nome desse banco."
        ),
        examples=["admin", "meu_banco"],
    )
    authentication_mechanism: Literal[
        "SCRAM-SHA-1",
        "SCRAM-SHA-256",
        "MONGODB-CR",
        "MONGODB-X509",
        "GSSAPI",
        "PLAIN",
    ] = Field(
        default="SCRAM-SHA-1",
        title="Mecanismo de Autenticação",
        description=(
            "Protocolo de autenticação a ser utilizado:\n"
            "- `SCRAM-SHA-1` — padrão para MongoDB 3.0+\n"
            "- `SCRAM-SHA-256` — padrão para MongoDB 4.0+; mais seguro\n"
            "- `MONGODB-CR` — legado, evitar em instalações novas\n"
            "- `MONGODB-X509` — autenticação por certificado TLS/SSL\n"
            "- `GSSAPI` — Kerberos (ambientes corporativos)\n"
            "- `PLAIN` — LDAP via SASL (requer TLS habilitado)"
        ),
    )


class MongoDBAdvanced(BaseModel):
    """Parâmetros avançados de conexão."""

    replicaset: str | None = Field(
        default=None,
        title="Replica Set",
        description=(
            "Nome do Replica Set, quando a instância faz parte de um conjunto replicado. "
            "Deixe em branco para conexões standalone. "
            "Pode ser definido alternativamente via URI: "
            "`mongodb://host/db?replicaSet=rs-name`."
        ),
        examples=["rs0", "globaldb"],
    )
    tls: bool = Field(
        default=False,
        title="TLS / SSL",
        description=(
            "Habilita conexão criptografada com TLS/SSL. "
            "Obrigatório para MongoDB Atlas e recomendado em produção. "
            "Parâmetros adicionais de certificado (tlsCAFile, tlsCertificateKeyFile, etc.) "
            "podem ser passados via URI no campo `host`."
        ),
    )
    uuid_representation: Literal[
        "standard",
        "pythonLegacy",
        "javaLegacy",
        "csharpLegacy",
        "unspecified",
    ] = Field(
        default="standard",
        title="Representação de UUID",
        description=(
            "Define como valores UUID são codificados/decodificados no BSON:\n"
            "- `standard` — RFC 4122, interoperável entre linguagens (**recomendado**)\n"
            "- `pythonLegacy` — formato legado do driver Python\n"
            "- `javaLegacy` / `csharpLegacy` — compatibilidade com drivers Java e C#\n"
            "- `unspecified` — sem conversão automática"
        ),
    )


# ---------------------------------------------------------------------------
# Bloco principal
# ---------------------------------------------------------------------------


class MongoDBCredentials(Block):
    """
    Credenciais e parâmetros de conexão para MongoDB via MongoEngine.

    Armazena todas as configurações necessárias para estabelecer conexões com
    ``mongoengine.connect()``. Use o método ``get_connect_kwargs()`` para obter
    o dicionário de parâmetros pronto para passar ao driver.

    **Registro do bloco:**

    .. code-block:: bash

        prefect block register --file ./blocks/mongodb_credentials_block.py

    **Uso em flows:**

    .. code-block:: python

        from blocks.mongodb_credentials_block import MongoDBCredentials

        creds = await MongoDBCredentials.load("producao")
    """

    _block_type_name = "MongoDB Credentials"
    _block_type_slug = "mongodb-credentials"
    _description = (
        "Credenciais e parâmetros de conexão para MongoDB via MongoEngine. "
        "Armazena host, porta, usuário, senha, banco de autenticação, mecanismo de "
        "autenticação e configurações avançadas (TLS, Replica Set, UUID). "
        "Use `get_connect_kwargs()` para obter o dict pronto para `mongoengine.connect()`."
    )
    _logo_url = "https://cdn.worldvectorlogo.com/logos/mongodb-icon-2.svg"  # type: ignore

    # --- Seção 1: Conexão ---
    connection: MongoDBConnection = Field(
        title="Conexão",
        description="Endereço e porta do servidor MongoDB.",
    )

    # --- Seção 2: Autenticação ---
    auth: MongoDBAuth = Field(
        title="Autenticação",
        description="Credenciais e mecanismo de autenticação.",
    )

    # --- Seção 3: Avançado ---
    advanced: MongoDBAdvanced = Field(
        default_factory=MongoDBAdvanced,
        title="Avançado",
        description="Replica Set, TLS e representação de UUID.",
    )
