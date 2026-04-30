# Server端 - 应急响应分析系统

## 功能说明

Server端是应急响应分析系统的核心，负责：
1. 接收Client端发送的系统检查数据
2. 调用AI模型进行安全分析
3. 将分析结果返回给Client
4. 将数据上传至对象存储
5. 提供AI模型管理功能

## 文件说明

| 文件 | 说明 |
|------|------|
| `server.py` | Server端主程序（Flask API） |
| `ai_manager.py` | AI模型管理命令行工具 |
| `config.json` | 配置文件 |
| `aescode.py` | AES加密模块 |

## 环境要求

- Python 3.6+
- 依赖包：
  - flask
  - boto3
  - pycryptodome
  - requests

## 安装依赖

```bash
pip install flask boto3 pycryptodome requests
```

## 配置说明

配置文件 `config.json` 包含以下配置：

### Server配置
```json
{
  "server": {
    "port": 8080,
    "host": "0.0.0.0"
  }
}
```

### AI模型配置
```json
{
  "ai_models": {
    "default": "deepseek-flash",
    "models": {
      "deepseek": {
        "name": "DeepSeek",
        "api_url": "https://api.deepseek.com/chat/completions",
        "api_key": "sk-xxx",
        "model_name": "deepseek-chat",
        "temperature": 0.1,
        "max_tokens": 4096,
        "enabled": true
      }
    }
  }
}
```

### 对象存储配置
```json
{
  "object_storage": {
    "endpoint": "YOUR_S3_ENDPOINT",
    "access_key": "YOUR_ACCESS_KEY",
    "secret_key_encrypted": "YOUR_ENCRYPTED_SECRET_KEY",
    "bucket": "YOUR_BUCKET_NAME",
    "prefix": "results/"
  }
}
```

## 启动Server

```bash
python3 server.py
```

Server启动后会显示：
```
╔══════════════════════════════════════════════════════════════╗
║           应急响应分析系统 - Server端 (模块化AI版)            ║
╠══════════════════════════════════════════════════════════════╣
║  监听地址: 0.0.0.0:8080                                      ║
║  默认模型: deepseek                                          ║
╚══════════════════════════════════════════════════════════════╝
```

## API接口

### 健康检查
```bash
GET /health
```

响应示例：
```json
{
  "status": "ok",
  "timestamp": "2024-01-01T12:00:00",
  "default_model": "deepseek-flash",
  "enabled_models": ["deepseek"]
}
```

### 查看模型列表
```bash
GET /models
```

响应示例：
```json
{
  "default": "deepseek",
  "models": {
    "deepseek": {
      "name": "DeepSeek",
      "enabled": true,
      "model_name": "deepseek-chat",
      "has_api_key": true
    }
  },
  "note": "模型管理请使用 ai_manager.py 命令行工具"
}
```

### 分析数据
```bash
POST /analyze
Content-Type: application/json

{
  "ticket_id": "T001",
  "hostname": "web-server",
  "ip_info": "192.168.1.100",
  "log_content": "日志内容...",
  "model": "deepseek"  // 可选，指定使用的AI模型
}
```

响应示例：
```json
{
  "success": true,
  "ticket_id": "T001",
  "hostname": "web-server",
  "model_used": "deepseek",
  "model_name": "DeepSeek",
  "analysis_report": "# AI 安全应急响应分析报告\n...",
  "log_uploaded": true,
  "log_filename": "T001_web-server_log.md",
  "analysis_filename": "T001_web-server_analysis_report.md"
}
```

### 上传文件
```bash
POST /upload
Content-Type: application/json

{
  "filename": "test.md",
  "content": "文件内容"
}
```

## AI模型管理

使用 `ai_manager.py` 命令行工具管理AI模型：

### 查看所有模型
```bash
python ai_manager.py list
```

输出示例：
```
============================================================
AI模型列表
============================================================
默认模型: deepseek
------------------------------------------------------------

[deepseek] [默认]
  名称: DeepSeek
  模型: deepseek-chat
  API地址: https://api.deepseek.com/chat/completions
  API密钥: 已配置
  状态: ✅ 已启用

[openai]
  名称: OpenAI GPT-4
  模型: gpt-4
  API地址: https://api.openai.com/v1/chat/completions
  API密钥: 未配置
  状态: ❌ 未启用

============================================================
```

### 查看模型详情
```bash
python ai_manager.py show openai
```

### 启用模型
```bash
python ai_manager.py enable openai
```

### 禁用模型
```bash
python ai_manager.py disable openai
```

### 设置默认模型
```bash
python ai_manager.py set-default openai
```

### 设置API密钥
```bash
python ai_manager.py set-key openai sk-xxxxxxxxxx
```

### 更新模型配置
```bash
# 更新API地址
python ai_manager.py update openai api_url https://api.openai.com/v1/chat/completions

# 更新模型名称
python ai_manager.py update openai model_name gpt-4-turbo

# 更新temperature
python ai_manager.py update openai temperature 0.5
```

