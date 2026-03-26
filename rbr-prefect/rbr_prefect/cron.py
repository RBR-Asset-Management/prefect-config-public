"""
rbr_prefect.cron - Módulo baseado no pacote cron-build.

Utilize rbr_prefect.cron para montar expressões Cron e
configurar a recorrência da execução de um deploy.

Exemplos:
```python
from rbr_prefect.cron import CronBuilder

# todo dia da semana às 4:00
cron = CronBuilder().on_weekdays().at_hour(4).at_minute(0)

# todo dia 1 do mês as 23:00
cron = CronBuilder().on_day_of_month(1).at_hour(23).at_minute(0)

# todo dia da semana a cada 30 minutos
cron = CronBuilder().on_weekdays().every_minutes(30)

# passa e expressão cron para o deploy
meu_deploy.schedule(cron)

# executa o deploy no prefect
meu_deploy.deploy()

```
rbr_prefect.cron é baseado em no pacote cron-builder.
Acesse a documentação completa e mais exemplos em: [cron-builder](https://pypi.org/project/cron-builder/)
"""

from cron_builder import CronBuilder, Weekday, Month


__all__ = ["CronBuilder", "Weekday", "Month"]
