#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
存储桶文件检查程序
检查Server配置的存储桶中的文件是否正常上传
"""

import json
import os
import sys
from datetime import datetime

# 尝试导入boto3
try:
    from boto3.session import Session
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False
    print("[WARNING] boto3未安装，将只检查本地存储")
    print("[INFO] 安装boto3: pip install boto3")

# 尝试导入AES解密模块
try:
    from aescode import AESCoder
    AES_AVAILABLE = True
except ImportError:
    AES_AVAILABLE = False
    print("[WARNING] aescode模块未加载，将跳过加密密钥解密")

def load_config():
    """加载配置文件"""
    config_path = "Server/config.json"
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"[ERROR] 加载配置文件失败: {e}")
        return None

def check_s3_storage(config):
    """检查S3对象存储"""
    if not BOTO3_AVAILABLE:
        print("[ERROR] boto3未安装，无法检查S3存储")
        return False
    
    print("\n" + "="*70)
    print("检查S3对象存储")
    print("="*70)
    
    try:
        obj_config = config['object_storage']
        endpoint = obj_config['endpoint']
        access_key = obj_config['access_key']
        secret_key_encrypted = obj_config['secret_key_encrypted']
        bucket = obj_config['bucket']
        prefix = obj_config.get('prefix', 'results/')
        
        print(f"Endpoint: {endpoint}")
        masked_ak = access_key[:4] + '****' + access_key[-4:] if len(access_key) > 8 else '****'
        print(f"Access Key: {masked_ak}")
        print(f"Bucket: {bucket}")
        print(f"Prefix: {prefix}")
        
        # 解密secret_key
        if AES_AVAILABLE and secret_key_encrypted:
            try:
                aes = AESCoder()
                secret_key = aes.decrypt(secret_key_encrypted.encode())
                print("Secret Key: ****（已解密，不显示明文）")
            except Exception as e:
                print(f"[WARNING] Secret Key解密失败: {e}")
                secret_key = None
        else:
            print("[WARNING] 无法解密Secret Key（aescode模块未加载）")
            secret_key = None
        
        if not secret_key:
            print("[ERROR] 无法获取Secret Key，跳过S3检查")
            return False
        
        # 创建S3客户端
        print("\n正在连接S3存储...")
        session = Session(access_key, secret_key)
        s3_client = session.client('s3', endpoint_url=endpoint)
        
        # 列出存储桶中的文件
        print(f"\n正在列出存储桶 '{bucket}' 中的文件...")
        response = s3_client.list_objects_v2(
            Bucket=bucket,
            Prefix=prefix,
            MaxKeys=100
        )
        
        if 'Contents' not in response:
            print("[WARNING] 存储桶中没有找到文件")
            return True
        
        files = response['Contents']
        print(f"\n找到 {len(files)} 个文件:")
        print("-" * 70)
        
        for obj in files:
            key = obj['Key']
            size = obj['Size']
            last_modified = obj['LastModified'].strftime('%Y-%m-%d %H:%M:%S')
            print(f"  📄 {key}")
            print(f"     大小: {size} 字节")
            print(f"     修改时间: {last_modified}")
            
            # 读取文件内容预览
            try:
                file_response = s3_client.get_object(Bucket=bucket, Key=key)
                content = file_response['Body'].read().decode('utf-8')
                
                # 判断文件类型
                if '_log.md' in key:
                    print(f"     类型: 日志文件")
                    if '## ' in content:
        print(f"     状态: OK 内容格式正确")
                    else:
                        print(f"     状态: ⚠️ 内容格式异常")
                
                elif '_analysis_report.md' in key:
                    print(f"     类型: 分析报告")
                    if '安全应急响应分析报告' in content:
                        print(f"     状态: ✅ AI分析报告格式正确")
                        # 提取安全评分
                        if '安全评分' in content:
                            lines = content.split('\n')
                            for line in lines:
                                if '安全评分' in line or '/100' in line:
                                    print(f"     内容: {line.strip()}")
                                    break
                    else:
                        print(f"     状态: ⚠️ 报告格式异常")
                else:
                    print(f"     类型: 其他文件")
                
                print()
            except Exception as e:
                print(f"     读取失败: {e}")
                print()
        
        print("="*70)
        print(f"✅ S3存储检查完成，共找到 {len(files)} 个文件")
        return True
        
    except Exception as e:
        print(f"\n❌ S3存储检查失败: {e}")
        import traceback
        traceback.print_exc()
        return False

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
        
        print(f"  📄 {filename}")
        print(f"     大小: {size} 字节")
        print(f"     修改时间: {modified}")
        
        # 读取并检查内容
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if '_log.md' in filename:
            print(f"     类型: 日志文件")
            if '## ' in content:
                print(f"     状态: ✅ 内容格式正确")
            else:
                print(f"     状态: ⚠️ 内容格式异常")
        
        elif '_analysis_report.md' in filename:
            print(f"     类型: 分析报告")
            if '安全应急响应分析报告' in content:
                print(f"     状态: ✅ AI分析报告格式正确")
                if '安全评分' in content:
                    lines = content.split('\n')
                    for line in lines:
                        if '安全评分' in line or '/100' in line:
                            print(f"     内容: {line.strip()}")
                            break
            else:
                print(f"     状态: ⚠️ 报告格式异常")
        else:
            print(f"     类型: 其他文件")
        
        print()
    
    print("="*70)
    print(f"✅ 本地存储检查完成，共找到 {len(files)} 个文件")
    return True

def main():
    print("="*70)
    print("应急响应工具 - 存储桶文件检查程序")
    print("="*70)
    print(f"检查时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 加载配置
    config = load_config()
    if not config:
        print("\n[ERROR] 无法加载配置文件，程序退出")
        return
    
    # 检查对象存储配置
    if 'object_storage' not in config:
        print("\n[WARNING] 配置文件中没有对象存储配置")
    else:
        obj_config = config['object_storage']
        if not obj_config.get('endpoint') or not obj_config.get('access_key'):
            print("\n[WARNING] 对象存储配置不完整")
        else:
            print("\n[INFO] 发现对象存储配置")
            check_s3_storage(config)
    
    # 检查本地存储
    check_local_storage()
    
    # 总结
    print("\n" + "="*70)
    print("检查总结")
    print("="*70)
    print("✅ 存储检查完成")
    print("\n说明:")
    print("  - 日志文件（*_log.md）：包含系统信息收集结果")
    print("  - 分析报告（*_analysis_report.md）：包含AI分析结果")
    print("  - 两个文件都应该存在才能确认分析流程正常")
    print("="*70)

if __name__ == "__main__":
    main()