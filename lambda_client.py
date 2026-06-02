import boto3
import json

lambda_client = boto3.client(

    "lambda",

    region_name="us-east-1"
)

LAMBDA_NAME = (
    "pull_ga4_data_alldimensions"
)


def invoke_ga_lambda(

    keynes_advertiser,

    property_name,

    level="source_medium",

    start_date="2025-05-01",

    end_date="2025-05-31",

    metric_set="core"
):

    payload = {

        "keynes_advertiser":
        keynes_advertiser,

        "property_name":
        property_name,

        "start_date":
        start_date,

        "end_date":
        end_date,

        "level":
        level,

        "metric_set":
        metric_set
    }

    print("\n========== LAMBDA PAYLOAD ==========")
    print(payload)

    response = lambda_client.invoke(

        FunctionName=LAMBDA_NAME,

        InvocationType="RequestResponse",

        Payload=json.dumps(payload)
    )

    result = json.loads(

        response["Payload"]
        .read()
        .decode("utf-8")
    )

    return result
