from prefect import flow
from prefect.runner.storage import GitRepository
from prefect_github import GitHubCredentials
# from requirements_detector

if __name__ == "__main__":
    github_repo = GitRepository(
        url="https://github.com/RBR-Asset-Management/prefect-v3-test.git",
        credentials=GitHubCredentials.load("rbr-org-github-finegrained-access-token"),
        branch="main",
    )

    d = flow.from_source(
        source=github_repo,
        entrypoint="country-prefect-test/flows/country_flow.py:country_flow",
    )

    d.deploy(
        name="country-prefect-test",
        work_pool_name="default",
        image="prefecthq/prefect:3-python3.12",
        build=False,
        push=False,
        job_variables={
            "env": {
                "PREFECT_API_URL": "https://prefect-eve.rbr.local/api",
                "PREFECT_API_SSL_CERT_FILE": "/host-certs/rbr-root-ca.crt",
                "PREFECT_API_AUTH_STRING": "{{ prefect.blocks.basic-auth-credentials.walle-basic-auth.token_config.auth_string }}",
                "PREFECT_CLIENT_CUSTOM_HEADERS": "{{ prefect.blocks.basic-auth-credentials.walle-basic-auth.token_config.header }}",
                "EXTRA_PIP_PACKAGES": "bs4 bizdays==1.0.19",
            },
            "volumes": ["/home/rbr-admin/certs:/host-certs:ro"],
            "auto_remove": True,
            "image_pull_policy": "IfNotPresent",
        },
        parameters={"country_name": "Brazil"},
    )
