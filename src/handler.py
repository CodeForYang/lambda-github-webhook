import json
import hmac
import hashlib
import boto3
import base64
import urllib.request
import urllib.error

# ========== 初始化 AWS 客户端 ==========
secretsmanager = boto3.client("secretsmanager")
ssm = boto3.client("ssm")


# ========== 从 Secrets Manager 获取 GitHub Webhook Secret ==========
def get_github_secret():
    secret_name = "webhook_secret"
    region_name = "ap-northeast-1"
    try:
        get_secret_value_response = secretsmanager.get_secret_value(SecretId=secret_name)
        secret_json = json.loads(get_secret_value_response['SecretString'])
        secret = secret_json['github_webhook_release_push_secret']
        print(f"GitHub Secret loaded")
        return secret
    except Exception as e:
        print(f"获取 GitHub Secret 失败: {e}")
        raise


# ========== 从 SSM Parameter Store 获取 Jenkins 凭证 ==========
def get_ssm_parameter(name, decrypt=True):
    """从 SSM Parameter Store 获取参数值"""
    resp = ssm.get_parameter(Name=name, WithDecryption=decrypt)
    return resp["Parameter"]["Value"]


def get_jenkins_crumb(jenkins_url, username, api_token):
    """获取 Jenkins CSRF Crumb"""
    url = f"{jenkins_url}/crumbIssuer/api/json"
    req = urllib.request.Request(url)

    credentials = f"{username}:{api_token}"
    encoded = base64.b64encode(credentials.encode()).decode()
    req.add_header("Authorization", f"Basic {encoded}")

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            print("成功获取 Jenkins Crumb")
            return data
    except urllib.error.HTTPError as e:
        print(f"获取 crumb 失败: {e.code} {e.reason}")
        raise


def trigger_jenkins_build(jenkins_url, username, api_token, job_name, job_token, params=None):
    """触发 Jenkins Job 构建"""
    crumb_data = get_jenkins_crumb(jenkins_url, username, api_token)

    # 构建 URL
    if params:
        param_str = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{jenkins_url}/job/{job_name}/buildWithParameters?token={job_token}&{param_str}"
    else:
        url = f"{jenkins_url}/job/{job_name}/build?token={job_token}"

    req = urllib.request.Request(url, data=b"", method="POST")

    credentials = f"{username}:{api_token}"
    encoded = base64.b64encode(credentials.encode()).decode()
    req.add_header("Authorization", f"Basic {encoded}")
    req.add_header(crumb_data["crumbRequestField"], crumb_data["crumb"])

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            print(f"Jenkins 构建触发成功, HTTP {resp.status}")
            return {
                "statusCode": resp.status,
                "queueLocation": resp.headers.get("Location", ""),
            }
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else ""
        print(f"触发构建失败: {e.code} - {error_body}")
        raise


# ========== 验证 GitHub Webhook 签名 ==========
def verify_github_signature(event, payload_bytes):
    """验证 GitHub webhook 签名"""
    github_signature = event.get('headers', {}).get('x-hub-signature-256', '')

    if not github_signature:
        print("签名缺失")
        return False

    signature = github_signature.split('=')[1]
    SECRET = get_github_secret()

    mac = hmac.new(SECRET.encode('utf-8'), msg=payload_bytes, digestmod=hashlib.sha256)
    local_signature = mac.hexdigest()

    if not hmac.compare_digest(local_signature, signature):
        print(f"签名验证失败")
        print(f"本地签名: {local_signature}")
        print(f"GitHub签名: {signature}")
        return False

    print("GitHub Webhook 签名验证成功")
    return True


# ========== Lambda 入口 ==========
def lambda_handler(event, context):
    print(f"收到事件: {json.dumps(event)}")

    # ===== 1. 处理请求体（支持 Base64 解码） =====
    body_str = event.get('body', '')
    if event.get('isBase64Encoded', False):
        payload_bytes = base64.b64decode(body_str)
    else:
        payload_bytes = body_str.encode('utf-8') if isinstance(body_str, str) else body_str

    print(f"Payload 长度: {len(payload_bytes)} 字节")

    # ===== 2. 验证 GitHub Webhook 签名 =====
    if not verify_github_signature(event, payload_bytes):
        return {"statusCode": 403, "body": json.dumps({"error": "Invalid signature"})}

    # ===== 3. 解析 GitHub Webhook 数据 =====
    try:
        webhook_data = json.loads(payload_bytes.decode('utf-8'))
        print(f"Webhook 类型: {webhook_data.get('action', 'unknown')}")
    except Exception as e:
        print(f"解析 Webhook 数据失败: {e}")
        webhook_data = {}

    # ===== 4. 从 SSM 获取 Jenkins 配置 =====
    try:
        jenkins_url = get_ssm_parameter("/jenkins/url", decrypt=False)
        username = get_ssm_parameter("/jenkins/username", decrypt=False)
        api_token = get_ssm_parameter("/jenkins/api-token", decrypt=True)
        job_token = get_ssm_parameter("/jenkins/job-token", decrypt=True)
        print("成功从 SSM 获取 Jenkins 配置")
    except Exception as e:
        print(f"读取 SSM 参数失败: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": f"SSM 读取失败: {str(e)}"})
        }

    # ===== 5. 构建传递给 Jenkins 的参数（从 GitHub webhook 提取信息） =====
    # 根据 webhook 事件类型提取分支和提交信息
    params = {
        "TRIGGERED_BY": "GitHub-Webhook",
        "GITHUB_EVENT": event.get('headers', {}).get('x-github-event', 'unknown'),
    }

    # 从 push 事件中提取信息
    if 'ref' in webhook_data:
        branch = webhook_data['ref'].replace('refs/heads/', '')
        params["GIT_BRANCH"] = branch

    if 'after' in webhook_data:
        params["GIT_COMMIT"] = webhook_data['after'][:7]  # 短 commit SHA

    if 'head_commit' in webhook_data and 'message' in webhook_data['head_commit']:
        params["GIT_MESSAGE"] = webhook_data['head_commit']['message'][:100]

    if 'repository' in webhook_data and 'name' in webhook_data['repository']:
        params["REPO_NAME"] = webhook_data['repository']['name']

    print(f"传递给 Jenkins 的参数: {params}")

    # ===== 6. 触发 Jenkins 构建 =====
    try:
        result = trigger_jenkins_build(
            jenkins_url=jenkins_url,
            username=username,
            api_token=api_token,
            job_name="demo-build",  # 可改为从环境变量或 webhook 配置读取
            job_token=job_token,
            params=params,
        )

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "message": "Jenkins 构建已触发",
                "queueUrl": result["queueLocation"],
                "jenkins_job": "demo-build"
            }),
        }
    except Exception as e:
        print(f"触发 Jenkins 失败: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": f"Jenkins 触发失败: {str(e)}"})
        }