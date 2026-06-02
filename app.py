from fastapi import FastAPI
import boto3
import time
import os
import json
import uuid
import redis

from datetime import datetime
from collections import Counter

from datasets import DATASETS

# =========================================================
# FASTAPI
# =========================================================

app = FastAPI()

# =========================================================
# CONFIG
# =========================================================

REGION = "us-east-1"

DATABASE = "domo_reports_s3"

OUTPUT_BUCKET = "s3://keynes-athena-results-srinivas"

AUDIT_BUCKET = "keynes-athena-results-srinivas"

AUDIT_PREFIX = "mcp-audit/"

MAX_QUERY_LENGTH = 5000

CACHE_TTL_SECONDS = 300

LOG_DIR = "logs"

LOG_FILE = f"{LOG_DIR}/query_history.log"

# =========================================================
# AWS CLIENTS
# =========================================================

athena = boto3.client(

    "athena",

    region_name=REGION

)

s3 = boto3.client(

    "s3",

    region_name=REGION

)

# =========================================================
# REDIS
# =========================================================

redis_client = redis.Redis(

    host="localhost",

    port=6379,

    decode_responses=True

)

# =========================================================
# SECURITY
# =========================================================

ALLOWED_TABLES = [

    "client_reporting_date_dataset",

    "client_reporting_geo_dataset",

    "client_reporting_network_dataset_myreports",

    "client_reporting_hour_dataset"

]

BLOCKED_KEYWORDS = [

    "DROP",
    "DELETE",
    "TRUNCATE",
    "ALTER",
    "INSERT",
    "UPDATE",
    "CREATE"

]

# =========================================================
# LOGS
# =========================================================

os.makedirs(LOG_DIR, exist_ok=True)

# =========================================================
# HELPERS
# =========================================================

def get_cache_key(query):

    return f"cache:{query}"

def get_registry_key(query_id):

    return f"registry:{query_id}"

def log_query(entry):

    with open(LOG_FILE, "a") as f:

        f.write(json.dumps(entry) + "\n")

# =========================================================
# AUDIT WRITER
# =========================================================

def write_audit_record(record):

    try:

        key = (

            AUDIT_PREFIX +

            f"{record['query_id']}.json"

        )

        s3.put_object(

            Bucket=AUDIT_BUCKET,

            Key=key,

            Body=json.dumps(record),

            ContentType="application/json"

        )

    except Exception as e:

        print(

            "Audit write failed:",

            str(e)

        )

# =========================================================
# SQL VALIDATION
# =========================================================

def validate_sql(sql):

    sql_upper = sql.upper()

    if len(sql) > MAX_QUERY_LENGTH:

        return {

            "valid": False,

            "error":
            "Query exceeds maximum length"

        }

    allowed_starts = [

        "SELECT",
        "SHOW",
        "WITH"

    ]

    if not any(
        sql_upper.strip().startswith(x)
        for x in allowed_starts
    ):

        return {

            "valid": False,

            "error":
            "Only SELECT/SHOW/WITH allowed"

        }

    for keyword in BLOCKED_KEYWORDS:

        if keyword in sql_upper:

            return {

                "valid": False,

                "error":
                f"Blocked keyword: {keyword}"

            }

    dataset = None

    found = False

    for table in ALLOWED_TABLES:

        if table.lower() in sql.lower():

            dataset = table

            found = True

            break

    if sql_upper.startswith("SHOW COLUMNS"):

        found = True

    if not found:

        return {

            "valid": False,

            "error":
            "Unauthorized table"

        }

    if (
        "LIMIT" not in sql_upper
        and sql_upper.startswith("SELECT")
    ):

        sql += "\nLIMIT 100"

    return {

        "valid": True,

        "sql": sql,

        "dataset": dataset

    }

# =========================================================
# REGISTRY
# =========================================================

def register_query(

    query_id,
    user_prompt,
    sql,
    dataset

):

    entry = {

        "query_id":
        query_id,

        "timestamp":
        str(datetime.utcnow()),

        "user_prompt":
        user_prompt,

        "generated_sql":
        sql,

        "dataset":
        dataset,

        "status":
        "STARTING",

        "cache_hit":
        False

    }

    redis_client.set(

        get_registry_key(query_id),

        json.dumps(entry)

    )

