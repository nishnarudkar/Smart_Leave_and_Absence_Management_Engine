import boto3
import json
from decimal import Decimal

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("leave_balances")


def decimal_to_int(obj):
    if isinstance(obj, Decimal):
        return int(obj)
    raise TypeError


def lambda_handler(event, context):

    # Works with API Gateway
    employee_id = event.get("queryStringParameters", {}).get("employee_id")

    if not employee_id:
        return {
            "statusCode": 400,
            "headers": {
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps({
                "message": "employee_id is required"
            })
        }

    response = table.query(
        KeyConditionExpression=boto3.dynamodb.conditions.Key("employee_id").eq(employee_id)
    )

    balances = {
        "SICK": 0,
        "CASUAL": 0,
        "EARNED": 0
    }

    for item in response["Items"]:

        leave_type = item["leave_type_year"].split("#")[0]

        balances[leave_type] = item["remaining"]

    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
        },
        "body": json.dumps(balances, default=decimal_to_int)
    }
