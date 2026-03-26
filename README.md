# 应急响应工具 - AI驱动的安全分析系统

## 项目简介

这是一个基于AI的应急响应工具，采用CS（Client-Server）架构，能够自动收集系统安全信息并进行智能分析。该工具支持Windows和Linux平台，可以帮助安全团队快速识别系统中的潜在威胁和异常行为。

## 项目特点

- 🔍 **全面信息收集**: 收集系统信息、网络连接、进程列表、用户账户、定时任务等关键安全数据
- 🤖 **AI智能分析**: 支持多种AI模型（DeepSeek、OpenAI、Claude等）进行安全威胁分析
- 📊 **分批处理**: 支持分批分析模式，避免超出大模型上下文限制
- 💻 **跨平台支持**: 提供Windows和Linux客户端
- 🔐 **安全设计**: 客户端不存储任何敏感密钥，所有敏感信息由服务端处理
- 📴 **离线模式**: 支持离线安全检查，即使无法连接服务器也能执行基本检查
- 🎯 **灵活配置**: 通过命令行参数指定服务器地址，无需硬编码配置

## 项目结构

```
AIIR/
├── winClient/                      # Windows客户端（分批分析版本）
│   ├── main.go                     # 主程序源码
│   ├── go.mod                      # Go模块依赖配置
│   ├── windows_check-v5.exe        # 编译好的可执行文件
│   └── README.md                   # 使用说明
│
├── windowsclient_gaint/            # Windows客户端（一次性发送版本）
│   ├── main_gaint.go               # 主程序源码
│   ├── go.mod                      # Go模块依赖配置
│   ├── windows_check_gaint-v5.exe  # 编译好的可执行文件
│   └── README.md                   # 使用说明
│
├── LinuxClient/                    # Linux客户端（分批分析版本）
│   ├── client.sh                   # 主程序脚本
│   ├── busybox                     # 工具箱（可选）
│   ├── vuln                        # 漏洞扫描工具（可选）
│   └── README.md                   # 使用说明
│
├── linuxclient_gaint/              # Linux客户端（一次性发送版本）
│   ├── client_gaint.sh             # 主程序脚本
│   ├── busybox                     # 工具箱（可选）
│   ├── vuln                        # 漏洞扫描工具（可选）
│   └── README.md                   # 使用说明
│
└── Server/                         # 服务端
    ├── server.py                   # 服务端主程序
    ├── ai_manager.py               # AI模型管理工具
    ├── aescode.py                  # AES加密模块
    ├── config.json                 # 配置文件
    ├── attack_patterns.json        # 攻击特征库
    ├── install_deps.sh             # 依赖安装脚本
    └── README.md                   # 使用说明
```

## 快速开始

### 1. 服务端部署

```bash
# 进入Server目录
cd Server

# 安装依赖
bash install_deps.sh

# 配置API密钥（编辑config.json）
vi config.json

# 启动服务
python3 server.py
```

服务端默认监听 `0.0.0.0:8000`。

### 2. Windows客户端使用

```cmd
# 进入winClient目录
cd winClient

# 使用命令行参数指定服务器地址
win_client.exe -s http://YOUR_SERVER_IP:8000

# 或使用交互式输入
win_client.exe

# 查看帮助
win_client.exe -h
```

### 3. Linux客户端使用

```bash
# 进入LinuxClient目录
cd LinuxClient

# 赋予执行权限
chmod +x client.sh

# 使用命令行参数指定服务器地址
sudo ./client.sh -s http://YOUR_SERVER_IP:8000

# 或使用交互式输入
sudo ./client.sh

# 查看帮助
./client.sh -h
```

## 版本说明

### 分批分析版本（winClient / LinuxClient）

- 逐个模块发送到Server分析
- 适合标准上下文窗口的AI模型
- 可处理较大数据量
- 网络请求次数较多（N+1次，N为模块数）

### 一次性发送版本（windowsclient_gaint / linuxclient_gaint）

- 一次性发送所有数据到Server
- 适合大上下文窗口的AI模型（如128K tokens以上）
- 网络请求次数少（1次）
- 数据量受大模型上下文限制

## 功能特性

### 信息收集

