#!/bin/bash
# Server端依赖安装脚本

echo "=========================================="
echo "应急响应分析系统 - Server端依赖安装"
echo "=========================================="

# 检查Python版本
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "Python版本: $python_version"

# 安装必需依赖
echo ""
echo "[1/3] 安装必需依赖 (Flask, requests)..."
pip3 install flask requests

# 安装可选依赖（对象存储功能）
echo ""
echo "[2/3] 安装可选依赖 (boto3, pycryptodome - 用于对象存储)..."
pip3 install boto3 pycryptodome

# 检查安装结果
echo ""
echo "[3/3] 检查依赖安装情况..."

python3 -c "import flask; print('✅ Flask: OK')" 2>/dev/null || echo "❌ Flask: 安装失败"
python3 -c "import requests; print('✅ Requests: OK')" 2>/dev/null || echo "❌ Requests: 安装失败"
python3 -c "import boto3; print('✅ Boto3: OK')" 2>/dev/null || echo "⚠️  Boto3: 未安装（对象存储功能不可用）"
python3 -c "from Crypto.Cipher import AES; print('✅ Pycryptodome: OK')" 2>/dev/null || echo "⚠️  Pycryptodome: 未安装（对象存储功能不可用）"

echo ""
echo "=========================================="
echo "安装完成！"
echo ""
echo "启动Server:"
echo "  python3 server.py"
echo ""
echo "如果看到 [WARNING] 提示，表示对象存储功能不可用"
echo "但AI分析功能仍可正常使用"
echo "=========================================="