def update_registry(

    query_id,
    updates

):

    data = redis_client.get(

        get_registry_key(query_id)

    )

    if not data:
        return

    current = json.loads(data)

    current.update(updates)

    redis_client.set(

        get_registry_key(query_id),

        json.dumps(current)

    )

# =========================================================
# ATHENA EXECUTION
# =========================================================

def execute_query(

    query_id,
    sql

):

    start_time = time.time()

    response = athena.start_query_execution(

        QueryString=sql,

        QueryExecutionContext={
            "Database": DATABASE
        },

        ResultConfiguration={
            "OutputLocation": OUTPUT_BUCKET
        }

    )

    athena_execution_id = response[
        "QueryExecutionId"
    ]

    update_registry(

        query_id,

        {

            "status":
            "RUNNING",

            "athena_execution_id":
            athena_execution_id

        }

    )

    while True:

        status = athena.get_query_execution(

            QueryExecutionId=athena_execution_id

        )

        state = status[
            "QueryExecution"
        ]["Status"]["State"]

        update_registry(

            query_id,

            {

                "status": state

            }

        )

        if state == "SUCCEEDED":
            break

        if state in [

            "FAILED",
            "CANCELLED"

        ]:

            raise Exception(
                f"Athena query {state}"
            )

        time.sleep(2)

    results = athena.get_query_results(

        QueryExecutionId=athena_execution_id

    )

    rows = results["ResultSet"]["Rows"]

    if len(rows) <= 1:

        parsed_rows = []

    else:

        headers = [

            col.get("VarCharValue", "")

            for col in rows[0]["Data"]

        ]

        parsed_rows = []

        for row in rows[1:]:

            values = [

                col.get("VarCharValue", "")

                for col in row["Data"]

            ]

            parsed_rows.append(

                dict(zip(headers, values))

            )

    execution_time = round(

        time.time() - start_time,

        2

    )

    redis_client.setex(

        get_cache_key(sql),

        CACHE_TTL_SECONDS,

        json.dumps(parsed_rows)

    )

    update_registry(

        query_id,

        {

            "status":
            "COMPLETED",

            "execution_time_seconds":
            execution_time,

            "row_count":
            len(parsed_rows)

        }

    )

    audit_record = json.loads(

        redis_client.get(

            get_registry_key(query_id)

        )

    )

    write_audit_record(audit_record)

    log_query({

        "query_id":
        query_id,

        "query":
        sql,

        "execution_time_seconds":
        execution_time

    })

    return parsed_rows

# =========================================================
# HEALTH
# =========================================================

@app.get("/health")
def health():

    return {

        "status":
        "healthy"

    }

# =========================================================
# LIVE QUERIES
# =========================================================

@app.get("/live-queries")
def live_queries():

    keys = redis_client.keys(

        "registry:*"

    )

    output = []

    for key in keys:

        output.append(

            json.loads(

                redis_client.get(key)

            )

        )

    return {

        "queries": output

    }

# =========================================================
# QUERY STATS
# =========================================================

@app.get("/query-stats")
def query_stats():

    keys = redis_client.keys(

        "registry:*"

    )

    total_queries = len(keys)

    completed = 0

    failed = 0

    total_latency = 0

    for key in keys:

        data = json.loads(

            redis_client.get(key)

        )

        if data.get("status") == "COMPLETED":
            completed += 1

        if data.get("status") == "FAILED":
            failed += 1

        total_latency += data.get(

            "execution_time_seconds",

            0

        )

    avg_latency = 0

    if total_queries > 0:

        avg_latency = round(

            total_latency /
            total_queries,

            2

        )

    return {

        "total_queries":
        total_queries,

        "completed":
        completed,

        "failed":
        failed,

        "average_latency_seconds":
        avg_latency

    }

# =========================================================
# SLOW QUERIES
# =========================================================

