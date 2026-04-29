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
│   ├── action_executor.sh     # 自动操作执行器（逐条确认执行AI建议的修复命令）
│   ├── busybox
│   └── vuln
├── winClient/                 # Windows客户端（分批分析版）
│   ├── main.go                # Go源码
│   ├── go.mod / go.sum        # Go模块依赖
│   └── README.md              # Windows客户端说明
├── windowsclient_gaint/       # Windows增强客户端（一次性分析版）
│   ├── main_gaint.go          # 增强版Go源码
│   ├── action_executor_gaint.go # 自动操作执行器（逐条确认执行AI建议的修复命令）
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

## 🚀 一键安装脚本（Linux）

项目提供了 `install.sh` 一键安装脚本，支持中国网络环境，可自动完成 Docker 安装、源码克隆、exe 编译和服务部署。

### 功能特点

- 🐳 **Docker 自动安装**：自动检测并安装 Docker 和 Docker Compose
- 🌐 **网络加速**自动检测网络状况，支持代理配置和镜像加速
- 🔧 **一键编译 exe**：使用 Docker 交叉编译 Windows 客户端
- 📦 **自动部署**：源码克隆后自动部署服务
- 🔄 **一键升级**：自动更新源码并重建服务

### 使用方法

```bash
# 下载脚本（已在本地创建）
chmod +x install.sh

# 运行脚本
sudo ./install.sh
```

### 脚本菜单

```
         AIIR 一键安装脚本
         AI驱动的安全应急响应分析系统

1. 安装 (自动git源码安装 + Docker部署)
2. 编译 exe (使用Docker交叉编译)
3. 升级版本
4. 查看状态
5. 卸载
0. 退出
```

### 网络加速说明

脚本会自动检测网络状况：

1. **优先使用官方源**：如果 GitHub 连接正常，直接克隆
2. **自动切换 Gitee 镜像**：GitHub 连接失败时自动使用 Gitee 镜像
3. **手动配置代理**：网络不通时可输入代理地址
4. **Docker 镜像加速**：自动配置国内 Docker 镜像源（USTC、腾讯云等）

### 默认安装路径

| 组件 | 路径 |
|------|------|
| 源码 | `/opt/aiir` |
| 配置 | `/etc/aiir/config.json` |
| 上传文件 | `/etc/aiir/uploaded_files` |
| 编译产物 | `/opt/aiir/dist/` |

### 快速使用

```bash
# 一键安装（包含编译exe）
sudo ./install.sh
# 选择 1 开始安装

# 单独编译 exe
sudo ./install.sh
# 选择 2 编译

# 一键升级
sudo ./install.sh
# 选择 3 升级
```

### 编译时配置 Server 地址

编译 exe 时，脚本会提示输入 Server 地址，该地址会在编译时注入到客户端中：

```
=== 配置 Server 地址 ===

请输入 Server 地址 (格式: http://IP:端口，留空使用默认): http://192.168.1.100:8000

[SUCCESS] 将使用 Server 地址: http://192.168.1.100:8000

确认继续编译? (y/n): y
```

**特性**：
- 输入的地址通过 `ldflags` 在编译时注入到可执行文件中
- 客户端运行时可直接使用预置地址，无需手动输入
- 如需修改地址，可重新编译或使用客户端的手动输入功能

## 🚀 快速开始

### 方式一：Docker部署（推荐）

配置文件独立存放在宿主机 `/etc/aiir/config.json`，升级时无需重新配置。

#### 1. 克隆仓库并准备配置

```bash
git clone https://github.com/zixiaohao/AIIR.git
cd AIIR/Server

# 创建配置目录并复制配置文件（仅需首次执行）
sudo mkdir -p /etc/aiir
sudo cp config.json.example /etc/aiir/config.json

# 编辑配置文件，填入API密钥
sudo vim /etc/aiir/config.json
```

#### 2. 启动服务

```bash
# 使用Docker Compose启动
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

#### 3. Docker常用命令

```bash
# 查看运行状态
docker-compose ps

# 重启服务
docker-compose restart

# 查看容器日志
docker logs -f aiir-server

# 进入容器内部
docker exec -it aiir-server bash
```

### 方式二：手动部署

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

### 3. 使用Linux客户端

```bash
cd LinuxClient

# 上传到目标服务器后
chmod +x client.sh busybox vuln
./client.sh
# 输入工单号后自动开始采集和分析
```

### 4. 使用Windows客户端

```bash
cd winClient

# 编译
go build -o windows_check.exe main.go

# 运（需要管理员权限）
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
python ai_manager.py set-default deepspeed             # 设置默认模型
python ai_manager.py set-key deepseek sk-xxx           # 设置API密钥
python ai_manager.py add mymodel "My Model" URL gpt-4  # 添加新模型
python ai_manager.py rate-limit                        # 查看限流配置
python ai_manager.py full-analysis-model               # 查看一次性分析模型
```

## 🔧 自动修复操作功能（gaint版本）

gaint版本的增强客户端支持**自动操作**功能，AI分析后会返回可执行的修复命令，每条命令都需要用户确认后才执行，确保操作安全可控。

### 工作流程

```
┌────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   收集系统信息    │ ──► │   AI智能分析     │ ──► │  返回报告+命令   │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                        │
                                                        ▼
                                            ┌─────────────────────────┐
                                            │   逐条确认执行修复命令    │
                                            │   (每条都需要用户确认)    │
                                            └─────────────────────────┘
