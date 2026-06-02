from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ga_router import route_ga_query

from athena_client import execute_athena_query

from lambda_client import invoke_ga_lambda

from cache_client import (
    get_cache,
    set_cache
)

from property_cache import (
    advertiser_property_cache
)

from prompt_parser import (
    extract_advertiser,
    extract_level
)

import uuid
import time

from datetime import datetime

app = FastAPI()

# =====================================================
# CORS
# =====================================================

app.add_middleware(

    CORSMiddleware,

    allow_origins=["*"],

    allow_credentials=True,

    allow_methods=["*"],

    allow_headers=["*"],
)

# =====================================================
# QUERY STORAGE
# =====================================================

query_history = []

# =====================================================
# ADVERTISER CACHE
# =====================================================

advertiser_cache = []

# =====================================================
# LOAD ADVERTISERS AT STARTUP
# =====================================================

@app.on_event("startup")
async def load_advertisers():

    global advertiser_cache

    sql = """

    SELECT DISTINCT keynes_advertiser
    FROM ga4_data.fact_google_analytics_date
    WHERE keynes_advertiser IS NOT NULL

    """

    try:

        result = execute_athena_query(sql)

        rows = result.get(
            "rows",
            []
        )

        advertisers = []

        for row in rows[1:]:

            if len(row) > 0:

                advertisers.append(
                    row[0]
                )

        advertiser_cache = advertisers

        print("\n========== ADVERTISERS LOADED ==========")
        print("Total advertisers:", len(advertiser_cache))

    except Exception as e:

        print("\n========== ADVERTISER LOAD FAILED ==========")
        print(str(e))

# =====================================================
# HEALTH
# =====================================================

@app.get("/health")
async def health():

    return {

        "status": "healthy",

        "environment": "qa"
    }

# =====================================================
# GENERIC QUERY ENDPOINT
# =====================================================

@app.post("/query")
async def execute_query(payload: dict):

    user_prompt = payload.get(
        "prompt",
        ""
    )

    cache_key = user_prompt

    # =====================================================
    # CACHE CHECK
    # =====================================================

    cached_response = get_cache(
        cache_key
    )

    if cached_response:

        print("\n========== CACHE HIT ==========")

        return {

            "success": True,

            "cache_hit": True,

            "response":
            cached_response
        }

    query_id = str(uuid.uuid4())

    start_time = time.time()

    # =====================================================
    # ROUTE QUERY
    # =====================================================

    route = route_ga_query(
        user_prompt
    )

    print("\n========== ROUTE ==========")
    print(route)

    # =====================================================
    # LAMBDA FLOW
    # =====================================================

    if route["source"] == "lambda":

        advertiser = extract_advertiser(
            user_prompt
        )

        level = extract_level(
            user_prompt
        )

        print("\n========== EXTRACTED ==========")
        print("Advertiser:", advertiser)
        print("Level:", level)

        property_name = (
            advertiser_property_cache.get(
                advertiser
            )
        )

        if not property_name:

            return {

                "success": False,

                "error":
                f"No property mapping found for advertiser: {advertiser}"
            }

        lambda_result = invoke_ga_lambda(

            keynes_advertiser=
            advertiser,

            property_name=
            property_name,

            level=
            level,

            start_date=
            "2025-05-01",

            end_date=
            "2025-05-31",

            metric_set="core"
        )

        execution_time = round(

            time.time() - start_time,

            2
        )

        response = {

            "success":
            True,

            "query_id":
            query_id,

            "route":
            route,

            "cache_hit":
            False,

            "execution_time_seconds":
            execution_time,

            "advertiser":
            advertiser,

            "level":
            level,

            "lambda_result":
            lambda_result
        }

        # =====================================================
        # CACHE STORE
        # =====================================================

        set_cache(

            cache_key,

            response
        )

        # =====================================================
        # QUERY LOGGING
        # =====================================================

        query_record = {

            "query_id":
            query_id,

            "timestamp":
            str(datetime.utcnow()),

            "user_prompt":
            user_prompt,

            "generated_sql":
            "LAMBDA_EXECUTION",

            "dataset":
            "pull_ga4_data_alldimensions",

            "status":
            "COMPLETED",

            "cache_hit":
            False,

            "execution_time_seconds":
            execution_time,

            "row_count":
            len(str(lambda_result))
        }

        query_history.append(
            query_record
        )

        return response

    # =====================================================
    # ATHENA FLOW
    # =====================================================

    selected_table = route["table"]

    generated_sql = f"""

    SELECT *
    FROM {selected_table}
    LIMIT 10

    """

    athena_result = execute_athena_query(
        generated_sql
    )

    execution_time = round(

        time.time() - start_time,

        2
    )

    query_status = athena_result.get(
        "status",
        "UNKNOWN"
    )

    query_execution_id = athena_result.get(
        "query_execution_id",
        ""
    )

    rows = athena_result.get(
        "rows",
        []
    )

    response = {

        "success":
        True,

        "query_id":
        query_id,

        "route":
        route,

        "generated_sql":
        generated_sql,

        "execution_time_seconds":
        execution_time,

        "results":
        rows
    }

    # =====================================================
    # CACHE STORE
    # =====================================================

    set_cache(

        cache_key,

        response
    )

    # =====================================================
    # QUERY LOGGING
    # =====================================================

    query_record = {

        "query_id":
        query_id,

        "timestamp":
        str(datetime.utcnow()),

        "user_prompt":
        user_prompt,

        "generated_sql":
        generated_sql,

        "dataset":
        selected_table,

        "status":
        query_status,

        "cache_hit":
        False,

        "athena_execution_id":
        query_execution_id,

        "execution_time_seconds":
        execution_time,

        "row_count":
        len(rows)
    }

    query_history.append(
        query_record
    )

    return response

