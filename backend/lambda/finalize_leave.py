import boto3, json
from datetime import datetime
from decimal import Decimal

dynamodb = boto3.resource('dynamodb')
ses = boto3.client('ses', region_name='ap-south-1')
SENDER = 'your-verified-email@gmail.com'

def lambda_handler(event, context):
    # event comes from Step Functions
    payload = event.get('Payload', event)
    request_id  = payload['request_id']
    action      = payload['action']       # 'APPROVE' or 'REJECT'
    employee_id = payload['employee_id']

    req_table = dynamodb.Table('leave_requests')

    # Fetch the original request
    resp = req_table.query(
        KeyConditionExpression='employee_id = :eid AND request_id = :rid',
        ExpressionAttributeValues={':eid': employee_id, ':rid': request_id}
    )
    if not resp['Items']:
        return {'statusCode': 404, 'body': 'Request not found'}
    request = resp['Items'][0]

    new_status = 'APPROVED' if action == 'APPROVE' else 'REJECTED'

    # Update request status
    req_table.update_item(
        Key={'employee_id': employee_id, 'request_id': request_id},
        UpdateExpression='SET #s = :s, finalized_at = :t',
        ExpressionAttributeNames={'#s': 'status'},
        ExpressionAttributeValues={
            ':s': new_status,
            ':t': datetime.now().isoformat()
        }
    )

    # Decrement balance ONLY on APPROVE
    if action == 'APPROVE':
        year = request['start_date'][:4]
        bal_key = f"{request['leave_type']}_{year}"
        dynamodb.Table('leave_balances').update_item(
            Key={'employee_id': employee_id, 'leave_type_year': bal_key},
            UpdateExpression='SET used_days = used_days + :d, remaining_days = remaining_days - :d',
            ConditionExpression='remaining_days >= :d',
            ExpressionAttributeValues={':d': Decimal(str(request['num_days']))}
        )

    # Email employee with final decision
    subject = f"Leave {new_status.lower()} — {request['leave_type']} {request['start_date']} to {request['end_date']}"
    body = (f"Your {request['leave_type']} leave request from {request['start_date']} "
            f"to {request['end_date']} has been {new_status.lower()}.")
    ses.send_email(
        Source=SENDER,
        Destination={'ToAddresses': [request['employee_email']]},
        Message={'Subject':{'Data':subject},'Body':{'Text':{'Data':body}}}
    )
    return {'statusCode': 200, 'body': new_status}
