CREATE SCHEMA IF NOT EXISTS bronze.raw;
CREATE SCHEMA IF NOT EXISTS bronze.bench;
CREATE SCHEMA IF NOT EXISTS silver.core;
CREATE SCHEMA IF NOT EXISTS gold.mart;
CREATE TABLE IF NOT EXISTS bronze.raw.customer WITH (format='PARQUET') AS
SELECT custkey,name,mktsegment FROM tpch.sf1.customer;
CREATE TABLE IF NOT EXISTS bronze.raw.orders WITH (format='PARQUET') AS
SELECT orderkey,custkey,orderstatus,totalprice,orderdate FROM tpch.sf1.orders;