- **系统信息**: 操作系统版本、CPU、内存、磁盘空间
- **网络信息**: ARP表、网络连接、路由表、防火墙规则、开放端口
- **用户信息**: 本地用户、特权用户、登录历史、命令历史
- **进程信息**: 进程列表、可疑进程检测
- **持久化检查**: 启动项、定时任务、服务
- **安全日志**: 登录记录、服务创建事件
- **Web服务器**: IIS/Apache/Nginx日志分析
- **OA/ERP系统**: 通达、致远、泛微等系统日志检查

### AI分析

支持多种AI模型：
- DeepSeek
- OpenAI GPT-4
- Claude
- 智谱GLM-4
- Moonshot (Kimi)
- 通义千问
- 自定义OPENAI兼容接口

### 离线模式

当无法连接Server时，客户端会自动执行离线安全检查：
- 可疑进程检测
- 异常网络连接检查
- SUID/SGID文件检查
- 最近修改的可执行文件检查
- 异常定时任务检查
- 异常用户检查
- SSH配置检查
- 关键文件权限检查

## 配置说明

### 服务端配置（config.json）

```json
{
  "server": {
    "port": 8000,
    "host": "0.0.0.0"
  },
  "ai_models": {
    "default": "deepseek",
    "models": {
      "deepseek": {
        "api_url": "https://api.deepseek.com/chat/completions",
        "api_key": "YOUR_API_KEY_HERE",
        "model_name": "deepseek-chat",
        "enabled": true
      }
    }
  }
}
```

### 客户端配置

客户端不再硬编码服务器地址，通过以下方式指定：
1. 命令行参数：`-s` 或 `--server`
2. 交互式输入：运行时提示输入

## API接口

服务端提供以下API接口：

- `GET /health` - 健康检查
- `GET /models` - 查看模型列表
- `POST /analyze` - 分析数据（分批模式）
- `POST /analyze_full` - 一次性分析（gaint版本）
- `POST /analyze_section` - 分析单个模块
- `POST /analyze_summary` - 汇总分析
- `POST /upload` - 上传文件
- `GET /attack_patterns` - 获取攻击特征库

## 使用流程

1. **部署服务端**: 在服务器上部署并启动Server
2. **配置AI模型**: 在config.json中配置AI模型的API密钥
3. **运行客户端**: 在目标机器上运行客户端，指定Server地址
4. **输入工单ID**: 为本次检测任务指定一个工单ID
5. **等待收集**: 客户端自动收集系统信息
6. **AI分析**: 数据发送到Server进行AI分析
7. **查看报告**: 分析报告会保存为 `{工单ID}_analysis_report.md`

## 安全说明

- 客户端不存储任何API密钥或敏感信息
- 所有敏感配置由服务端管理
- 数据通过HTTP传输，建议在内网环境使用
- 客户端需要管理员/root权限才能完整收集信息

## 故障排查

### 客户端无法连接Server

```bash
# 检查Server是否运行
curl http://YOUR_SERVER_IP:8000/health

# 检查网络连通性
ping YOUR_SERVER_IP

# 检查防火墙
telnet YOUR_SERVER_IP 8000
```

### AI分析失败

- 检查config.json中的API密钥是否正确
- 检查API余额是否充足
- 使用 `ai_manager.py` 检查模型状态

### 权限不足

- Windows: 右键选择"以管理员身份运行"
- Linux: 使用 `sudo` 运行

## 开发说明

### 编译Windows客户端

```bash
cd winClient
go mod tidy
go build -o windows_check-v5.exe main.go
```

### 修改配置

- 修改 `Server/config.json` 配置AI模型
- 使用 `python3 ai_manager.py` 管理模型

## 版本历史

- **v3.1** - 通用版本
  - 移除硬编码服务器地址
  - 添加命令行参数支持
  - 支持离线安全检查
  - 支持多种AI模型

- **v3.0** - CS架构版本
  - 采用Client-Server架构
  - 支持分批分析模式
  - 移除本地密钥存储

- **v2.0** - 本地分析版本
  - 本地AI分析
  - 本地密钥存储

- **v1.0** - 初始版本

## 许可证

本项目仅供学习和研究使用，请勿用于非法用途。

## 联系方式

如有问题或建议，请联系项目维护者。