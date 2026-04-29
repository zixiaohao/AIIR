#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
存储桶文件检查程序（简化版）
检查Server配置的存储桶中的文件是否正常上传
"""

import json
import os
from datetime import datetime

def load_config():
    """加载配置文件"""
    config_path = "Server/config.json"
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"[ERROR] 加载配置文件失败: {e}")
        return None

def check_local_storage():
    """检查本地存储"""
    print("\n" + "="*70)
    print("检查本地存储")
    print("="*70)
    
    local_storage_dir = "Server/uploaded_files"
    
    if not os.path.exists(local_storage_dir):
        print(f"[INFO] 本地存储目录不存在: {local_storage_dir}")
        print("[INFO] 这是正常的，如果没有文件上传")
        return True
    
    files = os.listdir(local_storage_dir)
    
    if not files:
        print(f"[INFO] 本地存储目录为空")
        return True
    
    print(f"找到 {len(files)} 个文件:")
    print("-" * 70)
    
    for filename in files:
        filepath = os.path.join(local_storage_dir, filename)
        size = os.path.getsize(filepath)
        modified = datetime.fromtimestamp(os.path.getmtime(filepath)).strftime('%Y-%m-%d %H:%M:%S')
        
        print(f"  [FILE] {filename}")
        print(f"     Size: {size} bytes")
        print(f"     Modified: {modified}")
        
        # 读取并检查内容
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if '_log.md' in filename:
            print(f"     Type: Log File")
            if '## ' in content:
                print(f"     Status: OK - Content format correct")
            else:
                print(f"     Status: WARNING - Content format abnormal")
        
        elif '_analysis_report.md' in filename:
            print(f"     Type: Analysis Report")
            if '安全应急响应分析报告' in content:
                print(f"     Status: OK - AI analysis report format correct")
                if '安全评分' in content:
                    lines = content.split('\n')
                    for line in lines:
                        if '安全评分' in line or '/100' in line:
                            print(f"     Content: {line.strip()}")
                            break
            else:
                print(f"     Status: WARNING - Report format abnormal")
        else:
            print(f"     Type: Other file")
        
        print()
    
    print("="*70)
    print(f"[OK] Local storage check completed, found {len(files)} files")
    return True

def main():
    print("="*70)
    print("Emergency Response Tool - Storage Check Program")
    print("="*70)
    print(f"Check Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 加载配置
    config = load_config()
    if not config:
        print("\n[ERROR] Cannot load config file, program exit")
        return
    
    # 检查对象存储配置
    if 'object_storage' not in config:
        print("\n[WARNING] No object storage config in config file")
    else:
        obj_config = config['object_storage']
        if not obj_config.get('endpoint') or not obj_config.get('access_key'):
            print("\n[WARNING] Object storage config incomplete")
        else:
            print("\n[INFO] Found object storage config")
            print(f"  Endpoint: {obj_config['endpoint']}")
            ak = obj_config['access_key']
            masked_ak = ak[:4] + '****' + ak[-4:] if len(ak) > 8 else '****'
            print(f"  Access Key: {masked_ak}")
            print(f"  Bucket: {obj_config['bucket']}")
            print(f"  Prefix: {obj_config.get('prefix', 'results/')}")
            print("\n[INFO] To check S3 storage, please install boto3 and aescode modules")
    
    # 检查本地存储
    check_local_storage()
    
    # 总结
    print("\n" + "="*70)
    print("Check Summary")
    print("="*70)
    print("[OK] Storage check completed")
    print("\nNotes:")
    print("  - Log files (*_log.md): Contains system information collection results")
    print("  - Analysis reports (*_analysis_report.md): Contains AI analysis results")
    print("  - Both files should exist to confirm the analysis process is normal")
    print("="*70)

if __name__ == "__main__":
    main()