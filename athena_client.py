import boto3
import time

ATHENA_DATABASE = "domo_reports_s3"

ATHENA_OUTPUT = \
"s3://keynes-athena-results-srinivas/"


athena = boto3.client(
    "athena",
    region_name="us-east-1"
)


def execute_athena_query(sql):

    response = athena.start_query_execution(

        QueryString=sql,

        QueryExecutionContext={
            "Database":
            ATHENA_DATABASE
        },

        ResultConfiguration={
            "OutputLocation":
            ATHENA_OUTPUT
        }
    )

    query_execution_id = response[
        "QueryExecutionId"
    ]

    # =====================================================
    # WAIT FOR COMPLETION
    # =====================================================

    while True:

        result = athena.get_query_execution(

            QueryExecutionId=
            query_execution_id
        )

        status = result[
            "QueryExecution"
        ]["Status"]["State"]

        if status in [
            "SUCCEEDED",
            "FAILED",
            "CANCELLED"
        ]:
            break

        time.sleep(2)

    # =====================================================
    # FETCH RESULTS
    # =====================================================

    results = athena.get_query_results(

        QueryExecutionId=
        query_execution_id
    )

    rows = []

    for row in results[
        "ResultSet"
    ]["Rows"]:

        data = []

        for col in row["Data"]:

            data.append(
                col.get(
                    "VarCharValue",
                    ""
                )
            )

        rows.append(data)

    return {

        "query_execution_id":
        query_execution_id,

        "status":
        status,

        "rows":
        rows
    }
