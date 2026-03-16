"""
Deploy do flow country usando o pacote rbr-prefect.

Este arquivo reproduz o mesmo deploy de deploy_flow_country.py,
mas usando DefaultDeploy do pacote rbr-prefect em vez da API
do Prefect diretamente.
"""

from rbr_prefect import DefaultDeploy
from rbr_prefect.cron import CronBuilder

from prefect import flow, task, get_run_logger
import httpx
import json


@task
def fetch_country_data(country_name: str):
    url = f"https://restcountries.com/v3.1/name/{country_name}"

    response = httpx.get(url)
    response.raise_for_status()

    return response.json()


@flow(name="country-flow")
def country_flow(country_name: str = "Brazil"):
    logger = get_run_logger()

    data = fetch_country_data(country_name)

    logger.info(json.dumps(data, indent=2, ensure_ascii=False))

    return data


if __name__ == "__main__":
    rbr_deploy = DefaultDeploy(
        flow_func=country_flow,
        entrypoint="country-prefect-test/flows/country_flow.py:country_flow",
        github_url="https://github.com/RBR-Asset-Management/prefect-v3-test.git",
        branch="main",
        requirements_source=r"C:\Users\thomaz.pougy\Documents\RBR\Projetos\prefect-config-public\rbr-prefect\requirements.txt",
        name="country-prefect-test",
        tags=["teste"],
    )
    rbr_deploy.parameters = rbr_deploy.override(country_name="Brazil")

    cron = CronBuilder().on_weekdays().at_hour(4)

    rbr_deploy = rbr_deploy.schedule(cron)

    rbr_deploy.deploy()
