from athena_client import execute_athena_query

sql = """

SELECT *
FROM ga4_data.fact_google_analytics_month
LIMIT 5

"""

result = execute_athena_query(sql)

print(result)
