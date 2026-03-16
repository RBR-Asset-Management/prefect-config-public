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
    country_flow("Brazil")
