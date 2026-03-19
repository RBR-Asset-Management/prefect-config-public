"""
Teste E2E manual — requer infraestrutura real da RBR.
NÃO faz parte do pytest. Ver tests/e2e/README.md.

Executar a partir da raiz do rbr-prefect/:
    cd rbr-prefect
    python tests/e2e/deploy_teste_flow.py
"""

from rbr_prefect import DefaultDeploy
from rbr_prefect.cron import CronBuilder
from tests.flows.teste_flow import teste_flow

if __name__ == "__main__":
    deploy = DefaultDeploy(
        flow_func=teste_flow,
        name="rbr-prefect-teste-flow",
        tags=["rbr-prefect", "teste"],
        requirements_source="tests/flows/requirements.txt",
    )
    deploy.parameters = deploy.override(country_name="Brazil")
    deploy.schedule(CronBuilder().on_weekdays().at_hour(4).at_minute(0))
    deploy.deploy()
