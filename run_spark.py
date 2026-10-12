"""Launch a fresh Spark JVM for each combination and check all results."""
import subprocess
from lakehouse import ROOT, RESULTS, compose, wait_trino


def main():
    jars = ROOT / "jars"
    jars.mkdir(exist_ok=True)
    for artifact in ("iceberg-spark-runtime-3.5_2.12", "iceberg-aws-bundle"):
        name = f"{artifact}-1.10.1.jar"
        if not (jars / name).exists():
            subprocess.run(["curl", "-fsSL", "--retry", "3", "-o", str(jars/name),
                f"https://repo.maven.apache.org/maven2/org/apache/iceberg/{artifact}/1.10.1/{name}"], check=True)
    compose("stop", "trino")
    try:
        for fmt in ("parquet", "orc"):
            for codec in ("none", "snappy", "gzip", "zstd"):
                slug = f"{fmt}_{codec}"
                if (RESULTS / f"spark_{slug}.json").exists():
                    continue
                compose("restart", "minio")
                options = {
                    "spark.sql.extensions": "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions",
                    "spark.sql.catalog.bronze": "org.apache.iceberg.spark.SparkCatalog",
                    "spark.sql.catalog.bronze.type": "rest",
                    "spark.sql.catalog.bronze.uri": "http://lakekeeper:8181/catalog",
                    "spark.sql.catalog.bronze.warehouse": "bronze",
                    "spark.sql.catalog.bronze.io-impl": "org.apache.iceberg.aws.s3.S3FileIO",
                    "spark.sql.catalog.bronze.s3.endpoint": "http://minio:9000",
                    "spark.sql.catalog.bronze.s3.path-style-access": "true",
                    "spark.sql.catalog.bronze.s3.access-key-id": "minioadmin",
                    "spark.sql.catalog.bronze.s3.secret-access-key": "minioadmin",
                    "spark.sql.catalog.bronze.client.region": "us-east-1",
                    "spark.sql.shuffle.partitions": "8",
                    "spark.default.parallelism": "2",
                    "spark.ui.enabled": "false",
                }
                command = ["exec", "-T", "-e", "SPARK_LOCAL_IP=127.0.0.1", "spark",
                    "/opt/spark/bin/spark-submit", "--master", "local[2]", "--driver-memory", "1g",
                    "--jars", "/opt/lab-jars/iceberg-spark-runtime-3.5_2.12-1.10.1.jar,/opt/lab-jars/iceberg-aws-bundle-1.10.1.jar"]
                for key, value in options.items():
                    command.extend(["--conf", key+"="+value])
                command.extend(["/workspace/spark_bench.py", slug])
                print("Spark: " + slug, flush=True)
                try:
                    output = compose(*command, capture=True)
                except subprocess.CalledProcessError as error:
                    (RESULTS / f"spark_{slug}.log").write_text((error.stdout or "")+(error.stderr or ""))
                    raise
                (RESULTS / f"spark_{slug}.log").write_text(output)
                print(output, flush=True)
    finally:
        compose("start", "trino")
        wait_trino()


if __name__ == "__main__":
    main()
