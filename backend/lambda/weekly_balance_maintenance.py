import boto3
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource("dynamodb")
ses = boto3.client("ses", region_name="ap-south-1")

# Verified SES sender email
SENDER = "divy220506@gmail.com"


def lambda_handler(event, context):

    bal_table = dynamodb.Table("leave_balances")
    req_table = dynamodb.Table("leave_requests")

    # Read all leave balances
    response = bal_table.scan()
    items = response.get("Items", [])

    # Group by employee
    employees = {}

    for item in items:
        emp_id = item["employee_id"]

        if emp_id not in employees:
            employees[emp_id] = []

        employees[emp_id].append(item)

    employees_notified = 0

    # Process each employee
    for emp_id, balances in employees.items():

        # ----------------------------
        # Plain text version
        # ----------------------------
        text_body = (
            "Dear Employee,\n\n"
            "Please find your weekly leave balance summary below.\n\n"
        )

        # ----------------------------
        # HTML version
        # ----------------------------
        html_body = f"""
        <html>
        <body style="font-family: Arial, Helvetica, sans-serif; background:#f4f4f4; padding:30px;">

        <div style="max-width:700px; margin:auto; background:white;
                    border-radius:10px; padding:25px;
                    box-shadow:0px 0px 8px rgba(0,0,0,0.1);">

            <h2 style="color:#1E88E5;">
                Weekly Leave Balance Summary
            </h2>

            <p>Hello,</p>

            <p>Your current leave balances are shown below.</p>

            <p><strong>Employee ID:</strong> {emp_id}</p>

            <table style="width:100%; border-collapse:collapse;" border="1">

                <tr style="background:#1E88E5; color:white;">
                    <th style="padding:10px;">Leave Type</th>
                    <th>Total</th>
                    <th>Used</th>
                    <th>Remaining</th>
                </tr>
        """

        # Build table rows
        for b in balances:

            leave_type = b["leave_type_year"].split("#")[0]

            html_body += f"""
            <tr>
                <td style="padding:8px;">{leave_type}</td>
                <td align="center">{b['total']}</td>
                <td align="center">{b['used']}</td>
                <td align="center">{b['remaining']}</td>
            </tr>
            """

            text_body += (
                f"{leave_type}\n"
                f"Total      : {b['total']}\n"
                f"Used       : {b['used']}\n"
                f"Remaining  : {b['remaining']}\n\n"
            )

        html_body += """
            </table>

            <br>

            <p>
                This is an automated weekly notification from the
                <strong>Leave Management System</strong>.
            </p>

            <p>
                If you have any questions regarding your leave balance,
                please contact the HR department.
            </p>

            <br>

            <p>
                Regards,<br>
                <strong>Leave Management System</strong>
            </p>

        </div>

        </body>
        </html>
        """

        # Fetch employee email from leave_requests
        employee_email = None

        response = req_table.query(
            KeyConditionExpression=Key("employee_id").eq(emp_id),
            ScanIndexForward=False,
            Limit=1
        )

        if response["Items"]:
            employee_email = response["Items"][0].get("employee_email")

        # Send email
        if employee_email:

            ses.send_email(
                Source=SENDER,
                Destination={
                    "ToAddresses": [employee_email]
                },
                Message={
                    "Subject": {
                        "Data": "Weekly Leave Balance Summary"
                    },
                    "Body": {
                        "Text": {
                            "Data": text_body
                        },
                        "Html": {
                            "Data": html_body
                        }
                    }
                }
            )

            employees_notified += 1

    return {
        "statusCode": 200,
        "employees_found": len(employees),
        "employees_notified": employees_notified
    }