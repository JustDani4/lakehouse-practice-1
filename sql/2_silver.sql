CREATE TABLE IF NOT EXISTS silver.core.dq_report WITH (format='PARQUET') AS
SELECT count(*) AS source_rows,
 count_if(l.quantity<=0 OR l.quantity IS NULL) AS invalid_quantity,
 count_if(l.extendedprice<0 OR l.extendedprice IS NULL) AS invalid_price,
 count_if(l.discount<0 OR l.discount>1 OR l.discount IS NULL) AS invalid_discount,
 count_if(o.orderkey IS NULL) AS missing_order,
 count_if(c.custkey IS NULL) AS missing_customer,
 count_if(l.shipdate<o.orderdate) AS invalid_shipdate
FROM bronze.bench.lineitem_parquet_zstd l
LEFT JOIN bronze.raw.orders o ON l.orderkey=o.orderkey
LEFT JOIN bronze.raw.customer c ON o.custkey=c.custkey;
CREATE TABLE IF NOT EXISTS silver.core.dim_customer WITH (format='PARQUET') AS
SELECT custkey,trim(name) AS name,upper(trim(mktsegment)) AS market_segment
FROM bronze.raw.customer WHERE custkey IS NOT NULL AND name IS NOT NULL;
CREATE TABLE IF NOT EXISTS silver.core.orders WITH (format='PARQUET') AS
SELECT o.orderkey,o.custkey,upper(trim(o.orderstatus)) AS order_status,
 CAST(o.totalprice AS DECIMAL(18,2)) AS totalprice,o.orderdate
FROM bronze.raw.orders o JOIN silver.core.dim_customer c ON o.custkey=c.custkey
WHERE o.totalprice>=0 AND o.orderdate IS NOT NULL;
CREATE TABLE IF NOT EXISTS silver.core.fact_lineitem WITH (format='PARQUET') AS
SELECT l.orderkey,l.linenumber,CAST(l.quantity AS DECIMAL(12,2)) AS quantity,
 CAST(l.extendedprice AS DECIMAL(18,2)) AS gross_amount,
 CAST(l.discount AS DECIMAL(4,2)) AS discount,
 CAST(CAST(l.extendedprice AS DECIMAL(18,2))*(1-CAST(l.discount AS DECIMAL(4,2))) AS DECIMAL(18,2)) AS net_amount,
 o.custkey,o.orderdate,year(o.orderdate) AS order_year
FROM bronze.bench.lineitem_parquet_zstd l JOIN silver.core.orders o ON l.orderkey=o.orderkey
WHERE l.quantity>0 AND l.extendedprice>=0 AND l.discount BETWEEN 0 AND 1
 AND l.shipdate>=o.orderdate;
CREATE TABLE IF NOT EXISTS silver.core.order_totals WITH (format='PARQUET') AS
SELECT orderkey,sum(quantity) AS total_quantity,count(*) AS item_count,
 sum(net_amount) AS net_amount
FROM silver.core.fact_lineitem GROUP BY orderkey;
