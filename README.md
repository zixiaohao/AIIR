# 🔒 SystemCheck - AI驱动的安全应急响应分析系统

基于 **C/S架构** 的自动化安全应急响应工具，支持 **Linux** 和 **Windows** 平台，集成多款AI大模型进行智能安全分析。

## 📋 项目简介

SystemCheck 是一套完整的安全应急响应解决方案，包含：

- **Server端**：Flask Web服务，接收客户端数据，调用AI模型进行模块化安全分析
- **Linux客户端**：Shell脚本，自动收集Linux系统安全信息并上报
- **Windows客户端**：Go语言程序，自动收集Windows系统安全信息并上报
- **增强版客户端（gaint）**：支持一次性全量分析的增强版本

## 🏗️ 项目结构

```
system_check/
├── Server/                     # 服务端
│   ├── server.py              # Flask主服务（API接口、AI分析引擎）
│   ├── ai_manager.py          # AI模型管理命令行工具
│   ├── config.json            # 服务配置文件（AI模型、限流、对象存储等）
│   ├── aescode.py             # AES加解密模块
│   ├── attack_patterns.json   # 攻击特征库
│   ├── install_deps.sh        # 依赖安装脚本
│   └── README.md              # Server端说明
├── LinuxClient/               # Linux客户端（分批分析版）
│   ├── client.sh              # 主脚本
│   ├── busybox                # 兼容性工具
│   └── vuln                   # 漏洞检测工具
├── linuxclient_gaint/         # Linux增强客户端（一次性分析版）
│   ├── client_gaint.sh        # 增强版主脚本
│   ├── busybox
│   └── vuln
├── winClient/                 # Windows客户端（分批分析版）
│   ├── main.go                # Go源码
│   ├── go.mod / go.sum        # Go模块依赖
│   └── README.md              # Windows客户端说明
├── windowsclient_gaint/       # Windows增强客户端（一次性分析版）
│   ├── main_gaint.go          # 增强版Go源码
│   ├── main_gaint_part2.go    # 源码分片
│   ├── main_gaint_merged.go   # 合并后源码
│   ├── go.mod / go.sum
│   └── README.md
├── .gitignore
└── README.md                  # 项目总说明（本文件）
```

## ✨ 核心功能

### Server端
- 🤖 **多AI模型支持**：DeepSeek、OpenAI GPT-4、Claude、智谱GLM-4、Moonshot、通义千问、MiMo、MiniMax 等
- 📊 **模块化分析**：将日志按模块拆分，逐个分析后汇总研判
- 🔍 **一次性全量分析**：支持大上下文窗口模型一次性分析所有数据
- 🛡️ **IP限流与黑名单**：防止API滥用
- ☁️ **对象存储集成**：支持S3兼容存储（可选）
- 📋 **白名单机制**：自动排除已知安全进程，减少误报

### 客户端
- 🖥️ **系统信息采集**：进程、网络连接、计划任务、系统日志、安全配置等
- 🔎 **本地攻击特征匹配**：内置攻击模式库，预筛可疑项
- 📡 **自动上报与分析**：采集完成后自动发送至Server进行AI分析
- 📄 **报告生成**：Server返回结构化Markdown安全报告

## 🚀 快速开始

### 1. 部署Server端

```bash
cd Server

# 安装依赖
bash install_deps.sh
# 或手动安装
pip install flask requests boto3

# 配置AI模型（编辑 config.json，填入API Key）
python ai_manager.py list                    # 查看所有模型
python ai_manager.py set-key deepseek sk-xxx  # 设置API密钥
python ai_manager.py enable deepseek          # 启用模型
python ai_manager.py set-default deepseek     # 设置默认模型

# 启动服务
python server.py
# 可选参数
python server.py --port 8000 --host 0.0.0.0 --debug
```

### 2. 使用Linux客户端

```bash
cd LinuxClient

# 上传到目标服务器后
chmod +x client.sh busybox vuln
./client.sh
# 输入工单号后自动开始采集和分析
```

### 3. 使用Windows客户端

```bash
cd winClient

# 编译
go build -o windows_check.exe main.go

# 运行（需要管理员权限）
windows_check.exe
```

## ⚙️ 配置说明

Server端核心配置在 `Server/config.json`：

| 配置项 | 说明 |
|--------|------|
| `server.port` | 监听端口（默认8000） |
| `ai_models.default` | 默认AI模型 |
| `ai_models.full_analysis_model` | 一次性分析接口使用的模型 |
| `ai_models.models.<key>.api_key` | 各模型的API密钥 |
| `rate_limit` | IP限流配置（每IP最大请求数、时间窗口） |
| `ip_blacklist` | IP黑名单 |
| `object_storage` | S3兼容对象存储配置（可选） |
| `analysis.whitelist_keywords` | 白名单关键词（排除已知安全进程） |

## 📡 API接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/models` | GET | 查看AI模型列表 |
| `/analyze` | POST | 分批分析（模块化） |
| `/analyze_full` | POST | 一次性全量分析 |
| `/analyze_section` | POST | 分析单个模块 |
| `/analyze_summary` | POST | 汇总分析 |
| `/upload` | POST | 直接上传文件 |
| `/attack_patterns` | GET | 获取攻击特征库 |
| `/ip_stats` | GET | IP访问统计 |
| `/blacklist` | GET | 黑名单管理 |

## 🛠️ AI模型管理工具

```bash
python ai_manager.py list                              # 列出所有模型
python ai_manager.py show deepseek                     # 查看模型详情
python ai_manager.py enable openai                     # 启用模型
python ai_manager.py disable openai                    # 禁用模型
python ai_manager.py set-default deepseek              # 设置默认模型
python ai_manager.py set-key deepseek sk-xxx           # 设置API密钥
python ai_manager.py add mymodel "My Model" URL gpt-4  # 添加新模型
python ai_manager.py rate-limit                        # 查看限流配置
python ai_manager.py full-analysis-model               # 查看一次性分析模型
```

## 📌 注意事项

1. **安全警告**：`config.json` 中包含API密钥等敏感信息，请勿将其提交到公开仓库
2. 客户端需要 **root/管理员** 权限运行
3. Server端建议部署在内网环境中，通过反向代理对外提供服务
4. Linux客户端建议使用 `dos2unix` 转换格式后再执行

## 📄 License

本项目仅供内部安全应急响应使用。