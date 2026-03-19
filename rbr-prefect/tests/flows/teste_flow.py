import json
from datetime import datetime

import httpx
from bizdays import Calendar
from prefect import flow, get_run_logger, task


@task
def fetch_country_data(country_name: str) -> dict:
    response = httpx.get(
        f"https://restcountries.com/v3.1/name/{country_name}",
        timeout=10,
    )
    response.raise_for_status()
    return response.json()[0]


@flow(name="teste-flow")
def teste_flow(country_name: str = "Brazil") -> dict:
    logger = get_run_logger()
    cal = Calendar.load("ANBIMA")
    d = datetime.now()
    msg = "é" if cal.isbizday(d) else "não é"
    logger.info(f"Hoje {d:%d-%m-%Y} {msg} dia útil")
    data = fetch_country_data(country_name)
    logger.info(json.dumps(data, indent=2, ensure_ascii=False))
    return data
