import json
import hmac
import hashlib
import boto3
import base64

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
    github_signature = event['headers'].get('x-hub-signature-256', '')
    
    if not github_signature:
        return {"statusCode": 403, "body": "Signature missing"}
    signature = github_signature.split('=')[1]

    # 获取原始请求体字节（关键修正）
    body_str = event.get('body', '')
    if event.get('isBase64Encoded', False):
        payload = base64.b64decode(body_str)   # 解码得到原始字节
    else:
        payload = body_str.encode('utf-8')     # 非编码情况按 UTF-8 编码

    # 打印前 50 字节十六进制供调试（可选）
    print(f"Payload hex (first 50): {payload.hex()[:100]}")

    SECRET = get_secret()
    mac = hmac.new(SECRET.encode('utf-8'), msg=payload, digestmod=hashlib.sha256)
    local_signature = mac.hexdigest()

    if not hmac.compare_digest(local_signature, signature):
        print("local_signature", local_signature)
        print("signature", signature)
        return {"statusCode": 403, "body": "Invalid signature==Ed"}

    print("Received event:", json.dumps(event, indent=2))

    return {"statusCode": 200, "body": "Webhook received"}