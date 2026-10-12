"""Run inside the Spark container: same Iceberg tables, same Q18 result."""
import argparse
import datetime as dt
import decimal
import hashlib
import json
from pathlib import Path
import statistics
import time
from pyspark.sql import SparkSession


def serial(value):
    if isinstance(value, decimal.Decimal):
        return format(value, ".2f")
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()
    raise TypeError(type(value).__name__)


def digest(rows):
    encoded = [json.dumps(list(row), ensure_ascii=False, default=serial) for row in rows]
    return hashlib.sha256("\n".join(sorted(encoded)).encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("slug")
    args = parser.parse_args()
    results = Path("/workspace/results")
    spark = SparkSession.builder.appName("Vodnev-Q18-"+args.slug).getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    table = f"bronze.bench.lineitem_{args.slug}"
    # Identical casts and semantics to lakehouse.q18; no persist()/cache().
    sql = f"""SELECT c.name,c.custkey,o.orderkey,o.orderdate,
 CAST(o.totalprice AS DECIMAL(18,2)) AS totalprice,
 CAST(SUM(l.quantity) AS DECIMAL(18,2)) AS total_quantity
FROM bronze.raw.customer c JOIN bronze.raw.orders o ON c.custkey=o.custkey
JOIN {table} l ON o.orderkey=l.orderkey
WHERE o.orderkey IN (SELECT orderkey FROM {table} GROUP BY orderkey HAVING SUM(quantity)>300)
GROUP BY c.name,c.custkey,o.orderkey,o.orderdate,o.totalprice
ORDER BY o.totalprice DESC,o.orderdate LIMIT 100"""
    reference = json.loads((results / "reference_q18.json").read_text())
    measurements = []
    for repeat in range(4):
        start = time.perf_counter()
        frame = spark.sql(sql)
        rows = frame.collect()
        elapsed = time.perf_counter()-start
        actual = digest(rows)
        assert actual == reference["sha256"], (args.slug, actual, reference["sha256"])
        item = {"repeat": repeat, "mode": "first" if repeat==0 else "warm", "seconds": elapsed,
                "rows": len(rows), "sha256": actual}
        measurements.append(item)
        print("MEASUREMENT " + json.dumps(item), flush=True)
    entry = {"slug": args.slug, "spark_version": spark.version, "master": spark.sparkContext.master,
             "driver_memory": spark.sparkContext.getConf().get("spark.driver.memory"),
             "shuffle_partitions": spark.conf.get("spark.sql.shuffle.partitions"),
             "first_sec": measurements[0]["seconds"],
             "warm_sec": statistics.median(m["seconds"] for m in measurements[1:]),
             "measurements": measurements, "sql": sql,
             "plan": frame._jdf.queryExecution().executedPlan().toString()}
    (results / f"spark_{args.slug}.json").write_text(json.dumps(entry, ensure_ascii=False, indent=2)+"\n")
    spark.stop()


if __name__ == "__main__":
    main()
