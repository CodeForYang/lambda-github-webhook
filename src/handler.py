import json
import hmac
import hashlib
import boto3

def get_secret():
    secret_name = "webhook_secret"
    region_name = "ap-northeast-1"
    session = boto3.session.Session()
    client = session.client(service_name='secretsmanager', region_name=region_name)
    get_secret_value_response = client.get_secret_value(SecretId=secret_name)
    secret_json = json.loads(get_secret_value_response['SecretString'])
    secret = secret_json['github_webhook_release_push_secret']
    print (f"Secret: {secret}")
    return secret




def lambda_handler(event, context):
    # request verification
    github_signature = event['headers'].get('x-hub-signature-256', '')
    if not github_signature:
        return {"statusCode": 403, "body": "Signature missing"}
    # 提取签名摘要部分
    signature = github_signature.split('=')[1]
    # 获取请求体并计算本地签名
    payload = event['body'].encode('utf-8')

    SECRET = get_secret()
    mac = hmac.new(SECRET.encode('utf-8'), msg=payload, digestmod=hashlib.sha256)
    local_signature = mac.hexdigest()

    # 验证签名是否匹配
    if not hmac.compare_digest(local_signature, signature):
        return {"statusCode": 403, "body": "Invalid signature"}

    print("Received event:", json.dumps(event, indent=2))

    return {"StatusCode": 200, "body": "Webhook received"}

