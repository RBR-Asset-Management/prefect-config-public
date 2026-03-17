"""
rbr-prefect - Utilitario de deploy de flows Prefect para a RBR Asset Management.

Uso basico:
    from rbr_prefect import DefaultDeploy, ScrapeDeploy

Para referenciar constantes de infraestrutura:
    from rbr_prefect.constants import RBRDocker, RBRWorkPools
"""

from rbr_prefect.deploy import DefaultDeploy, ScrapeDeploy, SQLDeploy

__version__ = "0.3.10"

__all__ = [
    "DefaultDeploy",
    "ScrapeDeploy",
    "SQLDeploy",
    "__version__",
]
