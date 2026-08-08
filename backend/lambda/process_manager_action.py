import json
import boto3
from datetime import datetime
from botocore.exceptions import ClientError

# AWS Resources
dynamodb = boto3.resource("dynamodb")
ses = boto3.client("ses", region_name="ap-south-1")
sfn = boto3.client("stepfunctions")

REQUESTS_TABLE = dynamodb.Table("leave_requests")
BALANCES_TABLE = dynamodb.Table("leave_balances")

SENDER_EMAIL = "divy220506@gmail.com"
STATE_MACHINE_ARN = "arn:aws:states:ap-south-1:020426223468:stateMachine:LeaveApprovalWorkflow"


def lambda_handler(event, context):
    try:
        # Read request body
        body = json.loads(event["body"])

        employee_id = body["employee_id"]
        request_id = body["request_id"]
        action = body["action"].upper()
        manager_comments = body.get("manager_comments", "")

        # Validate action
        if action not in ["APPROVE", "REJECT"]:
            return {
                "statusCode": 400,
                "body": json.dumps({
                    "message": "Action must be APPROVE or REJECT"
                })
            }

        # Get leave request
        response = REQUESTS_TABLE.get_item(
            Key={
                "employee_id": employee_id,
                "request_id": request_id
            }
        )

        if "Item" not in response:
            return {
                "statusCode": 404,
                "body": json.dumps({
                    "message": "Leave request not found"
                })
            }


        leave_request = response["Item"]

        # Already processed?
        if leave_request["status"] != "PENDING":
            return {
                "statusCode": 400,
                "body": json.dumps({
                    "message": "This leave request has already been processed."
                })
            }


        days = int(leave_request["num_days"])

        # If leave is more than 5 days, send to HR
        if action == "APPROVE" and days > 5:

            REQUESTS_TABLE.update_item(
                Key={
                    "employee_id": employee_id,
                    "request_id": request_id
                },
                UpdateExpression="SET #s = :status",
                ExpressionAttributeNames={
                    "#s": "status"
                },
                ExpressionAttributeValues={
                    ":status": "PENDING_HR"
                }
            )

            sfn.start_execution(
                stateMachineArn=STATE_MACHINE_ARN,
                name=request_id,
                input=json.dumps({
                    "employee_id": employee_id,
                    "request_id": request_id,
                    "num_days": days
                })
            )

            return {
                "statusCode": 200,
                "body": json.dumps({
                    "message": "Leave sent to HR approval.",
                    "status": "PENDING_HR"
                })
            }


        new_status = "APPROVED" if action == "APPROVE" else "REJECTED"

        # Update leave request
        REQUESTS_TABLE.update_item(
            Key={
                "employee_id": employee_id,
                "request_id": request_id
            },
            UpdateExpression="""
                SET #s = :status,
                    manager_comments = :comments,
                    approved_at = :time
            """,
            ExpressionAttributeNames={
                "#s": "status"
            },
            ExpressionAttributeValues={
                ":status": new_status,
                ":comments": manager_comments,
                ":time": datetime.utcnow().isoformat()
            }
        )

        # Deduct leave balance only when approved
        if action == "APPROVE":

            leave_type = leave_request["leave_type"]
            year = leave_request["start_date"][:4]
            balance_key = f"{leave_type}#{year}"
            days = int(leave_request["num_days"])

            BALANCES_TABLE.update_item(
                Key={
                    "employee_id": employee_id,
                    "leave_type_year": balance_key
                },
                UpdateExpression="""
                    SET remaining = remaining - :days,
                        used = used + :days
                """,
                ExpressionAttributeValues={
                    ":days": days
                }
            )

        # Send Email
        employee_email = leave_request["employee_email"]

        subject = f"Leave Request {new_status}"

        body_text = f"""
Hello,

Your leave request has been {new_status}.

Request ID: {request_id}
Leave Type: {leave_request['leave_type']}
From: {leave_request['start_date']}
To: {leave_request['end_date']}
Days: {leave_request['num_days']}

Manager Comments:
{manager_comments}

Status:
{new_status}

Regards,
Leave Management System
"""

        try:
            ses.send_email(
                Source=SENDER_EMAIL,
                Destination={
                    "ToAddresses": [
                        employee_email
                    ]
                },
                Message={
                    "Subject": {
                        "Data": subject
                    },
                    "Body": {
                        "Text": {
                            "Data": body_text
                        }
                    }
                }
            )
        except ClientError as e:
            print("SES Error:", e)

        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": f"Leave request {new_status.lower()} successfully.",
                "request_id": request_id,
                "status": new_status
            })
        }

    except Exception as e:
        print(e)

        return {
            "statusCode": 500,
            "body": json.dumps({
                "message": "Internal Server Error",
                "error": str(e)
            })
        }