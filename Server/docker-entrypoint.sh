#!/bin/bash
set -e

CONFIG_FILE="/app/config.json"
CONFIG_EXAMPLE="/app/config.json.example"

# 如果挂载卷中有配置文件（Docker部署时），直接使用
if [ -f "$CONFIG_FILE" ]; then
    echo "[*] 使用配置文件: $CONFIG_FILE"
# 否则从模板创建默认配置（首次启动）
elif [ -f "$CONFIG_EXAMPLE" ]; then
    echo "[*] 首次启动，从模板创建配置文件..."
    cp "$CONFIG_EXAMPLE" "$CONFIG_FILE"
    echo "[WARNING] 请编辑配置文件设置API密钥: $CONFIG_FILE"
    echo "[提示] Docker部署: 挂载 /etc/aiir/config.json 到容器 /app/config.json"
    echo "[提示] 源码部署: 直接编辑 Server/config.json"
else
    echo "[ERROR] 未找到配置文件模板"
    exit 1
fi

# 确保上传目录存在
mkdir -p /app/uploaded_files

echo "[*] AIIR Server 准备就绪"
echo "[*] 配置文件: $CONFIG_FILE"

# 执行 CMD
exec "$@"