### 添加自定义模型
```bash
python ai_manager.py add mymodel "My Custom Model" https://api.example.com/v1/chat/completions gpt-4

# 配置密钥并启用
python ai_manager.py set-key mymodel my-api-key
python ai_manager.py enable mymodel
```

### 删除模型
```bash
python ai_manager.py delete mymodel
```

## 支持的AI模型

| 模型Key | 模型名称 | API接口 | 状态 |
|---------|----------|---------|------|
| `deepseek` | DeepSeek | api.deepseek.com | ✅ 默认启用 |
| `openai` | OpenAI GPT-4 | api.openai.com | ⚙️ 需配置密钥 |
| `claude` | Claude | api.anthropic.com | ⚙️ 需配置密钥 |
| `zhipu` | 智谱GLM-4 | open.bigmodel.cn | ⚙️ 需配置密钥 |
| `moonshot` | Moonshot (Kimi) | api.moonshot.cn | ⚙️ 需配置密钥 |
| `qwen` | 通义千问 | dashscope.aliyuncs.com | ⚙️ 需配置密钥 |
| `custom` | 自定义接口 | localhost:8000 | ⚙️ 需配置 |

所有模型均支持OPENAI兼容接口格式。

## 添加新模型

在 `config.json` 的 `ai_models.models` 中添加：

```json
{
  "new_model": {
    "name": "新模型名称",
    "api_url": "https://api.xxx.com/v1/chat/completions",
    "api_key": "",
    "model_name": "model-id",
    "temperature": 0.1,
    "max_tokens": 4096,
    "enabled": false
  }
}
```

要求：
- API接口兼容OPENAI格式
- 支持 `messages` 数组格式
- 返回 `choices[0].message.content` 格式

## 白名单配置

在 `config.json` 的 `analysis.whitelist_keywords` 中配置白名单关键词：

```json
{
  "analysis": {
    "enable_whitelist": true,
    "whitelist_keywords": [
      "system_check",
      "linux_check-AI.sh",
      "busybox",
      "vuln",
      "titan agent",
      "security-agent",
      "cloud-monitor",
      "hostguard"
    ]
  }
}
```

## 注意事项

1. **网络安全**
   - 生产环境建议使用HTTPS
   - 添加Client认证机制
   - 限制Server访问IP

2. **API密钥管理**
   - 使用 `ai_manager.py` 管理密钥
   - 定期轮换API密钥
   - 限制API密钥权限

3. **数据安全**
   - 敏感数据加密传输
   - 定期清理临时文件
   - 对象存储访问控制

4. **性能优化**
   - 根据需要调整 `max_tokens`
   - 使用连接池
   - 添加缓存机制

## 故障排查

### Server无法启动

```bash
# 检查依赖
pip list | grep flask

# 检查配置文件
python -c "import json; json.load(open('config.json'))"

# 检查端口占用
netstat -tlnp | grep 8080
```

### AI模型调用失败

```bash
# 检查模型状态
python ai_manager.py list
python ai_manager.py show openai

# 确保模型已启用且配置了API密钥
python ai_manager.py enable openai
python ai_manager.py set-key openai sk-xxx
```

### 对象存储上传失败

```bash
# 检查配置
cat config.json | grep object_storage

# 检查网络连接
curl -I http://eos.xxx

# 检查权限
# 确保access_key和secret_key正确
```

### Client无法连接

```bash
# 检查Server是否启动
curl http://localhost:8080/health

# 检查防火墙
iptables -L -n | grep 8080

# 检查Server日志
# 查看终端输出的错误信息
```

## 开发说明

### 代码结构

```
server.py
├── 配置加载              # load_config()
├── AI模型管理            # AIModelManager类
├── AI分析模块            # call_ai_api(), full_analysis()
├── 对象存储              # upload_to_s3()
├── API路由
│   ├── /health         # 健康检查
│   ├── /models         # 查看模型
│   ├── /analyze        # 分析数据
│   └── /upload         # 上传文件
└── 主程序              # if __name__ == '__main__'
```

### 添加新的API接口

在 `server.py` 中添加：

```python
@app.route('/new-endpoint', methods=['POST'])
def new_endpoint():
    try:
        data = request.get_json()
        # 处理逻辑
        return jsonify({"success": True, "data": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
```

### 添加新的AI模型

1. 在 `config.json` 中添加模型配置
2. 如果API格式不同，在 `call_ai_api()` 中添加新的调用函数
3. 使用 `ai_manager.py` 启用并配置模型

## 版本历史

- v2.1 - 命令行管理版本
  - 新增 `ai_manager.py` 命令行管理工具
  - Server端API简化为只读
  - 模型配置通过命令行管理

- v2.0 - 多AI模型模块化版本
  - 支持多个OPENAI兼容AI模型
  - 配置文件管理模型参数
  - 运行时切换AI模型

- v1.0 - CS架构初始版本
  - 实现Client-Server分离
  - 密钥统一由Server管理