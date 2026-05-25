# 本地测试指南

## 快速开始

### 1️⃣ 生成测试事件
```bash
python3 scripts/generate_webhook_event.py
```

这会生成一个包含正确签名的 `events/event.json` 文件。

### 2️⃣ 本地运行 Lambda
```bash
make local
```

Serverless Framework 会在本地模拟 Lambda 环境并执行你的 handler。

## 🔑 配置密钥

### 环境变量方式（推荐用于本地测试）
编辑 `scripts/generate_webhook_event.py` 中的密钥：
```python
webhook_secret = "test_secret_key"  # 改为你的测试密钥
```

### AWS Secrets Manager 方式（生产环境）
1. 在 AWS 创建 secret：
```bash
aws secretsmanager create-secret \
  --name webhook_secret \
  --secret-string '{"github_webhook_release_push_secret":"your_real_secret"}'
```

2. 本地测试时需要 AWS 凭证配置

## 📝 自定义事件

### 示例：生成 Pull Request 事件
```python
from scripts.generate_webhook_event import generate_webhook_event
import json

payload = {
    "action": "opened",
    "pull_request": {
        "id": 1,
        "number": 1,
        "title": "Test PR",
        "body": "Test PR description"
    },
    "repository": {
        "full_name": "owner/repo",
        "name": "repo"
    }
}

event, sig = generate_webhook_event(payload, "test_secret", "pull_request")
print(json.dumps(event, indent=2))
```

## 🧪 验证测试

运行完 `make local` 后，查看输出：
- ✅ `"statusCode": 200` = 签名验证成功
- ❌ `"statusCode": 403` = 签名验证失败（检查密钥是否匹配）

## 🐛 调试技巧

查看 handler 输出：
```bash
make local 2>&1 | grep -A 5 "Payload hex"
```

这会显示原始 payload 的前 50 字节（十六进制），用于调试签名问题。

## ✨ 下一步

- [ ] 调整 `create_push_payload()` 参数匹配你的场景
- [ ] 本地验证 handler 逻辑
- [ ] 部署到 AWS：`make deploy`
- [ ] 在 GitHub 设置真实 Webhook（使用你的 Lambda URL）
