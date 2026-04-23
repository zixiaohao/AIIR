#!/bin/bash
set -e

CONFIG_FILE="/app/config.json"
CONFIG_EXAMPLE="/app/config.json.example"
CONFIG_VOLUME="/app/config/config.json"

# 如果挂载卷中有配置文件，优先使用
if [ -f "$CONFIG_VOLUME" ]; then
    echo "[*] 使用挂载的配置文件: $CONFIG_VOLUME"
    cp "$CONFIG_VOLUME" "$CONFIG_FILE"
# 否则如果存在本地配置文件，使用本地配置
elif [ -f "$CONFIG_FILE" ]; then
    echo "[*] 使用容器内配置文件: $CONFIG_FILE"
# 否则从模板创建默认配置
elif [ -f "$CONFIG_EXAMPLE" ]; then
    echo "[*] 首次启动，从模板创建配置文件..."
    cp "$CONFIG_EXAMPLE" "$CONFIG_FILE"
    echo "[WARNING] 请编辑配置文件设置API密钥: $CONFIG_FILE"
    echo "[提示] 可将外部配置文件挂载到 /app/config/config.json"
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