#!/bin/bash
set -e

CONFIG_FILE="/app/config.json"
CONFIG_EXAMPLE="/app/config.json.example"

# 修复常见问题：Docker挂载不存在的源文件时会创建空目录
if [ -d "$CONFIG_FILE" ]; then
    echo "[WARNING] $CONFIG_FILE 是一个目录（Docker挂载了不存在的文件时会出现此问题）"
    echo "[*] 正在修复：移除空目录并从模板创建配置文件..."
    rm -rf "$CONFIG_FILE"
fi

# 如果配置文件不存在，从模板创建
if [ ! -f "$CONFIG_FILE" ]; then
    if [ -f "$CONFIG_EXAMPLE" ]; then
        echo "[*] 首次启动，从模板创建配置文件..."
        cp "$CONFIG_EXAMPLE" "$CONFIG_FILE"
        echo ""
        echo "=========================================================="
        echo "  [WARNING] 配置文件已从模板创建"
        echo "  请编辑配置文件设置API密钥: $CONFIG_FILE"
        echo ""
        echo "  Docker部署方式:"
        echo "    1. 先在宿主机创建配置:"
        echo "       sudo mkdir -p /etc/aiir"
        echo "       sudo cp config.json.example /etc/aiir/config.json"
        echo "       sudo vim /etc/aiir/config.json"
        echo "    2. 然后启动容器: docker-compose up -d"
        echo ""
        echo "  或者进入容器编辑:"
        echo "       docker exec -it aiir-server vim /app/config.json"
        echo "=========================================================="
        echo ""
    else
        echo "[ERROR] 未找到配置文件和模板文件"
        echo "[ERROR] 请确保 config.json.example 存在于镜像中"
        exit 1
    fi
else
    echo "[*] 使用配置文件: $CONFIG_FILE"
fi

# 验证配置文件是有效的JSON
if command -v python3 &> /dev/null; then
    if ! python3 -c "import json; json.load(open('$CONFIG_FILE'))" 2>/dev/null; then
        echo "[ERROR] 配置文件 $CONFIG_FILE 不是有效的JSON格式"
        echo "[ERROR] 请检查配置文件语法"
        exit 1
    fi
    echo "[*] 配置文件JSON格式验证通过"
fi

# 确保上传目录存在
mkdir -p /app/uploaded_files

echo "[*] AIIR Server 准备就绪"
echo "[*] 配置文件: $CONFIG_FILE"

# 执行 CMD
exec "$@"
