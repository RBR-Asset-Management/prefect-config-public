# Teste E2E — `deploy_teste_flow.py`

## Descrição

Script de teste de integração manual contra a infraestrutura real da RBR.
Valida a auto-resolução de `github_url`, `branch`, `entrypoint` e `requirements`
sem nenhum valor hardcoded.

**Não faz parte do pytest.** O diretório `tests/e2e/` é ignorado pela coleta
automática via `collect_ignore` no `pyproject.toml`.

---

## Pré-requisitos

- Acesso à rede interna da RBR (VPN ou rede local)
- Servidor Prefect acessível em `prefect-eve.rbr.local`
- Bloco `rbr-org-github-finegrained-access-token` registrado no Prefect
- Pacote `rbr-prefect` instalado no ambiente (`uv sync` na raiz do repo)

---

## Execução

A partir da raiz de `rbr-prefect/`:

```bash
cd rbr-prefect
python tests/e2e/deploy_teste_flow.py
```

---

## O que é validado automaticamente

| Valor | Resolvido via |
|---|---|
| `github_url` | `git remote get-url origin` → URL do `prefect-config-public` |
| `branch` | `git rev-parse --abbrev-ref HEAD` |
| `entrypoint` | `inspect.getfile(teste_flow)` + `relative_to(repo_root)` → `rbr-prefect/tests/flows/teste_flow.py:teste_flow` |
| `requirements` | `from_requirements_txt("tests/flows/requirements.txt")` |

O deploy deve aparecer registrado na UI do Prefect com todos os valores
de infraestrutura corretos após a execução bem-sucedida.
