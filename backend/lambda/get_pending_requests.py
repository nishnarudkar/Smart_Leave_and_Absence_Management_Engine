import boto3
import json
from decimal import Decimal

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("leave_requests")


# Convert Decimal to int/float
def decimal_default(obj):
    if isinstance(obj, Decimal):
        return int(obj)
    raise TypeError


def lambda_handler(event, context):

    response = table.scan()

    pending = []

    for item in response["Items"]:
        if item["status"] == "PENDING":
            pending.append(item)

    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
        },
        "body": json.dumps(pending, default=decimal_default)
    }