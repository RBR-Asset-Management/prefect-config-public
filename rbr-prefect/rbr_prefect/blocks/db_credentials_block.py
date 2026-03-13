# 1. Biblioteca padrão
from enum import Enum
from typing import Any

# 2. Dependências externas
from pydantic import BaseModel, Field, SecretStr
from sqlalchemy.engine.url import URL, make_url
from prefect.blocks.core import Block


# ---------------------------------------------------------------------------
# Enums de drivers — espelho fiel do prefect-sqlalchemy original
# ---------------------------------------------------------------------------


class AsyncDriver(str, Enum):
    """
    Dialetos com suporte a conexões **assíncronas**.

    Combine com ``create_async_engine()`` do SQLAlchemy.
    """

    POSTGRESQL_ASYNCPG = "postgresql+asyncpg"

    SQLITE_AIOSQLITE = "sqlite+aiosqlite"

    MYSQL_ASYNCMY = "mysql+asyncmy"
    MYSQL_AIOMYSQL = "mysql+aiomysql"


class SyncDriver(str, Enum):
    """
    Dialetos com suporte a conexões **síncronas**.

    Combine com ``create_engine()`` do SQLAlchemy.
    """

    POSTGRESQL_PSYCOPG2 = "postgresql+psycopg2"
    POSTGRESQL_PG8000 = "postgresql+pg8000"
    POSTGRESQL_PSYCOPG2CFFI = "postgresql+psycopg2cffi"
    POSTGRESQL_PYPOSTGRESQL = "postgresql+pypostgresql"
    POSTGRESQL_PYGRESQL = "postgresql+pygresql"

    MYSQL_MYSQLDB = "mysql+mysqldb"
    MYSQL_PYMYSQL = "mysql+pymysql"
    MYSQL_MYSQLCONNECTOR = "mysql+mysqlconnector"
    MYSQL_CYMYSQL = "mysql+cymysql"
    MYSQL_OURSQL = "mysql+oursql"
    MYSQL_PYODBC = "mysql+pyodbc"

    SQLITE_PYSQLITE = "sqlite+pysqlite"
    SQLITE_PYSQLCIPHER = "sqlite+pysqlcipher"

    ORACLE_CX_ORACLE = "oracle+cx_oracle"

    MSSQL_PYODBC = "mssql+pyodbc"
    MSSQL_MXODBC = "mssql+mxodbc"
    MSSQL_PYMSSQL = "mssql+pymssql"


# ---------------------------------------------------------------------------
# Modelos aninhados — geram seções visuais na Prefect UI
# ---------------------------------------------------------------------------


class SQLAlchemyConnection(BaseModel):
    """Endereço, porta e dialeto do banco de dados."""

    driver: AsyncDriver | SyncDriver | str | None = Field(
        default=None,
        title="Driver",
        description=(
            "Dialeto e driver SQLAlchemy no formato `dialeto+driver`. "
            "Selecione um dos drivers conhecidos nos enums `AsyncDriver` / `SyncDriver`, "
            "ou informe uma string livre para dialetos externos "
            "(ex: `snowflake`, `bigquery+pybigquery`). "
            "Obrigatório quando o campo `url` não for preenchido."
        ),
        examples=["postgresql+asyncpg", "postgresql+psycopg2", "snowflake"],
    )
    host: str | None = Field(
        default=None,
        title="Host",
        description=(
            "Endereço do servidor de banco de dados. "
            "Ignorado quando o campo `url` for preenchido."
        ),
        examples=["localhost", "db.empresa.com", "10.0.0.50"],
    )
    port: int | None = Field(
        default=None,
        title="Porta",
        description=(
            "Porta TCP do servidor. "
            "Quando omitida, o SQLAlchemy usa o padrão do dialeto "
            "(5432 para PostgreSQL, 3306 para MySQL, etc.). "
            "Ignorado quando o campo `url` for preenchido."
        ),
        examples=[5432, 3306, 1433, 1521],
        ge=1,
        le=65535,
    )


class SQLAlchemyDatabase(BaseModel):
    """Nome do banco de dados alvo."""

    database: str | None = Field(
        default=None,
        title="Banco de Dados",
        description=(
            "Nome do banco de dados (schema) a ser utilizado. "
            "Obrigatório quando o campo `url` não for preenchido. "
            "Em dialetos como Snowflake ou BigQuery, corresponde ao nome do database/projeto."
        ),
        examples=["producao", "dwh", "analytics"],
    )


