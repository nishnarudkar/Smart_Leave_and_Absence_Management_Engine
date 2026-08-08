import json
import boto3

dynamodb = boto3.resource("dynamodb")

requests_table = dynamodb.Table("leave_requests")
balances_table = dynamodb.Table("leave_balances")


def lambda_handler(event, context):

    employee_id = event["employee_id"]
    request_id = event["request_id"]
    decision = event["decision"]  # APPROVED or REJECTED

    # Fetch the leave request
    response = requests_table.get_item(
        Key={
            "employee_id": employee_id,
            "request_id": request_id
        }
    )

    if "Item" not in response:
        return respond(404, "Leave request not found")

    request = response["Item"]

    # Update request status
    requests_table.update_item(
        Key={
            "employee_id": employee_id,
            "request_id": request_id
        },
        UpdateExpression="SET #s = :status",
        ExpressionAttributeNames={
            "#s": "status"
        },
        ExpressionAttributeValues={
            ":status": decision
        }
    )

    # If approved, update leave balance
    if decision == "APPROVED":

        leave_type = request["leave_type"]
        num_days = int(request["num_days"])

        balance_key = f"{leave_type}#2026"

        balance = balances_table.get_item(
            Key={
                "employee_id": employee_id,
                "leave_type_year": balance_key
            }
        )

        if "Item" in balance:

            item = balance["Item"]

            remaining = int(item["remaining"])
            used = int(item["used"])

            balances_table.update_item(
                Key={
                    "employee_id": employee_id,
                    "leave_type_year": balance_key
                },
                UpdateExpression="""
                    SET remaining = :remaining,
                        used = :used
                """,
                ExpressionAttributeValues={
                    ":remaining": remaining - num_days,
                    ":used": used + num_days
                }
            )

    return respond(
        200,
        {
            "message": f"Leave request {decision.lower()} successfully."
        }
    )


def respond(status_code, body):

    return {
        "statusCode": status_code,
        "body": json.dumps(body)
    }