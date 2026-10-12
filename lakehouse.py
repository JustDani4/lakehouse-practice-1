"""Common client and audit helpers; adapted from the supplied bench_codecs.py."""
import csv
import datetime as dt
import decimal
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

import trino

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
RESULTS.mkdir(exist_ok=True)


def serial(value):
    if isinstance(value, decimal.Decimal):
        return format(value, ".2f")
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()
    raise TypeError(type(value).__name__)


def save_json(name, data):
    path = RESULTS / name
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=serial) + "\n", encoding="utf-8")


def result_hash(rows):
    encoded = [json.dumps(list(row), ensure_ascii=False, default=serial) for row in rows]
    return hashlib.sha256("\n".join(sorted(encoded)).encode()).hexdigest()


def connect(codec="ZSTD"):
    return trino.dbapi.connect(host="127.0.0.1", port=int(os.getenv("TRINO_PORT", "18080")),
        user="vodnev", catalog="bronze", schema="raw",
        session_properties={"bronze.compression_codec": codec,
                            "silver.compression_codec": "ZSTD", "gold.compression_codec": "ZSTD"})


def query(sql, label="query", conn=None):
    conn = conn or connect()
    cursor = conn.cursor()
    start = time.perf_counter()
    cursor.execute(sql)
    rows = cursor.fetchall()
    elapsed = time.perf_counter() - start
    columns = [c[0] for c in cursor.description] if cursor.description else []
    event = {"at": dt.datetime.now(dt.timezone.utc).isoformat(), "label": label,
             "query_id": cursor.query_id, "seconds": elapsed, "sql": sql,
             "rows": len(rows), "result_sha256": result_hash(rows)}
    with (RESULTS / "queries.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, ensure_ascii=False) + "\n")
    print(f"{label}: {elapsed:.3f}s, rows={len(rows)}, id={cursor.query_id}", flush=True)
    return rows, elapsed, columns, cursor.query_id


def compose(*args, capture=False):
    command = ["docker", "compose"]
    probe = subprocess.run(command + ["version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if probe.returncode:
        command = ["docker-compose"]
    result = subprocess.run(command + ["-f", str(ROOT / "compose.yaml"), *args],
        cwd=ROOT, check=True, text=True, capture_output=capture)
    return result.stdout + result.stderr if capture else None


def wait_trino(timeout=180):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            # SELECT 1 can succeed before discovery has registered an active worker.
            query("SELECT count(*) FROM tpch.tiny.nation", "ready-worker")
            return
        except Exception:
            time.sleep(2)
    raise TimeoutError("Trino did not become ready")


def run_sql_file(path):
    # These files intentionally contain no semicolons inside strings/comments.
    for i, statement in enumerate(Path(path).read_text(encoding="utf-8").split(";")):
        if statement.strip():
            query(statement.strip(), f"{Path(path).name}:{i + 1}")


def q18(lineitem, orders="bronze.raw.orders", customer="bronze.raw.customer"):
    return f"""SELECT c.name, c.custkey, o.orderkey, o.orderdate,
       CAST(o.totalprice AS DECIMAL(18,2)) AS totalprice,
       CAST(SUM(l.quantity) AS DECIMAL(18,2)) AS total_quantity
FROM {customer} c JOIN {orders} o ON c.custkey=o.custkey
JOIN {lineitem} l ON o.orderkey=l.orderkey
WHERE o.orderkey IN (
  SELECT orderkey FROM {lineitem} GROUP BY orderkey HAVING SUM(quantity)>300
)
GROUP BY c.name,c.custkey,o.orderkey,o.orderdate,o.totalprice
ORDER BY o.totalprice DESC,o.orderdate
LIMIT 100"""


def export_csv(name, rows, columns):
    with (RESULTS / name).open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(columns)
        writer.writerows(rows)
