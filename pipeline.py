"""ELT and verification for variant 3 (Q18)."""
import argparse
import json
from lakehouse import ROOT, RESULTS, query, q18, export_csv, result_hash, run_sql_file, save_json, wait_trino


def bronze():
    run_sql_file(ROOT / "sql/1_bronze.sql")


def silver_gold():
    run_sql_file(ROOT / "sql/2_silver.sql")
    run_sql_file(ROOT / "sql/3_gold.sql")
    rows, sec, columns, qid = query("SELECT * FROM gold.mart.large_volume_customer ORDER BY totalprice DESC,orderdate", "gold-result")
    reference = json.loads((RESULTS / "reference_q18.json").read_text())
    assert result_hash(rows) == reference["sha256"], "Gold differs from reference Q18"
    export_csv("gold_q18.csv", rows, columns)
    save_json("gold_q18.json", {"rows": rows, "columns": columns, "sha256": result_hash(rows), "query_id": qid, "seconds": sec})
    dq, _, dq_cols, _ = query("SELECT * FROM silver.core.dq_report", "dq")
    assert all(v == 0 for v in dq[0][1:]), dq
    save_json("data_quality.json", dict(zip(dq_cols,dq[0])))
    inventory = []
    tables = [("bronze", "raw", "customer"), ("bronze", "raw", "orders"),
              ("bronze", "bench", "lineitem_parquet_zstd"),
              ("silver", "core", "dq_report"), ("silver", "core", "dim_customer"),
              ("silver", "core", "orders"), ("silver", "core", "fact_lineitem"),
              ("silver", "core", "order_totals"), ("gold", "mart", "large_volume_customer")]
    for cat, schema, table in tables:
        full = f"{cat}.{schema}.{table}"
        count = query(f"SELECT count(*) FROM {full}", "count-" + table)[0][0][0]
        size, files = query(f'SELECT sum(file_size_in_bytes),count(*) FROM {cat}.{schema}."{table}$files"', "size-" + table)[0][0]
        columns = query(f"SHOW COLUMNS FROM {full}", "columns-" + table)[0]
        props = query(f'SELECT * FROM {cat}.{schema}."{table}$properties"', "properties-" + table)[0]
        inventory.append({"table": full, "rows": count, "data_bytes": size, "files": files, "columns": columns, "properties": props})
    save_json("inventory.json", inventory)


def demo():
    table = "silver.core.customer_demo"
    query(f"DROP TABLE IF EXISTS {table}", "demo-drop")
    query(f"CREATE TABLE {table} WITH (format='PARQUET') AS SELECT custkey,name FROM silver.core.dim_customer WHERE custkey<=3", "demo-create")
    before = query(f"SHOW COLUMNS FROM {table}", "demo-schema-before")[0]
    query(f"ALTER TABLE {table} ADD COLUMN classification VARCHAR", "demo-add-column")
    query(f"ALTER TABLE {table} RENAME COLUMN classification TO customer_tier", "demo-rename-column")
    after = query(f"SHOW COLUMNS FROM {table}", "demo-schema-after")[0]
    baseline = query(f"SELECT custkey,name FROM {table} ORDER BY custkey", "demo-baseline")[0]
    added_values = query(f"SELECT custkey,customer_tier FROM {table} ORDER BY custkey", "demo-new-column-values")[0]
    assert all(row[1] is None for row in added_values)
    snapshot = query('SELECT snapshot_id FROM silver.core."customer_demo$snapshots" ORDER BY committed_at DESC LIMIT 1', "demo-snapshot")[0][0][0]
    query(f"UPDATE {table} SET name='TEMPORARY CHANGE',customer_tier='TEST' WHERE custkey=1", "demo-update")
    changed = query(f"SELECT custkey,name FROM {table} ORDER BY custkey", "demo-changed")[0]
    historical = query(f"SELECT custkey,name FROM {table} FOR VERSION AS OF {snapshot} ORDER BY custkey", "demo-time-travel")[0]
    assert historical == baseline and changed != baseline
    query(f"ALTER TABLE {table} EXECUTE rollback_to_snapshot({snapshot})", "demo-rollback")
    restored = query(f"SELECT custkey,name FROM {table} ORDER BY custkey", "demo-restored")[0]
    assert restored == baseline
    snapshots = query('SELECT committed_at,snapshot_id,parent_id,operation FROM silver.core."customer_demo$snapshots" ORDER BY committed_at', "demo-snapshots")[0]
    save_json("iceberg_demo.json", {"schema_before": before, "schema_after": after, "snapshot_id": snapshot,
        "baseline": baseline, "changed": changed, "historical": historical, "restored": restored, "snapshots": snapshots,
        "added_column_values": added_values,
        "verified": True})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("step", choices=["bronze", "silver-gold", "demo"])
    step = parser.parse_args().step
    wait_trino()
    {"bronze": bronze, "silver-gold": silver_gold, "demo": demo}[step]()
