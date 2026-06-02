import re


def detect_query_granularity(
    user_prompt: str
):

    prompt = user_prompt.lower()

    # =====================================================
    # LAMBDA LEVEL QUERIES
    # =====================================================

    lambda_keywords = [

        "source medium",

        "source_medium",

        "sessions",

        "new users",

        "transactions",

        "channel",

        "device",

        "country"
    ]

    for keyword in lambda_keywords:

        if keyword in prompt:

            return "lambda"

    # =====================================================
    # MONTH LEVEL
    # =====================================================

    month_keywords = [

        "month",

        "monthly",

        "last month",

        "this month"
    ]

    for keyword in month_keywords:

        if keyword in prompt:

            return "month"

    # =====================================================
    # DATE RANGE
    # =====================================================

    date_patterns = [

        r"\d{4}-\d{2}-\d{2}",

        r"between",

        r"from",

        r"to"
    ]

    for pattern in date_patterns:

        if re.search(
            pattern,
            prompt
        ):

            return "range"

    # =====================================================
    # DEFAULT
    # =====================================================

    return "date"


def route_ga_query(
    user_prompt: str
):

    granularity = detect_query_granularity(
        user_prompt
    )

    # =====================================================
    # LAMBDA
    # =====================================================

    if granularity == "lambda":

        return {

            "source":
            "lambda",

            "function":
            "pull_ga4_data_alldimensions"
        }

    # =====================================================
    # MONTH TABLE
    # =====================================================

    elif granularity == "month":

        return {

            "source":
            "athena",

            "table":
            "ga4_data.fact_google_analytics_month"
        }

    # =====================================================
    # RANGE
    # =====================================================

    elif granularity == "range":

        return {

            "source":
            "lambda",

            "function":
            "pull_ga4_data_alldimensions"
        }

    # =====================================================
    # DATE TABLE
    # =====================================================

    return {

        "source":
        "athena",

        "table":
        "ga4_data.fact_google_analytics_date"
    }
