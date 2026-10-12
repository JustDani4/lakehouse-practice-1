"""Read file footers through S3 and verify actual format, codec and row count."""
from urllib.parse import urlparse
import pyarrow.fs as fs
import pyarrow.parquet as pq
import pyarrow.orc as orc
from lakehouse import query, save_json, wait_trino


def main():
    wait_trino()
    s3 = fs.S3FileSystem(access_key="minioadmin", secret_key="minioadmin", region="us-east-1",
        endpoint_override="127.0.0.1:19000", scheme="http")
    results=[]
    for fmt in ("parquet","orc"):
        for codec in ("none","snappy","gzip","zstd"):
            slug=fmt+"_"+codec
            paths=query(f'SELECT file_path,record_count,file_size_in_bytes FROM bronze.bench."lineitem_{slug}$files"',"audit-files-"+slug)[0]
            files=[]
            for path, rows, size in paths:
                parsed=urlparse(path)
                source=s3.open_input_file(parsed.netloc+parsed.path)
                if fmt=="parquet":
                    metadata=pq.ParquetFile(source).metadata
                    actual={metadata.row_group(i).column(j).compression for i in range(metadata.num_row_groups) for j in range(metadata.num_columns)}
                    expected={"none":"UNCOMPRESSED","snappy":"SNAPPY","gzip":"GZIP","zstd":"ZSTD"}[codec]
                    actual_rows=metadata.num_rows
                else:
                    metadata=orc.ORCFile(source)
                    actual={metadata.compression}
                    expected={"none":"UNCOMPRESSED","snappy":"SNAPPY","gzip":"ZLIB","zstd":"ZSTD"}[codec]
                    actual_rows=metadata.nrows
                assert actual=={expected},(slug,actual,expected)
                assert actual_rows==rows,(path,actual_rows,rows)
                files.append({"path":path,"rows":rows,"bytes":size,"physical_compression":sorted(actual)})
            assert sum(f["rows"] for f in files)==6001215
            results.append({"slug":slug,"format":fmt,"expected_codec":codec,"files":files,"verified":True})
    save_json("physical_files.json",results)


if __name__=="__main__":
    main()