class SQLAlchemyAuth(BaseModel):
    """Credenciais de acesso ao banco de dados."""

    username: str | None = Field(
        default=None,
        title="Usuário",
        description=(
            "Nome de usuário para autenticação. "
            "Deixe em branco para bancos sem autenticação (ex: SQLite local)."
        ),
        examples=["app_user", "readonly"],
    )
    password: SecretStr | None = Field(
        default=None,
        title="Senha",
        description=(
            "Senha do usuário. "
            "Armazenada como `SecretStr` — use `.get_secret_value()` ao acessar o valor. "
            "Deixe em branco para bancos sem autenticação."
        ),
    )


class SQLAlchemyAdvanced(BaseModel):
    """Parâmetros avançados de conexão."""

    url: str | None = Field(
        default=None,
        title="URL de Conexão (override)",
        description=(
            "URL completa de conexão no formato SQLAlchemy. "
            "**Quando preenchida, todos os outros campos são ignorados na construção da URL.** "
            "Útil para dialetos externos com parâmetros não suportados diretamente "
            "(ex: Snowflake com `warehouse`, `role`; BigQuery com `project`). "
            "Formato: `dialeto+driver://usuario:senha@host:porta/banco?param=valor`. "
            "A senha na URL é armazenada como texto — prefira usar os campos individuais "
            "quando a senha precisar ser protegida como `SecretStr`."
        ),
        examples=[
            "postgresql+psycopg2://user:pwd@localhost/mydb",
            "snowflake://user:pwd@account/db?warehouse=wh&role=analyst",
        ],
    )
    query: dict[str, str] | None = Field(
        default=None,
        title="Parâmetros de Query",
        description=(
            "Dicionário de parâmetros adicionais a serem acrescentados à URL de conexão "
            'como query string (ex: `{"sslmode": "require", "connect_timeout": "10"}`). '
            "São repassados ao dialeto e/ou ao DBAPI no momento da conexão. "
            "Para parâmetros não-string ao DBAPI, use `connect_args`."
        ),
        examples=[
            {"sslmode": "require"},
            {"charset": "utf8mb4", "connect_timeout": "10"},
        ],
    )
    connect_args: dict[str, Any] | None = Field(
        default=None,
        title="Argumentos de Conexão (connect_args)",
        description=(
            "Dicionário de opções passadas diretamente ao método `connect()` do DBAPI "
            "como kwargs adicionais. "
            "Útil para parâmetros que não podem ser representados na query string da URL, "
            "como objetos SSL (`ssl_context`), timeouts complexos ou certificados. "
            "Corresponde ao parâmetro `connect_args` de `create_engine()` / `create_async_engine()`."
        ),
        examples=[{"ssl": True}, {"options": "-c timezone=utc"}],
    )


# ---------------------------------------------------------------------------
# Bloco principal
# ---------------------------------------------------------------------------