```

### 使用方法

#### Linux客户端

```bash
# 1. 启动增强版客户端（会自动调用/analyze_with_actions接口）
cd linuxclient_gaint
chmod +x client_gaint.sh action_executor.sh
./client_gaint.sh

# 2. 分析完成后，自动进入命令执行流程
#    或手动调用执行器
./action_executor.sh response.json
```

#### Windows客户端

```bash
# 1. 编译执行器
cd windowsclient_gaint
go build -o action_executor_gaint.exe action_executor_gaint.go

# 2. 启动增强版客户端（会自动调用/analyze_with_actions接口）
go run main_gaint.go -s http://server:8000

# 3. 分析完成后，自动进入命令执行流程
#    或手动调用执行器
action_executor_gaint.exe -f response.json
```

### 命令格式

AI返回的修复命令采用结构化JSON格式：

```json
{
  "actions": [
    {
      "command": "systemctl stop suspicious-service",
      "description": "停止可疑服务以防止进一步损害",
      "risk_level": "high",
      "category": "service"
    },
    {
      "command": "iptables -A INPUT -s 192.168.1.100 -j DROP",
      "description": "封禁恶意IP连接",
      "risk_level": "medium",
      "category": "network"
    }
  ]
}
```

### 执行确认流程

每条命令执行前都会显示详细信息：

```
════════════════════════════════════════════
  操作 [1/3]
════════════════════════════════════════════
  风险等级: 🔴 高危
  类别: service

  描述:
  停止可疑服务以防止进一步损害

  命令:
  systemctl stop suspicious-service

  ⚠️  高风险操作警告！
  此操作可能会对系统产生重大影响，请谨慎确认。
════════════════════════════════════════════

⚠️  高风险操作，请再次输入 YES 确认执行: YES

是否执行此操作? (y=执行 / n=跳过 / v=查看详情) [默认: n]: y

正在执行...
✅ 执行成功
```

### 执行总结

所有命令处理完成后，会显示执行统计：

```
     执行总结
  ✅ 已执行: 2
  ↻ 已跳过: 1
  ❌ 执行失败: 0
  执行率: 66%
```

### 风险等级说明

| 等级 | 标识 | 说明 | 额外确认 |
|------|------|------|---------|
| high | 🔴 高危 | 可能影响系统运行的操作 | 需要输入"YES"二次确认 |
| medium | 🟡 中危 | 常规修复操作 | 正常确认即可 |
| low | 🟢 低危 | 风险较低的查询操作 | 正常确认即可 |

### 注意事项

1. **安全优先**：所有操作都需要用户显式确认，高风险操作需要二次确认
2. **幂等设计**：建议AI生成的命令是幂等的（可安全重复执行）
3. **日志记录**：可通过`-l`参数指定日志文件，记录所有操作历史
4. **权限要求**：部分操作（如停止服务、修改防火墙）需要root/管理员权限

## 🔄 源码部署迁移到Docker

如果你当前使用源码部署，想要迁移到Docker部署：

```bash
# 1. 停止源码运行的Server（Ctrl+C 或 kill 进程）

# 2. 复制现有配置文件到Docker挂载路径
sudo mkdir -p /etc/aiir
sudo cp /path/to/your/AIIR/Server/config.json /etc/aiir/config.json

# 3. 进入Server目录启动Docker
cd /path/to/your/AIIR/Server
docker-compose up -d

# 4. 验证Docker运行状态
docker-compose ps
docker-compose logs -f

# 5. 确认正常后，源码进程可以完全停止
```

**迁移说明**：
- 配置文件复用：直接复制现有的 `config.json` 即可，无需重新配置API密钥
- 上传文件：如有历史上传文件，可手动复制到 `/etc/aiir/uploaded_files/`
- 端口冲突：确保源码Server已停止，避免8000端口冲突

## 🐳 Docker版本更新方法

当项目有新版本发布时，使用以下步骤快速更新：

### 1. 拉取最新代码

```bash
cd AIIR
git pull origin main
```

### 2. 更新Docker镜像并重启

```bash
cd Server

# 停止并删除旧容器
docker-compose down

# 重新构建镜像（强制拉取最新依赖）
docker-compose build --no-cache

# 启动新容器
docker-compose up -d

# 查看更新后的日志
docker-compose logs -f
```

### 3. 一键更新脚本

也可以将上述步骤写入脚本，实现一键更新：

```bash
#!/bin/bash
# update.sh - 一键更新AIIR Server

cd "$(dirname "$0")" || exit 1

echo "[*] 正在拉取最新代码..."
git pull origin main || exit 1

echo "[*] 正在更新Docker容器..."
cd Server
docker-compose down
docker-compose build --no-cache
docker-compose up -d

echo "[*] 更新完成！"
echo "[*] 查看日志: docker-compose logs -f"
```

## 📌 注意事项

1. **安全警告**：`config.json` 中包含API密钥等敏感信息，请勿将其提交到公开仓库
2. 客户端需要 **root/管理员** 权限运行
3. Server端建议部署在内网环境中，通过反向代理对外提供服务
4. Linux客户端建议使用 `dos2unix` 转换格式后再执行

## 📄 License

本项目仅供内部安全应急响应使用。