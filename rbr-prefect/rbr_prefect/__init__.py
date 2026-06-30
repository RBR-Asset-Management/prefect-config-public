"""
rbr-prefect - Utilitario de deploy de flows Prefect para a RBR Asset Management.

Uso basico:
    from rbr_prefect import DefaultDeploy, ScrapeDeploy, ProcessDeploy

Para referenciar constantes de infraestrutura:
    from rbr_prefect.constants import RBRDocker, RBRWorkPools
"""

from rbr_prefect.deploy import (
    DefaultDeploy,
    ProcessDeploy,
    ScrapeDeploy,
    SQLDeploy,
)

__version__ = "1.0.0"

__all__ = [
    "DefaultDeploy",
    "ProcessDeploy",
    "ScrapeDeploy",
    "SQLDeploy",
    "__version__",
]
