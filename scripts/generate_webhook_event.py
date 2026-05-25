#!/usr/bin/env python3
"""
生成真实格式的 GitHub Webhook 事件用于本地测试
"""
import json
import hmac
import hashlib
from datetime import datetime
import uuid

def generate_webhook_event(payload, secret="your_webhook_secret", event_type="push"):
    """
    生成包含正确签名的 Webhook 事件
    
    Args:
        payload (dict): GitHub Webhook payload
        secret (str): Webhook 密钥
        event_type (str): GitHub 事件类型 (push, pull_request, issues 等)
    
    Returns:
        dict: 完整的 API Gateway Lambda 事件
    """
    # 将 payload 转为 JSON 字符串（必须与签名计算时相同）
    body_str = json.dumps(payload, separators=(',', ':'), ensure_ascii=False)
    
    # 计算 HMAC SHA256 签名
    signature = hmac.new(
        secret.encode('utf-8'),
        body_str.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    # 创建完整的 Lambda 事件
    event = {
        "version": "2.0",
        "routeKey": "POST /webhook",
        "rawPath": "/webhook",
        "rawQueryString": "",
        "headers": {
            "accept": "*/*",
            "content-type": "application/json",
            "host": "xxx.execute-api.ap-northeast-1.amazonaws.com",
            "user-agent": "GitHub-Hookshot/12345678",
            "x-github-delivery": str(uuid.uuid4()),
            "x-github-event": event_type,
            "x-github-hook-id": "123456789",
            "x-github-hook-installation-target-id": "123456789",
            "x-github-hook-installation-target-type": "repository",
            "x-hub-signature": f"sha1={hmac.new(secret.encode('utf-8'), body_str.encode('utf-8'), hashlib.sha1).hexdigest()}",
            "x-hub-signature-256": f"sha256={signature}",
            "x-forwarded-for": "140.82.115.55",
            "x-forwarded-port": "443",
            "x-forwarded-proto": "https"
        },
        "requestContext": {
            "http": {
                "method": "POST",
                "path": "/webhook",
                "protocol": "HTTP/1.1",
                "sourceIp": "140.82.115.55",
                "userAgent": "GitHub-Hookshot/12345678"
            },
            "stage": "$default"
        },
        "body": body_str,  # 必须是字符串
        "isBase64Encoded": False
    }
    
    return event, signature


def create_push_payload(repo="your-org/your-repo", branch="main", commit_id="abc123"):
    """创建一个 GitHub push 事件 payload"""
    return {
        "ref": f"refs/heads/{branch}",
        "before": "0000000000000000000000000000000000000000",
        "after": commit_id,
        "repository": {
            "id": 123456789,
            "name": repo.split('/')[-1],
            "full_name": repo,
            "private": False,
            "owner": {
                "name": repo.split('/')[0],
                "email": "user@example.com"
            }
        },
        "pusher": {
            "name": "github-user",
            "email": "user@example.com"
        },
        "sender": {
            "login": "github-user",
            "id": 123456789
        },
        "created": False,
        "deleted": False,
        "forced": False,
        "compare": f"https://github.com/{repo}/compare/0000000000000000000000000000000000000000...{commit_id}",
        "commits": [
            {
                "id": commit_id,
                "tree_id": "tree123",
                "distinct": True,
                "message": "Test commit",
                "timestamp": datetime.now().isoformat(),
                "url": f"https://github.com/{repo}/commit/{commit_id}",
                "author": {
                    "name": "Test User",
                    "email": "user@example.com",
                    "username": "testuser"
                },
                "committer": {
                    "name": "Test User",
                    "email": "user@example.com",
                    "username": "testuser"
                },
                "added": ["file.txt"],
                "removed": [],
                "modified": []
            }
        ],
        "head_commit": {
            "id": commit_id,
            "tree_id": "tree123",
            "message": "Test commit",
            "timestamp": datetime.now().isoformat(),
            "author": {
                "name": "Test User",
                "email": "user@example.com",
                "username": "testuser"
            }
        }
    }


if __name__ == "__main__":
    # 示例：生成一个 push 事件
    # 使用 AWS Secrets Manager 中的密钥
    webhook_secret = "13265139960"  # 替换为你的密钥
    
    payload = create_push_payload(
        repo="CodeForYang/lambda-github-webhook",
        branch="main",
        commit_id="abc123def456"
    )
    
    event, signature = generate_webhook_event(payload, webhook_secret, event_type="push")
    
    # 保存为 event.json
    with open("events/event.json", "w") as f:
        json.dump(event, f, indent=2)
    
    print("✅ 已生成事件文件: events/event.json")
    print(f"🔐 签名: {signature}")
    print(f"🔑 使用的密钥: {webhook_secret}")
    print(f"\n📝 现在可以运行: make local")
