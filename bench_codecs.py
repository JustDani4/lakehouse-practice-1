"""TPC-H Q18 benchmark, adapted from the supplied Lakehouse/bench_codecs.py.

One timed CTAS per combination, three pairs of process-cold/warm reads.
Cold = restart Trino and MinIO, NOT clearing the VM/host page cache.
Every result is checked against the reference TPC-H connector query.
"""
import argparse
import csv
from pathlib import Path
import statistics
from lakehouse import ROOT, RESULTS, compose, connect, query, q18, result_hash, save_json, wait_trino


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--only", help="e.g. parquet_zstd, for resuming")
    parser.add_argument("--refresh-reads", action="store_true", help="Remeasure reads without repeating CTAS")
    args = parser.parse_args()
    reference_path = RESULTS / "reference_q18.json"
    if reference_path.exists():
        import json
        reference = json.loads(reference_path.read_text())
    else:
        rows, sec, columns, qid = query(q18("tpch.sf1.lineitem", "tpch.sf1.orders", "tpch.sf1.customer"), "reference-q18")
        reference = {"rows": rows, "columns": columns, "sha256": result_hash(rows), "seconds": sec, "query_id": qid}
        save_json("reference_q18.json", reference)
    measurements = []
    for fmt in ("PARQUET", "ORC"):
        for codec in ("NONE", "SNAPPY", "GZIP", "ZSTD"):
            slug = f"{fmt.lower()}_{codec.lower()}"
            if args.only and slug != args.only:
                continue
            detail_path = RESULTS / f"trino_{slug}.json"
            if detail_path.exists() and not args.refresh_reads:
                import json
                measurements.append(json.loads(detail_path.read_text()))
                continue
            print(f"=== {slug} ===", flush=True)
            table = f"bronze.bench.lineitem_{slug}"
            import json
            progress_path = RESULTS / f"progress_{slug}.json"
            write_path = RESULTS / f"write_{slug}.json"
            if args.refresh_reads and detail_path.exists():
                entry = json.loads(detail_path.read_text())
                save_json(f"calibration_{slug}.json", entry)
                entry["reads"] = []
            elif progress_path.exists() or write_path.exists():
                entry = json.loads((progress_path if progress_path.exists() else write_path).read_text())
            else:
                conn = connect(codec)
                actual_codec = query("SHOW SESSION LIKE 'bronze.compression_codec'", "codec", conn)[0][0][1]
                assert actual_codec == codec, (actual_codec, codec)
                # Never count a reused table as a new write.
                _, write_sec, _, write_id = query(f"CREATE TABLE {table} WITH (format='{fmt}') AS SELECT * FROM tpch.sf1.lineitem", "write-" + slug, conn)
                files = query(f'SELECT sum(file_size_in_bytes),count(*),sum(record_count) FROM bronze.bench."lineitem_{slug}$files"', "files-" + slug)[0][0]
                metadata = query(f'SELECT coalesce(sum(length),0) FROM bronze.bench."lineitem_{slug}$manifests"', "manifests-" + slug)[0][0][0]
                assert files[2] == 6001215, files
                entry = {"format": fmt, "codec": codec, "sf": 1, "data_bytes": files[0], "files": files[1],
                         "source_rows": files[2], "meta_bytes": metadata, "gb": files[0]/2**30,
                         "write_sec": write_sec, "write_query_id": write_id, "reads": []}
                save_json(f"write_{slug}.json", entry)
            for n in range(len(entry["reads"])+1, args.repeats+1):
                compose("restart", "trino", "minio")
                wait_trino()
                cold_rows, cold, _, cold_id = query(q18(table), f"{slug}-cold-{n}")
                warm_rows, warm, _, warm_id = query(q18(table), f"{slug}-warm-{n}")
                assert result_hash(cold_rows) == reference["sha256"], (slug, "cold result differs")
                assert result_hash(warm_rows) == reference["sha256"], (slug, "warm result differs")
                entry["reads"].append({"repeat": n, "cold_sec": cold, "warm_sec": warm,
                    "cold_query_id": cold_id, "warm_query_id": warm_id,
                    "rows": len(warm_rows), "sha256": result_hash(warm_rows)})
                save_json(f"progress_{slug}.json", entry)
            entry["cold_sec"] = statistics.median(r["cold_sec"] for r in entry["reads"])
            entry["warm_sec"] = statistics.median(r["warm_sec"] for r in entry["reads"])
            save_json(f"trino_{slug}.json", entry)
            measurements.append(entry)
            summarize()
    summarize()


def summarize():
    import json
    fields = ["format", "codec", "gb", "files", "data_bytes", "meta_bytes", "write_sec", "cold_sec", "warm_sec", "sf", "source_rows"]
    values = [json.loads(p.read_text()) for p in sorted(RESULTS.glob("trino_*.json"))]
    with (RESULTS / "trino_summary.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(values)


if __name__ == "__main__":
    main()
