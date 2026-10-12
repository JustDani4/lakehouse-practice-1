# Основа работы и изменения

Проект адаптирован из предоставленного архива `Lakehouse.zip`. Сохранены архитектура
MinIO → Lakekeeper → Trino, три warehouse Bronze/Silver/Gold, восемь комбинаций
Parquet/ORC × NONE/SNAPPY/GZIP/ZSTD, измерение размеров через Iceberg `$files` и
`$manifests`, отдельные холодные и повторные чтения. Метод измерения клиентским
`perf_counter()` с полным `fetchall()` основан на исходном `bench_codecs.py`.

Под вариант 3 заменены запрос Q1 и прежние бизнес-витрины: теперь выполняется Q18
«Large Volume Customer». Windows-скрипты заменены переносимым Docker Compose и
Python. Подключён Spark, добавлены сверка результатов с TPC-H, журнал query ID,
проверки качества данных, изменение схемы и проверяемый откат снимка Iceberg.

Форма `отчет.md` преподавателя сохранена как структура итогового отчёта: разделы
1–7 и таблицы решений по слоям. Назначение варианта подтверждено строкой Воднев
Даниил → 3 в файле `вариант.xlsx`; описание Q18 взято из `варианты.md`.

Числа из исходных `results/run1.csv`, `run2.csv`, `run3.csv` и снимки чужого стенда
в итоговые результаты не переносились. Все публикуемые результаты находятся в
`results/` и получены запуском этого проекта. Момент измерения и SQL зафиксированы
в `queries.jsonl`. Это учебное сравнение на ноутбуке, а не сертифицированный
результат TPC-H: не измеряются throughput, полный набор запросов и требования TPC.

Документация, использованная при настройке:

- [Исходный учебный гайд](https://github.com/m1705161/laba2)
- [Официальный пример Lakekeeper 0.14.0](https://github.com/lakekeeper/lakekeeper/tree/v0.14.0/examples/minimal)
- [Lakekeeper: подключение Trino и Spark](https://docs.lakekeeper.io/docs/latest/engines/)
- [Trino: Iceberg connector](https://trino.io/docs/current/connector/iceberg.html)
- [Apache Iceberg: Spark configuration](https://iceberg.apache.org/docs/latest/spark-configuration/)
- [TPC-H](https://www.tpc.org/tpch/)
