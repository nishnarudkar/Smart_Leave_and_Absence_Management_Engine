import json
import boto3
from datetime import datetime
from botocore.exceptions import ClientError


# AWS Resources
dynamodb = boto3.resource("dynamodb")
ses = boto3.client("ses", region_name="ap-south-1")


REQUESTS_TABLE = dynamodb.Table("leave_requests")
BALANCES_TABLE = dynamodb.Table("leave_balances")


SENDER_EMAIL = "divy220506@gmail.com"


def lambda_handler(event, context):

    try:

        # API Gateway body
        body = json.loads(event["body"])


        employee_id = body["employee_id"]
        request_id = body["request_id"]
        action = body["action"].upper()
        hr_comments = body.get("hr_comments", "")


        if action not in ["APPROVE", "REJECT"]:
            return response(
                400,
                "Action must be APPROVE or REJECT"
            )


        # Get request
        result = REQUESTS_TABLE.get_item(
            Key={
                "employee_id": employee_id,
                "request_id": request_id
            }
        )


        if "Item" not in result:

            return response(
                404,
                "Leave request not found"
            )


        leave_request = result["Item"]


        # Only HR pending requests allowed

        if leave_request["status"] != "PENDING_HR":

            return response(
                400,
                "Request is not waiting for HR approval"
            )


        new_status = (
            "APPROVED"
            if action == "APPROVE"
            else "REJECTED"
        )


        # Update status

        REQUESTS_TABLE.update_item(

            Key={
                "employee_id": employee_id,
                "request_id": request_id
            },

            UpdateExpression="""
            SET #s = :status,
            hr_comments = :comments,
            hr_processed_at = :time
            """,

            ExpressionAttributeNames={
                "#s": "status"
            },

            ExpressionAttributeValues={

                ":status": new_status,

                ":comments": hr_comments,

                ":time": datetime.utcnow().isoformat()

            }

        )


        # Deduct balance ONLY after HR approval

        if action == "APPROVE":


            leave_type = leave_request["leave_type"]

            days = int(
                leave_request["num_days"]
            )

            year = leave_request["start_date"][:4]


            balance_key = f"{leave_type}#{year}"


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



        # Send employee email

        employee_email = leave_request["employee_email"]


        subject = (
            f"HR Leave Decision - {new_status}"
        )


        message = f"""

Hello,

Your leave request has been {new_status} by HR.


Request ID:
{request_id}


Leave Type:
{leave_request['leave_type']}


From:
{leave_request['start_date']}


To:
{leave_request['end_date']}


Days:
{leave_request['num_days']}


HR Comments:
{hr_comments}


Regards,
Leave Management System

"""


        try:

            ses.send_email(

                Source=SENDER_EMAIL,

                Destination={

                    "ToAddresses":[

                        employee_email

                    ]

                },


                Message={

                    "Subject":{

                        "Data":subject

                    },

                    "Body":{

                        "Text":{

                            "Data":message

                        }

                    }

                }

            )


        except ClientError as e:

            print(
                "SES ERROR:",
                e
            )



        return response(

            200,

            {

                "message":
                f"Leave {new_status.lower()} by HR",

                "status":
                new_status

            }

        )


    except Exception as e:


        print(e)


        return response(

            500,

            {

                "message":
                "Internal Server Error",

                "error":
                str(e)

            }

        )




def response(status_code, message):

    return {

        "statusCode": status_code,

        "headers":{

            "Access-Control-Allow-Origin":"*",

            "Content-Type":"application/json"

        },


        "body":json.dumps(

            {

                "message":message

            }

        )

    }