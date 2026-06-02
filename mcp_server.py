from fastmcp import FastMCP

import requests

# =====================================================
# MCP SERVER
# =====================================================

mcp = FastMCP(
    "Keynes QA MCP Server"
)

# =====================================================
# GET CURRENT DATE
# =====================================================

@mcp.tool()
async def get_current_date():

    """
    Returns current system date.
    """

    response = requests.get(
        "http://localhost:8000/date"
    )

    return response.json()

# =====================================================
# QUERY ATHENA
# =====================================================

@mcp.tool()
async def query_athena(
    query: str
):

    """
    Execute Athena analytics queries.
    """

    response = requests.post(

        "http://localhost:8000/query",

        json={
            "query": query
        }
    )

    return response.json()

# =====================================================
# LIST ALL ADVERTISERS
# =====================================================

@mcp.tool()
async def list_all_advertisers():

    """
    Returns advertiser list.
    """

    response = requests.get(
        "http://localhost:8000/advertisers"
    )

    return response.json()

# =====================================================
# GET MONTHLY USERS
# =====================================================

@mcp.tool()
async def get_monthly_users():

    """
    Returns monthly users analytics.
    """

    response = requests.get(
        "http://localhost:8000/ga/monthly-users"
    )

    return response.json()

# =====================================================
# GET GA4 DATA
# =====================================================

@mcp.tool()
async def get_ga4_data(
    advertiser: str,
    level: str
):

    """
    Returns GA4 analytics data.

    Levels:
    - source_medium
    - country
    - device
    - channel
    """

    endpoint_map = {

        "source_medium":
        "http://localhost:8000/ga/source-medium",

        "country":
        "http://localhost:8000/ga/country",

        "device":
        "http://localhost:8000/ga/device",

        "channel":
        "http://localhost:8000/ga/channel"
    }

    endpoint = endpoint_map.get(
        level
    )

    if not endpoint:

        return {

            "success": False,

            "error":
            f"Unsupported level: {level}"
        }

    response = requests.get(
        endpoint
    )

    return response.json()

# =====================================================
# HEALTH CHECK
# =====================================================

@mcp.tool()
async def health_check():

    """
    Health check tool.
    """

    return {

        "success": True,

        "service":
        "keynes-qa-mcp",

        "status":
        "running"
    }

# =====================================================
# RUN MCP SERVER
# =====================================================

if __name__ == "__main__":

    mcp.run(

        transport="sse",

        host="0.0.0.0",

        port=9000
    )
