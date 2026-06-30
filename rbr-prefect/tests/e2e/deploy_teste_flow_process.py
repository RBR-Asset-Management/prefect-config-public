"""
Teste E2E manual — deploy em work pool do tipo process.

Requer infraestrutura real da RBR: um worker process registrado no work pool
RBRWorkPools.PROCESS ("windows"), com as dependencias do flow (httpx, bizdays,
prefect) ja instaladas no ambiente Python do worker.

NAO faz parte do pytest. Ver tests/e2e/README.md.

Executar a partir da raiz do rbr-prefect/:
    cd rbr-prefect
    python tests/e2e/deploy_teste_flow_process.py
"""

from rbr_prefect import ProcessDeploy
from rbr_prefect.cron import CronBuilder
from tests.flows.teste_flow import teste_flow

if __name__ == "__main__":
    # ProcessDeploy nao gerencia dependencias: elas devem estar pre-instaladas
    # no ambiente do worker. Por isso nao ha 'image' nem 'dependency_mode'.
    deploy = ProcessDeploy(
        flow_func=teste_flow,
        name="rbr-prefect-teste-flow-process",
        tags=["rbr-prefect", "teste", "process"],
    )
    deploy.parameters = deploy.override(country_name="Brazil")
    deploy.schedule(CronBuilder().on_weekdays().at_hour(4)).deploy()
