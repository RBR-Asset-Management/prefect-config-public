"""
Constantes de texto e factories de mensagens para o terminal.

Este arquivo é a fonte única da verdade para todos os textos exibidos ao dev.
Nenhum texto literal deve aparecer em ui.py ou em outros arquivos de lógica.
"""


class DeployMessages:
    """Mensagens do fluxo principal de auditoria e execução do deploy."""

    # Cabeçalhos do painel de auditoria
    RESOLVED_HEADER = "Valores resolvidos automaticamente"
    OVERRIDES_HEADER = "Overrides aplicados"
    ENV_HEADER = "Variáveis de ambiente (env resolvido)"

    # Labels das linhas do painel de auditoria
    LABEL_GITHUB_URL = "github_url"
    LABEL_BRANCH = "branch"
    LABEL_ENTRYPOINT = "entrypoint"
    LABEL_PARAMETERS = "parameters"
    LABEL_IMAGE = "image"
    LABEL_WORK_POOL = "work_pool_name"
    LABEL_TAGS = "tags"
    LABEL_SCHEDULE = "schedule"
    LABEL_NAME = "name"

    # Separador de passagem de responsabilidade
    HANDOFF_MESSAGE = "Configuracao validada. Passando para o Prefect..."

    # Templates e factories
    _DEPLOY_STARTING = "Iniciando deploy: '{name}'"

    @staticmethod
    def deploy_starting(name: str) -> str:
        return DeployMessages._DEPLOY_STARTING.format(name=name)


class WorkPoolMessages:
    """Mensagens relacionadas ao prompt de confirmacao de override do work pool."""

    OVERRIDE_WARNING = (
        "Sobrescrever o work pool e incomum e raramente necessario. "
        "O work pool padrao RBR e suficiente para a grande maioria dos flows."
    )
    OVERRIDE_ABORTED = "Deploy abortado pelo usuario."

    _OVERRIDE_CONFIRM = "Confirma a sobrescrita do work pool para '{pool}'?"

    @staticmethod
    def override_confirm(pool: str) -> str:
        return WorkPoolMessages._OVERRIDE_CONFIRM.format(pool=pool)


class ConcurrencyMessages:
    """Mensagens relacionadas ao prompt de confirmacao de concurrency limit."""

    WARNING = (
        "Configurar concurrency limit diretamente no deploy e incomum. "
        "O work pool e a queue ja gerenciam concorrencia por padrao."
    )
    ABORTED = "Deploy abortado pelo usuario."
    CONFIRM = "O controle de concorrencia ja existe no work pool. Confirma mesmo assim?"


class EnvMessages:
    """Mensagens relacionadas ao override total do env."""

    OVERRIDE_WARNING = (
        "OVERRIDE TOTAL do env aplicado - "
        "toda a configuracao de ambiente base da RBR foi ignorada."
    )


class JobVariablesMessages:
    """Mensagens relacionadas ao override total de job_variables."""

    OVERRIDE_WARNING = (
        "OVERRIDE TOTAL de job_variables aplicado - "
        "toda a configuracao base de job_variables da RBR foi ignorada."
    )


class ScheduleMessages:
    """Mensagens relacionadas a configuracao avancada de schedule."""

    ADVANCED_WARNING = (
        "Interval e rrule sao configuracoes avancadas de schedule. "
        "Para a maioria dos casos, o parametro cron e suficiente."
    )
    ADVANCED_CONFIRM = "Confirma o uso de schedule avancado (interval/rrule)?"
    ABORTED = "Deploy abortado pelo usuario."


class ValidationMessages:
    """Mensagens de erro de validacao lancadas como excecoes."""

    TAGS_REQUIRED = "Pelo menos uma tag e obrigatoria."
    NAME_REQUIRED = "O parametro 'name' e obrigatorio."
    OUTSIDE_GIT_REPO = (
        "Nao foi possivel detectar um repositorio Git. "
        "Verifique se o script de deploy esta dentro de um repositorio Git "
        "ou forneca 'github_url' e 'branch' explicitamente."
    )
    NO_REMOTE_ORIGIN = (
        "Nao foi encontrado um remote 'origin' no repositorio Git. "
        "Forneca 'github_url' explicitamente."
    )
    ENTRYPOINT_OUTSIDE_REPO = (
        "O arquivo da funcao flow esta fora do repositorio Git detectado. "
        "Forneca o 'entrypoint' explicitamente."
    )
    SOURCE_FILE_NOT_FOUND = (
        "Nao foi possivel localizar o arquivo fonte (.py) da funcao flow."
    )
    ENV_MUTEX = (
        "Apenas 'env_override' ou 'extra_env' pode ser fornecido, nao ambos. "
        "Use 'extra_env' para adicionar variaveis ao env base RBR, "
        "ou 'env_override' para substituir completamente o env."
    )
    JOB_VARIABLES_MUTEX = (
        "Apenas 'job_variables_override' ou 'extra_job_variables' pode ser fornecido, nao ambos. "
        "Use 'extra_job_variables' para adicionar chaves ao dict base RBR, "
        "ou 'job_variables_override' para substituir completamente."
    )
    SCHEDULE_REQUIRED = (
        "E necessario fornecer exatamente um dos parametros: "
        "cron, interval ou rrule."
    )

    _INVALID_PARAM = (
        "Parametro de override invalido: '{param}'. "
        "A funcao '{flow}' nao possui esse parametro."
    )
    _SCHEDULE_MUTEX = (
        "Apenas um tipo de schedule pode ser configurado por vez. "
        "Forneca 'cron', 'interval' ou 'rrule' - nao multiplos simultaneamente."
    )

    @staticmethod
    def invalid_param(param: str, flow: str) -> str:
        return ValidationMessages._INVALID_PARAM.format(param=param, flow=flow)

    @staticmethod
    def schedule_mutex() -> str:
        return ValidationMessages._SCHEDULE_MUTEX