@app.get("/slow-queries")
def slow_queries():

    keys = redis_client.keys(

        "registry:*"

    )

    slow = []

    for key in keys:

        data = json.loads(

            redis_client.get(key)

        )

        latency = data.get(

            "execution_time_seconds",

            0

        )

        if latency >= 5:

            slow.append(data)

    slow = sorted(

        slow,

        key=lambda x:
        x.get(
            "execution_time_seconds",
            0
        ),

        reverse=True

    )

    return {

        "slow_queries":
        slow[:20]

    }

# =========================================================
# TOP DATASETS
# =========================================================

@app.get("/top-datasets")
def top_datasets():

    keys = redis_client.keys(

        "registry:*"

    )

    datasets = []

    for key in keys:

        data = json.loads(

            redis_client.get(key)

        )

        dataset = data.get("dataset")

        if dataset:
            datasets.append(dataset)

    counts = Counter(datasets)

    return {

        "top_datasets":
        counts.most_common(10)

    }

# =========================================================
# CACHE ANALYTICS
# =========================================================

@app.get("/cache-analytics")
def cache_analytics():

    keys = redis_client.keys(

        "registry:*"

    )

    total = len(keys)

    hits = 0

    for key in keys:

        data = json.loads(

            redis_client.get(key)

        )

        if data.get("cache_hit"):
            hits += 1

    ratio = 0

    if total > 0:

        ratio = round(

            (hits / total) * 100,

            2

        )

    return {

        "total_queries":
        total,

        "cache_hits":
        hits,

        "cache_hit_ratio_percent":
        ratio

    }

# =========================================================
# FAILED QUERIES
# =========================================================

@app.get("/failed-queries")
def failed_queries():

    keys = redis_client.keys(

        "registry:*"

    )

    failed = []

    for key in keys:

        data = json.loads(

            redis_client.get(key)

        )

        if data.get("status") == "FAILED":

            failed.append(data)

    return {

        "failed_queries":
        failed

    }

# =========================================================
# PROMPT ANALYTICS
# =========================================================

@app.get("/prompt-analytics")
def prompt_analytics():

    keys = redis_client.keys(

        "registry:*"

    )

    prompts = []

    for key in keys:

        data = json.loads(

            redis_client.get(key)

        )

        prompt = data.get(

            "user_prompt",

            ""

        )

        if prompt:
            prompts.append(prompt)

    counts = Counter(prompts)

    return {

        "top_prompts":
        counts.most_common(20)

    }

# =========================================================
# QUERY
# =========================================================

@app.post("/query")
def query(payload: dict):

    sql = payload.get("sql")

    user_prompt = payload.get(

        "user_prompt",

        "unknown"

    )

    if not sql:

        return {

            "success": False,

            "error":
            "No SQL provided"

        }

    validation = validate_sql(sql)

    if not validation["valid"]:

        return {

            "success": False,

            "error":
            validation["error"]

        }

    sql = validation["sql"]

    dataset = validation.get("dataset")

    query_id = str(uuid.uuid4())

    register_query(

        query_id,
        user_prompt,
        sql,
        dataset

    )

    cache_key = get_cache_key(sql)

    cached = redis_client.get(cache_key)

    if cached:

        update_registry(

            query_id,

            {

                "status":
                "COMPLETED",

                "cache_hit":
                True,

                "row_count":
                len(json.loads(cached))

            }

        )

        audit_record = json.loads(

            redis_client.get(

                get_registry_key(query_id)

            )

        )

        write_audit_record(audit_record)

        return {

            "success": True,

            "cached": True,

            "query_id":
            query_id,

            "results":
            json.loads(cached)

        }

    try:

        results = execute_query(

            query_id,
            sql

        )

        return {

            "success": True,

            "query_id":
            query_id,

            "results":
            results

        }

    except Exception as e:

        update_registry(

            query_id,

            {

                "status":
                "FAILED",

                "error":
                str(e)

            }

        )

        return {

            "success": False,

            "error":
            str(e)

        }

# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(

        app,

        host="0.0.0.0",

        port=8000

    )
