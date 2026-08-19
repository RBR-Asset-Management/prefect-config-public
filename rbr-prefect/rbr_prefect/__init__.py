"""
rbr-prefect - Utilitario de deploy de flows Prefect para a RBR Asset Management.

Uso basico:
    from rbr_prefect import DefaultDeploy, ScrapeDeploy, ProcessDeploy

Para disparar o fluxo de envio de e-mail:
    from rbr_prefect import EnvioEmailTrigger

Para referenciar constantes de infraestrutura:
    from rbr_prefect.constants import RBRDocker, RBRWorkPools
"""

from rbr_prefect.deploy import (
    DefaultDeploy,
    ProcessDeploy,
    ScrapeDeploy,
    SQLDeploy,
)
from rbr_prefect.trigger import EnvioEmailTrigger

__version__ = "1.1.0"

__all__ = [
    "DefaultDeploy",
    "ProcessDeploy",
    "ScrapeDeploy",
    "SQLDeploy",
    "EnvioEmailTrigger",
    "__version__",
]
