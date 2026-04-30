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

# 验证配置文件是有效的JSON，失败时显示具体错误并尝试修复
if command -v python3 &> /dev/null; then
    PARSE_RESULT=$(python3 -c "
import json, sys
try:
    with open('$CONFIG_FILE', 'r', encoding='utf-8') as f:
        json.load(f)
    print('OK')
except json.JSONDecodeError as e:
    print(f'ERROR|{e.lineno}|{e.colno}|{e.msg}')
except Exception as e:
    print(f'ERROR|||{e}')
" 2>&1)

    if [ "$PARSE_RESULT" = "OK" ]; then
        echo "[*] 配置文件JSON格式验证通过"
    else
        # 解析错误详情
        ERROR_LINE=$(echo "$PARSE_RESULT" | cut -d'|' -f2)
        ERROR_COL=$(echo "$PARSE_RESULT" | cut -d'|' -f3)
        ERROR_MSG=$(echo "$PARSE_RESULT" | cut -d'|' -f4-)

        echo ""
        echo "=========================================================="
        echo "  [ERROR] 配置文件JSON格式错误!"
        echo "  位置: 第 ${ERROR_LINE} 行, 第 ${ERROR_COL} 列"
        echo "  原因: ${ERROR_MSG}"
        echo ""
        echo "  出错位置附近的代码:"
        python3 -c "
with open('$CONFIG_FILE', 'r', encoding='utf-8') as f:
    lines = f.readlines()
    err_line = $ERROR_LINE
    start = max(0, err_line - 3)
    end = min(len(lines), err_line + 2)
    for i in range(start, end):
        marker = ' >>> ' if i + 1 == err_line else '     '
        print(f'{marker}{i+1:4d}: {lines[i].rstrip()}')
" 2>/dev/null
        echo ""
        echo "  修复方式:"
        echo "    1. 进入容器编辑: docker exec -it aiir-server vi $CONFIG_FILE"
        echo "    2. 或在宿主机编辑: sudo vi /etc/aiir/config.json"
        echo "    3. 或重置为模板:   docker exec aiir-server cp $CONFIG_EXAMPLE $CONFIG_FILE"
        echo "=========================================================="
        echo ""

        # 如果模板可用，自动重置
        if [ -f "$CONFIG_EXAMPLE" ]; then
            echo "[*] 自动从模板重置配置文件（API密钥需重新配置）..."
            cp "$CONFIG_EXAMPLE" "$CONFIG_FILE"
            echo "[WARNING] 配置文件已重置为模板，请重新配置API密钥"
            echo "[WARNING] 编辑: docker exec -it aiir-server vi $CONFIG_FILE"
        else
            exit 1
        fi
    fi
fi

# 确保上传目录存在
mkdir -p /app/uploaded_files

echo "[*] AIIR Server 准备就绪"
echo "[*] 配置文件: $CONFIG_FILE"

# 执行 CMD
exec "$@"
