CREATE TABLE IF NOT EXISTS gold.mart.large_volume_customer WITH (format='PARQUET') AS
SELECT c.name,c.custkey,o.orderkey,o.orderdate,o.totalprice,
 CAST(t.total_quantity AS DECIMAL(18,2)) AS total_quantity
FROM silver.core.dim_customer c JOIN silver.core.orders o ON c.custkey=o.custkey
JOIN silver.core.order_totals t ON o.orderkey=t.orderkey
WHERE t.total_quantity>300
ORDER BY o.totalprice DESC,o.orderdate LIMIT 100;
