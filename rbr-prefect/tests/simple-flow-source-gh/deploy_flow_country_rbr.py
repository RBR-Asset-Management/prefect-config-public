"""
Deploy do flow country usando o pacote rbr-prefect.

Este arquivo reproduz o mesmo deploy de deploy_flow_country.py,
mas usando DefaultDeploy do pacote rbr-prefect em vez da API
do Prefect diretamente.
"""

from rbr_prefect import DefaultDeploy

from flows.flow_country import country_flow

if __name__ == "__main__":
    deploy = DefaultDeploy(
        flow_func=country_flow,
        entrypoint="country-prefect-test/flows/country_flow.py:country_flow",
        github_url="https://github.com/RBR-Asset-Management/prefect-v3-test.git",
        branch="main",
        name="country-prefect-test",
        tags=["teste"],
    )
    deploy.parameters = deploy.override(country_name="Brazil")
    deploy.deploy()
