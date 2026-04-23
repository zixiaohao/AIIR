#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试上传功能，检查Server是否正确接收和存储文件
"""

import requests
import json

SERVER_URL = "http://127.0.0.1:8000"

def test_upload():
    """测试上传功能"""
    
    # 测试内容1：日志内容
    log_content = """# 测试日志文件

## 系统信息
这是测试日志内容
主机名: TEST
IP地址: 192.168.1.100
"""
    
    # 测试内容2：分析报告内容
    analysis_content = """# 安全应急响应分析报告

## 检测目标信息
- 主机名: TEST
- IP地址: 192.168.1.100
- 检测平台: windows
- 检测时间: 2026-03-27 11:00:00
- 分析模型: mimo-v2-pro

---

## 分析报告

这是测试分析报告内容
系统安全评分：85/100
未发现明显安全问题。
"""
    
    print("=" * 60)
    print("测试上传功能")
    print("=" * 60)
    
    # 1. 上传日志文件
    print("\n[1] 上传日志文件: test_log.md")
    upload_log_request = {
        "filename": "test_log.md",
        "content": log_content
    }
    
    try:
        response = requests.post(
            f"{SERVER_URL}/upload",
            json=upload_log_request,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        result = response.json()
        print(f"  响应: {json.dumps(result, ensure_ascii=False, indent=2)}")
        if result.get('success'):
            print("  ✅ 日志文件上传成功")
        else:
            print(f"  ❌ 日志文件上传失败: {result.get('message')}")
    except Exception as e:
        print(f"  ❌ 请求失败: {str(e)}")
    
    # 2. 上传分析报告文件
    print("\n[2] 上传分析报告文件: test_analysis_report.md")
    upload_analysis_request = {
        "filename": "test_analysis_report.md",
        "content": analysis_content
    }
    
    try:
        response = requests.post(
            f"{SERVER_URL}/upload",
            json=upload_analysis_request,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        result = response.json()
        print(f"  响应: {json.dumps(result, ensure_ascii=False, indent=2)}")
        if result.get('success'):
            print("  ✅ 分析报告上传成功")
        else:
            print(f"  ❌ 分析报告上传失败: {result.get('message')}")
    except Exception as e:
        print(f"  ❌ 请求失败: {str(e)}")
    
    # 3. 检查上传的文件
    print("\n" + "=" * 60)
    print("检查上传的文件")
    print("=" * 60)
    
    import os
    uploaded_files_dir = "Server/uploaded_files"
    
    if os.path.exists(uploaded_files_dir):
        files = os.listdir(uploaded_files_dir)
        print(f"\n上传目录中的文件: {files}")
        
        for filename in files:
            filepath = os.path.join(uploaded_files_dir, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            print(f"\n{'='*60}")
            print(f"文件名: {filename}")
            print(f"{'='*60}")
            
            # 检查文件内容是否正确
            if "test_log.md" in filename:
                if "测试日志文件" in content:
                    print("✅ 日志文件内容正确")
                else:
                    print("❌ 日志文件内容错误")
                    print(f"内容预览: {content[:200]}...")
            
            elif "test_analysis_report.md" in filename:
                if "安全应急响应分析报告" in content and "85/100" in content:
                    print("✅ 分析报告内容正确")
                else:
                    print("❌ 分析报告内容错误")
                    print(f"内容预览: {content[:200]}...")
    else:
        print(f"\n❌ 上传目录不存在: {uploaded_files_dir}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

if __name__ == "__main__":
    test_upload()