class DBCredentials(Block):
    """
    Credenciais e parâmetros de conexão para bancos de dados relacionais via SQLAlchemy.

    Substitui o bloco ``DatabaseCredentials`` do pacote ``prefect-sqlalchemy``,
    tornado obsoleto. Armazena as mesmas informações de conexão, mas **não** cria
    engines nem gerencia conexões — isso fica a cargo do código externo.

    Use ``get_url()`` para obter a ``sqlalchemy.engine.URL`` pronta para passar a
    ``create_engine()`` ou ``create_async_engine()``.

    **Registro do bloco:**

    .. code-block:: bash

        prefect block register --file ./blocks/database_credentials_block.py

    **Uso em flows:**

    .. code-block:: python

        from sqlalchemy.ext.asyncio import create_async_engine
        from blocks.database_credentials_block import DatabaseCredentials

        creds = await DatabaseCredentials.load("postgres-producao")
        engine = create_async_engine(creds.get_url())

    **Migração a partir do prefect-sqlalchemy:**

    Os campos são equivalentes. Basta criar um novo bloco com o mesmo nome e
    substituir o import:

    .. code-block:: python

        # Antes
        from prefect_sqlalchemy import DatabaseCredentials

        # Depois
        from blocks.database_credentials_block import DatabaseCredentials
    """

    _block_type_name = "DB Credentials"
    _block_type_slug = "db-credentials"
    _description = (
        "Credenciais e parâmetros de conexão para bancos de dados relacionais via SQLAlchemy. "
        "Substitui o bloco DatabaseCredentials do prefect-sqlalchemy (obsoleto). "
        "Armazena driver, host, porta, banco, usuário, senha e parâmetros avançados. "
        "Use `get_url()` para obter a URL pronta para `create_engine()` ou `create_async_engine()`."
    )
    _logo_url = "https://icon.icepanel.io/Technology/svg/SQLAlchemy.svg"  # type: ignore

    # --- Seção 1: Conexão ---
    connection: SQLAlchemyConnection = Field(
        title="Conexão",
        description="Driver, host e porta do servidor de banco de dados.",
    )

    # --- Seção 2: Banco de Dados ---
    database: SQLAlchemyDatabase = Field(
        title="Banco de Dados",
        description="Nome do banco de dados (schema) alvo.",
    )

    # --- Seção 3: Autenticação ---
    auth: SQLAlchemyAuth = Field(
        default_factory=SQLAlchemyAuth,
        title="Autenticação",
        description="Usuário e senha para autenticação no banco.",
    )

    # --- Seção 4: Avançado ---
    advanced: SQLAlchemyAdvanced = Field(
        default_factory=SQLAlchemyAdvanced,
        title="Avançado",
        description="URL override, parâmetros de query e connect_args.",
    )

    # ---------------------------------------------------------------------------
    # API pública
    # ---------------------------------------------------------------------------

    def get_url(self) -> URL:
        """
        Retorna a ``sqlalchemy.engine.URL`` construída a partir dos campos do bloco.

        Quando ``advanced.url`` está preenchido, ele é usado diretamente
        (equivalente ao comportamento original do ``prefect-sqlalchemy``).
        Caso contrário, a URL é composta a partir dos campos individuais;
        nesse caso ``connection.driver`` e ``database.database`` são obrigatórios.

        :raises ValueError: se ``advanced.url`` não for fornecida e ``driver``
            ou ``database`` estiverem ausentes; ou se ``advanced.url`` for fornecida
            junto com campos individuais (combinação ambígua).
        :returns: ``sqlalchemy.engine.URL`` pronta para ``create_engine()``
            ou ``create_async_engine()``.
        """
        has_url = bool(self.advanced.url)
        individual_values = {
            "driver": self.connection.driver,
            "host": self.connection.host,
            "port": self.connection.port,
            "database": self.database.database,
            "username": self.auth.username,
            "password": self.auth.password,
            "query": self.advanced.query,
        }
        has_individual = any(v is not None for v in individual_values.values())

        if has_url and has_individual:
            raise ValueError(
                "O campo `advanced.url` não deve ser preenchido junto com campos "
                "individuais de conexão (driver, host, porta, banco, usuário, senha). "
                "Use uma das duas formas, nunca ambas simultaneamente."
            )

        if has_url:
            return make_url(self.advanced.url)

        # Validação dos campos obrigatórios quando URL não é fornecida
        missing = [
            name
            for name, val in {
                "driver": self.connection.driver,
                "database": self.database.database,
            }.items()
            if not val
        ]
        if missing:
            raise ValueError(
                f"Quando `advanced.url` não é fornecida, os seguintes campos são obrigatórios: "
                f"{missing}. Preencha-os ou forneça uma URL completa em `advanced.url`."
            )

        driver_value = (
            self.connection.driver.value
            if isinstance(self.connection.driver, (AsyncDriver, SyncDriver))
            else self.connection.driver
        )

        return URL.create(
            drivername=driver_value,
            username=self.auth.username,
            password=self.auth.password.get_secret_value()
            if self.auth.password
            else None,
            host=self.connection.host,
            port=self.connection.port,
            database=self.database.database,
            query=self.advanced.query or {},
        )

    def get_url_string(self, hide_password: bool = True) -> str:
        """
        Retorna a URL de conexão como string.

        :param hide_password: Se ``True`` (padrão), oculta a senha na string retornada.
            Passe ``False`` apenas quando precisar da string completa para passar a um
            driver externo.
        :returns: String da URL de conexão.
        """
        return self.get_url().render_as_string(hide_password=hide_password)

    def is_async(self) -> bool:
        """
        Indica se o driver configurado suporta conexões assíncronas.

        Útil para decidir entre ``create_engine()`` e ``create_async_engine()``
        sem precisar inspecionar a string do driver manualmente.

        :returns: ``True`` se o driver for uma instância de ``AsyncDriver``
            ou se o valor string estiver na lista de drivers async conhecidos.
        """
        driver = self.connection.driver
        if isinstance(driver, AsyncDriver):
            return True
        if isinstance(driver, SyncDriver):
            return False
        # Driver informado como string livre — verifica contra os valores conhecidos
        return driver in AsyncDriver._value2member_map_

    class Config:
        """Permite serialização do tipo ``URL`` do SQLAlchemy."""

        arbitrary_types_allowed = True
