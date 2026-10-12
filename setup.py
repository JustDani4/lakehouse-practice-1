"""Start the isolated Compose project and register its three warehouses."""
import json
from pathlib import Path
import time
import requests
from lakehouse import ROOT, compose, save_json, wait_trino


def main():
    (ROOT / "trino/catalog").mkdir(exist_ok=True)
    for layer in ("bronze", "silver", "gold"):
        (ROOT / "catalog" / f"{layer}.properties").write_text(f"""connector.name=iceberg
iceberg.catalog.type=rest
iceberg.rest-catalog.uri=http://lakekeeper:8181/catalog
iceberg.rest-catalog.warehouse={layer}
iceberg.rest-catalog.nested-namespace-enabled=true
iceberg.unique-table-location=true
fs.native-s3.enabled=true
s3.endpoint=http://minio:9000
s3.path-style-access=true
s3.region=us-east-1
s3.aws-access-key=minioadmin
s3.aws-secret-key=minioadmin
""", encoding="utf-8")
    (ROOT / "catalog" / "tpch.properties").write_text("connector.name=tpch\ntpch.splits-per-node=3\n")
    compose("up", "-d", "postgres", "minio", "buckets", "migrate", "lakekeeper")
    base = "http://127.0.0.1:18181/management/v1"
    for attempt in range(90):
        try:
            response = requests.get(base + "/info", timeout=3)
            if response.ok:
                break
        except requests.RequestException:
            pass
        time.sleep(2)
    else:
        raise TimeoutError("Lakekeeper is not ready")
    info = response.json()
    if not info.get("bootstrapped", False):
        response = requests.post(base + "/bootstrap", json={"accept-terms-of-use": True}, timeout=30)
        response.raise_for_status()
    response = requests.get(base + "/warehouse", params={"project-id": "00000000-0000-0000-0000-000000000000"}, timeout=30)
    response.raise_for_status()
    existing = {w.get("name", w.get("warehouse-name")) for w in response.json().get("warehouses", [])}
    for layer in ("bronze", "silver", "gold"):
        payload = {"warehouse-name": layer, "project-id": "00000000-0000-0000-0000-000000000000",
            "storage-profile": {"type": "s3", "bucket": layer, "key-prefix": "", "endpoint": "http://minio:9000",
                "region": "us-east-1", "path-style-access": True, "flavor": "s3-compat", "sts-enabled": False},
            "storage-credential": {"type": "s3", "credential-type": "access-key",
                "access-key-id": "minioadmin", "secret-access-key": "minioadmin"}}
        (ROOT / "warehouses" / f"{layer}.json").write_text(json.dumps(payload, indent=2) + "\n")
        if layer not in existing:
            response = requests.post(base + "/warehouse", json=payload, timeout=30)
            if not response.ok:
                raise RuntimeError(response.text)
    compose("up", "-d", "trino", "spark")
    wait_trino()
    save_json("warehouses.json", requests.get(base + "/warehouse", timeout=30).json())
    (ROOT / "results" / "docker-ps.txt").write_text(compose("ps", capture=True))


if __name__ == "__main__":
    main()
