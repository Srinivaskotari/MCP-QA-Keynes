from lambda_client import invoke_ga_lambda

result = invoke_ga_lambda(

    keynes_advertiser="LSPACE",

    level="source_medium",

    start_date="2025-05-01",

    end_date="2025-05-31",

    metric_set="core"
)

print(result)

