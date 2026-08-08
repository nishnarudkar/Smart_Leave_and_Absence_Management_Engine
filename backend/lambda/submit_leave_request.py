import boto3
import uuid
import json
from datetime import datetime
from boto3.dynamodb.conditions import Key, Attr


# AWS Clients
dynamodb = boto3.resource("dynamodb")
sfn = boto3.client("stepfunctions")
ses = boto3.client("ses", region_name="ap-south-1")


# Step Functions ARN
STATE_MACHINE_ARN = "arn:aws:states:ap-south-1:020426223468:stateMachine:LeaveApprovalWorkflow"


# Verified SES Email
SENDER_EMAIL = "divy220506@gmail.com"



def lambda_handler(event, context):

    # Works for BOTH Lambda Test Event and API Gateway
    if "body" in event:
        body = json.loads(event["body"])
    else:
        body = event


    employee_id = body["employee_id"]
    leave_type = body["leave_type"]
    start_date = body["start_date"]
    end_date = body["end_date"]
    num_days = int(body["num_days"])
    employee_email = body.get("employee_email", "")
    manager_id = body["manager_id"]
    reason = body.get("reason", "")



    # ----------------------------------------------------
    # 1. Fetch Leave Configuration
    # ----------------------------------------------------

    config_table = dynamodb.Table("leave_config")

    config = config_table.get_item(
        Key={
            "leave_type": leave_type
        }
    ).get("Item")


    if not config:
        return respond(
            400,
            f"Invalid leave type: {leave_type}"
        )



    # ----------------------------------------------------
    # 2. Check Leave Balance
    # ----------------------------------------------------

    balance_table = dynamodb.Table("leave_balances")

    year = "2026"

    balance_key = f"{leave_type}#{year}"


    balance_response = balance_table.get_item(
        Key={
            "employee_id": employee_id,
            "leave_type_year": balance_key
        }
    )


    if "Item" not in balance_response:
        return respond(
            400,
            f"No leave balance found for {leave_type}"
        )


    balance = balance_response["Item"]

    remaining = int(balance["remaining"])



    if remaining < num_days:

        write_rejected(
            employee_id,
            leave_type,
            start_date,
            end_date,
            num_days,
            manager_id,
            f"Insufficient balance ({remaining} remaining)"
        )


        return respond(
            400,
            f"Insufficient leave balance. Remaining: {remaining}"
        )



    # ----------------------------------------------------
    # 3. Check Date Overlap
    # ----------------------------------------------------

    overlap, message = check_overlaps(
        employee_id,
        start_date,
        end_date
    )


    if overlap:

        write_rejected(
            employee_id,
            leave_type,
            start_date,
            end_date,
            num_days,
            manager_id,
            message
        )


        return respond(
            400,
            message
        )



    # ----------------------------------------------------
    # 4. Store Leave Request
    # ----------------------------------------------------

    request_id = f"REQ-{uuid.uuid4().hex[:8].upper()}"


    request_table = dynamodb.Table(
        "leave_requests"
    )


    request_table.put_item(
        Item={
            "employee_id": employee_id,
            "request_id": request_id,
            "leave_type": leave_type,
            "start_date": start_date,
            "end_date": end_date,
            "num_days": num_days,
            "status": "PENDING",
            "reason": reason,
            "manager_id": manager_id,
            "employee_email": employee_email,
            "submitted_at": datetime.now().isoformat()
        }
    )



    # ----------------------------------------------------
    # 5. Start Step Functions Workflow
    # ----------------------------------------------------

    # try:

    #     print("Starting Step Function")

    #     sfn.start_execution(
        #     stateMachineArn=STATE_MACHINE_ARN,
        #     name=request_id,
        #     input=json.dumps(
        #         {
        #             "employee_id": employee_id,
        #             "request_id": request_id,
        #             "decision": "APPROVED",
        #             "num_days": num_days
        #         }
        #     )
        # )


    #     print("Step Function Started")


    # except Exception as e:

    #     print(
    #         "STEP FUNCTION ERROR:",
    #         str(e)
    #     )
    # ----------------------------------------------------
    # 6. Send Email using Amazon SES
    # ----------------------------------------------------
    try:
        print(f"Sending email to: {employee_email}")

        response = ses.send_email(
            Source=SENDER_EMAIL,
            Destination={
                "ToAddresses": [
                    employee_email
                ]
            },
            Message={
                "Subject": {
                    "Data": f"Leave Request Submitted ({request_id})"
                },
                "Body": {
                    "Text": {
                        "Data": (
                            f"Hello,\n\n"
                            f"Your leave request has been submitted successfully.\n\n"
                            f"Request ID: {request_id}\n"
                            f"Employee ID: {employee_id}\n"
                            f"Leave Type: {leave_type}\n"
                            f"Start Date: {start_date}\n"
                            f"End Date: {end_date}\n"
                            f"Number of Days: {num_days}\n"
                            f"Reason: {reason}\n"
                            f"Status: PENDING\n\n"
                            f"Your request has been forwarded for manager approval.\n\n"
                            f"Thank you,\n"
                            f"Leave Management System"
                        )
                    }
                }
            }
        )

        print("SES Response:", response)

    except Exception as e:
        print("SES ERROR:", str(e))


    return respond(
        200,
        {
            "request_id": request_id,
            "status": "PENDING",
            "message": "Leave request submitted successfully."
        }
    )



def check_overlaps(employee_id, start_date, end_date):

    table = dynamodb.Table("leave_requests")

    response = table.query(
        KeyConditionExpression=Key("employee_id").eq(employee_id),
        FilterExpression=Attr("status").is_in(
            [
                "APPROVED",
                "PENDING",
                "PENDING_HR"
            ]
        )
    )


    start = datetime.strptime(
        start_date,
        "%Y-%m-%d"
    )

    end = datetime.strptime(
        end_date,
        "%Y-%m-%d"
    )


    for item in response.get("Items", []):

        existing_start = datetime.strptime(
            item["start_date"],
            "%Y-%m-%d"
        )

        existing_end = datetime.strptime(
            item["end_date"],
            "%Y-%m-%d"
        )


        if start <= existing_end and end >= existing_start:

            return (
                True,
                f"Leave overlaps with existing {item['status']} request."
            )


    return False, None
    
def write_rejected(
    employee_id,
    leave_type,
    start_date,
    end_date,
    num_days,
    manager_id,
    reason
):

    table = dynamodb.Table("leave_requests")

    table.put_item(
        Item={
            "employee_id": employee_id,
            "request_id": f"REJ-{uuid.uuid4().hex[:8].upper()}",
            "leave_type": leave_type,
            "start_date": start_date,
            "end_date": end_date,
            "num_days": num_days,
            "status": "REJECTED",
            "rejection_reason": reason,
            "manager_id": manager_id,
            "submitted_at": datetime.now().isoformat()
        }
    )



def respond(status_code, body):

    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
        },
        "body": json.dumps(body)
    }