# =====================================================
# ADVERTISERS
# =====================================================

@app.get("/advertisers")
async def advertisers():

    return {

        "success": True,

        "total_advertisers":
        len(advertiser_cache),

        "advertisers":
        advertiser_cache
    }

# =====================================================
# MONTHLY USERS
# =====================================================

@app.get("/ga/monthly-users")
async def monthly_users():

    sql = """

    SELECT *
    FROM ga4_data.fact_ga4_month
    LIMIT 10

    """

    try:

        result = execute_athena_query(sql)

        return {

            "success": True,

            "source": "athena",

            "table": "fact_ga4_month",

            "result": result
        }

    except Exception as e:

        return {

            "success": False,

            "error": str(e)
        }

# =====================================================
# COUNTRY ANALYTICS
# =====================================================

@app.get("/ga/country")
async def country_analytics():

    advertiser = "Brighton"

    property_name = (
        advertiser_property_cache.get(
            advertiser
        )
    )

    result = invoke_ga_lambda(

        keynes_advertiser=
        advertiser,

        property_name=
        property_name,

        level="country",

        start_date=
        "2025-05-01",

        end_date=
        "2025-05-31",

        metric_set="core"
    )

    return {

        "source":
        "lambda",

        "level":
        "country",

        "result":
        result
    }

# =====================================================
# DEVICE ANALYTICS
# =====================================================

@app.get("/ga/device")
async def device_analytics():

    advertiser = "Brighton"

    property_name = (
        advertiser_property_cache.get(
            advertiser
        )
    )

    result = invoke_ga_lambda(

        keynes_advertiser=
        advertiser,

        property_name=
        property_name,

        level="device",

        start_date=
        "2025-05-01",

        end_date=
        "2025-05-31",

        metric_set="core"
    )

    return {

        "source":
        "lambda",

        "level":
        "device",

        "result":
        result
    }

# =====================================================
# CHANNEL ANALYTICS
# =====================================================

@app.get("/ga/channel")
async def channel_analytics():

    advertiser = "Brighton"

    property_name = (
        advertiser_property_cache.get(
            advertiser
        )
    )

    result = invoke_ga_lambda(

        keynes_advertiser=
        advertiser,

        property_name=
        property_name,

        level="channel",

        start_date=
        "2025-05-01",

        end_date=
        "2025-05-31",

        metric_set="core"
    )

    return {

        "source":
        "lambda",

        "level":
        "channel",

        "result":
        result
    }

# =====================================================
# SOURCE MEDIUM ANALYTICS
# =====================================================

@app.get("/ga/source-medium")
async def source_medium_analytics():

    advertiser = "Brighton"

    property_name = (
        advertiser_property_cache.get(
            advertiser
        )
    )

    result = invoke_ga_lambda(

        keynes_advertiser=
        advertiser,

        property_name=
        property_name,

        level="source_medium",

        start_date=
        "2025-05-01",

        end_date=
        "2025-05-31",

        metric_set="core"
    )

    return {

        "source":
        "lambda",

        "level":
        "source_medium",

        "result":
        result
    }

# =====================================================
# QUERY STATS
# =====================================================

@app.get("/query-stats")
async def query_stats():

    total_queries = len(
        query_history
    )

    completed = len([

        q for q in query_history

        if q["status"] == "COMPLETED"
    ])

    failed = len([

        q for q in query_history

        if q["status"] == "FAILED"
    ])

    avg_latency = 0

    if total_queries > 0:

        avg_latency = round(

            sum([

                q["execution_time_seconds"]

                for q in query_history

            ]) / total_queries,

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

# =====================================================
# LIVE QUERIES
# =====================================================

@app.get("/live-queries")
async def live_queries():

    latest_queries = sorted(

        query_history,

        key=lambda x:
        x["timestamp"],

        reverse=True

    )[:10]

    return {

        "queries":
        latest_queries
    }

# =====================================================
# SLOW QUERIES
# =====================================================

@app.get("/slow-queries")
async def slow_queries():

    slow = [

        q for q in query_history

        if q["execution_time_seconds"] > 3
    ]

    return {

        "slow_queries":
        slow
    }

# =====================================================
# CACHE ANALYTICS
# =====================================================

@app.get("/cache-analytics")
async def cache_analytics():

    total = len(query_history)

    hits = len([

        q for q in query_history

        if q["cache_hit"]
    ])

    misses = total - hits

    hit_ratio = 0

    if total > 0:

        hit_ratio = round(

            (hits / total) * 100,

            2
        )

    return {

        "cache_hits":
        hits,

        "cache_misses":
        misses,

        "cache_hit_ratio":
        hit_ratio
    }

# =====================================================
# FAILED QUERIES
# =====================================================

@app.get("/failed-queries")
async def failed_queries():

    failed = [

        q for q in query_history

        if q["status"] == "FAILED"
    ]

    return {

        "failed_queries":
        failed
    }
