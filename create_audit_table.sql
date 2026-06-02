CREATE EXTERNAL TABLE IF NOT EXISTS mcp_query_audit (

    query_id STRING,

    timestamp STRING,

    user_prompt STRING,

    generated_sql STRING,

    dataset STRING,

    status STRING,

    execution_time_seconds DOUBLE,

    cache_hit BOOLEAN,

    row_count INT,

    athena_execution_id STRING

)

ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'

LOCATION 's3://keynes-athena-results-srinivas/mcp-audit/';
