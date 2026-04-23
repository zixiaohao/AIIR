#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AI模型管理工具
用于管理config.json中的AI模型配置
"""

import json
import sys
import argparse

CONFIG_FILE = "config.json"

def load_config():
    """加载配置文件"""
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"[ERROR] 加载配置文件失败: {e}")
        return None

def save_config(config):
    """保存配置文件"""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"[ERROR] 保存配置文件失败: {e}")
        return False

def list_models(config):
    """列出所有模型"""
    print("\n" + "="*60)
    print("AI模型列表")
    print("="*60)
    print(f"默认模型: {config['ai_models']['default']}")
    print("-"*60)
    
    for key, model in config['ai_models']['models'].items():
        status = "✅ 已启用" if model.get('enabled', False) else "❌ 未启用"
        has_key = "已配置" if model.get('api_key') else "未配置"
        is_default = " [默认]" if key == config['ai_models']['default'] else ""
        
        print(f"\n[{key}]{is_default}")
        print(f"  名称: {model['name']}")
        print(f"  模型: {model['model_name']}")
        print(f"  API地址: {model['api_url']}")
        print(f"  API密钥: {has_key}")
        print(f"  状态: {status}")
    
    print("\n" + "="*60)

def enable_model(config, model_key):
    """启用模型"""
    if model_key not in config['ai_models']['models']:
        print(f"[ERROR] 模型 '{model_key}' 不存在")
        return False
    
    config['ai_models']['models'][model_key]['enabled'] = True
    if save_config(config):
        print(f"[SUCCESS] 模型 '{model_key}' 已启用")
        return True
    return False

def disable_model(config, model_key):
    """禁用模型"""
    if model_key not in config['ai_models']['models']:
        print(f"[ERROR] 模型 '{model_key}' 不存在")
        return False
    
    if model_key == config['ai_models']['default']:
        print(f"[ERROR] 不能禁用默认模型，请先切换默认模型")
        return False
    
    config['ai_models']['models'][model_key]['enabled'] = False
    if save_config(config):
        print(f"[SUCCESS] 模型 '{model_key}' 已禁用")
        return True
    return False

def set_default(config, model_key):
    """设置默认模型"""
    if model_key not in config['ai_models']['models']:
        print(f"[ERROR] 模型 '{model_key}' 不存在")
        return False
    
    if not config['ai_models']['models'][model_key].get('enabled', False):
        print(f"[ERROR] 模型 '{model_key}' 未启用，请先启用该模型")
        return False
    
    config['ai_models']['default'] = model_key
    if save_config(config):
        print(f"[SUCCESS] 默认模型已设置为 '{model_key}'")
        return True
    return False

def update_api_key(config, model_key, api_key):
    """更新API密钥"""
    if model_key not in config['ai_models']['models']:
        print(f"[ERROR] 模型 '{model_key}' 不存在")
        return False
    
    config['ai_models']['models'][model_key]['api_key'] = api_key
    if save_config(config):
        print(f"[SUCCESS] 模型 '{model_key}' 的API密钥已更新")
        return True
    return False

def update_config(config, model_key, field, value):
    """更新模型配置"""
    if model_key not in config['ai_models']['models']:
        print(f"[ERROR] 模型 '{model_key}' 不存在")
        return False
    
    allowed_fields = ['name', 'api_url', 'api_key', 'model_name', 'temperature', 'max_tokens']
    if field not in allowed_fields:
        print(f"[ERROR] 不允许修改字段 '{field}'")
        print(f"允许的字段: {', '.join(allowed_fields)}")
        return False
    
    # 类型转换
    if field == 'temperature':
        value = float(value)
    elif field == 'max_tokens':
        value = int(value)
    
    config['ai_models']['models'][model_key][field] = value
    if save_config(config):
        print(f"[SUCCESS] 模型 '{model_key}' 的 '{field}' 已更新为: {value}")
        return True
    return False

def show_model(config, model_key):
    """显示模型详情"""
    if model_key not in config['ai_models']['models']:
        print(f"[ERROR] 模型 '{model_key}' 不存在")
        return False
    
    model = config['ai_models']['models'][model_key]
    is_default = " [默认]" if model_key == config['ai_models']['default'] else ""
    
    print("\n" + "="*60)
    print(f"模型详情: [{model_key}]{is_default}")
    print("="*60)
    print(f"名称: {model['name']}")
    print(f"模型ID: {model['model_name']}")
    print(f"API地址: {model['api_url']}")
    print(f"API密钥: {'已配置' if model.get('api_key') else '未配置'}")
    print(f"Temperature: {model.get('temperature', 0.1)}")
    print(f"Max Tokens: {model.get('max_tokens', 4096)}")
    print(f"状态: {'已启用' if model.get('enabled', False) else '未启用'}")
    print("="*60 + "\n")

def add_model(config, model_key, name, api_url, model_name):
    """添加新模型"""
    if model_key in config['ai_models']['models']:
        print(f"[ERROR] 模型 '{model_key}' 已存在")
        return False
    
    config['ai_models']['models'][model_key] = {
        "name": name,
        "api_url": api_url,
        "api_key": "",
        "model_name": model_name,
        "temperature": 0.1,
        "max_tokens": 4096,
        "enabled": False
    }
    
    if save_config(config):
        print(f"[SUCCESS] 模型 '{model_key}' 已添加（未启用）")
        print("请使用以下命令配置API密钥并启用:")
        print(f"  python {sys.argv[0]} set-key {model_key} <YOUR_API_KEY>")
        print(f"  python {sys.argv[0]} enable {model_key}")
        return True
    return False

def delete_model(config, model_key):
    """删除模型"""
    if model_key not in config['ai_models']['models']:
        print(f"[ERROR] 模型 '{model_key}' 不存在")
        return False
    
    if model_key == config['ai_models']['default']:
        print(f"[ERROR] 不能删除默认模型，请先切换默认模型")
        return False
    
    model_name = config['ai_models']['models'][model_key]['name']
    del config['ai_models']['models'][model_key]
    
    if save_config(config):
        print(f"[SUCCESS] 模型 '{model_key}' ({model_name}) 已删除")
        return True
    return False

def show_rate_limit(config):
    """显示IP限流配置"""
    rate_limit = config.get('rate_limit', {})
    
    print("\n" + "="*60)
    print("IP限流配置")
    print("="*60)
    print(f"启用状态: {'✅ 已启用' if rate_limit.get('enabled', False) else '❌ 未启用'}")
    print(f"每个IP最大请求数: {rate_limit.get('max_requests_per_ip', 10)}")
    print(f"时间窗口（小时）: {rate_limit.get('time_window_hours', 2)}")
    print("="*60 + "\n")

def show_full_analysis_model(config):
    """显示/analyze_full接口使用的模型"""
    full_analysis_model = config['ai_models'].get('full_analysis_model', '未配置')
    default_model = config['ai_models'].get('default', '未配置')
    
    print("\n" + "="*60)
    print("一次性分析接口 (/analyze_full) 配置")
    print("="*60)
    print(f"full_analysis_model: {full_analysis_model}")
    print(f"default_model: {default_model}")
    
    # 检查模型是否启用
    if full_analysis_model in config['ai_models']['models']:
        model = config['ai_models']['models'][full_analysis_model]
        enabled = model.get('enabled', False)
        max_tokens = model.get('max_tokens', 0)
        print(f"模型状态: {'✅ 已启用' if enabled else '❌ 未启用'}")
        print(f"最大tokens: {max_tokens}")
    else:
        print("模型状态: ❌ 模型不存在")
    
    print("="*60 + "\n")

def set_full_analysis_model(config, model_key):
    """设置/analyze_full接口使用的模型"""
    if model_key not in config['ai_models']['models']:
        print(f"[ERROR] 模型 '{model_key}' 不存在")
        return False
    
    if not config['ai_models']['models'][model_key].get('enabled', False):
        print(f"[ERROR] 模型 '{model_key}' 未启用，请先启用该模型")
        return False
    
    config['ai_models']['full_analysis_model'] = model_key
    if save_config(config):
        print(f"[SUCCESS] /analyze_full 接口模型已设置为 '{model_key}'")
        return True
    return False

def set_rate_limit(config, field, value):
    """设置IP限流配置"""
    if 'rate_limit' not in config:
        config['rate_limit'] = {
            "enabled": True,
            "max_requests_per_ip": 10,
            "time_window_hours": 2
        }
    
    allowed_fields = ['enabled', 'max_requests_per_ip', 'time_window_hours']
    if field not in allowed_fields:
        print(f"[ERROR] 不允许修改字段 '{field}'")
        print(f"允许的字段: {', '.join(allowed_fields)}")
        return False
    
    # 类型转换
    if field == 'enabled':
        if isinstance(value, str):
            value = value.lower() in ['true', '1', 'yes', 'y']
        else:
            value = bool(value)
    elif field in ['max_requests_per_ip', 'time_window_hours']:
        value = int(value)
    
    config['rate_limit'][field] = value
    if save_config(config):
        print(f"[SUCCESS] IP限流配置 '{field}' 已更新为: {value}")
        return True
    return False

def show_ip_stats(config):
    """显示IP统计信息"""
    import requests
    
    try:
        # 请求Server获取IP统计
        server_url = f"http://{config['server']['host']}:{config['server']['port']}"
        response = requests.get(f"{server_url}/ip_stats", timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                stats = data.get('stats', {})
                blacklist = data.get('blacklist', [])
                
                print("\n" + "="*60)
                print("IP统计信息")
                print("="*60)
                
                if not stats:
                    print("暂无IP访问记录")
                else:
                    print(f"{'IP地址':<20} {'总请求数':<12} {'当前窗口':<12} {'黑名单':<8}")
                    print("-"*60)
                    for ip, info in stats.items():
                        blacklist_status = "是" if info.get('is_blacklisted') else "否"
                        print(f"{ip:<20} {info['total_requests']:<12} {info['current_window_requests']:<12} {blacklist_status:<8}")
                
                print("\n" + "="*60)
                if blacklist:
                    print(f"黑名单IP: {', '.join(blacklist)}")
                else:
                    print("黑名单: 空")
                print("="*60 + "\n")
                return True
            else:
                print(f"[ERROR] 获取统计信息失败: {data.get('error')}")
                return False
        else:
            print(f"[ERROR] Server返回错误: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("[ERROR] 无法连接到Server，请检查Server是否启动")
        return False
    except Exception as e:
        print(f"[ERROR] 获取统计信息失败: {e}")
        return False

def clear_ip_stats(config, ip=None):
    """清除IP统计数据"""
    import requests
    
    try:
        # 请求Server清除统计
        server_url = f"http://{config['server']['host']}:{config['server']['port']}"
        payload = {}
        if ip:
            payload['ip'] = ip
        
        response = requests.post(f"{server_url}/ip_stats/clear", json=payload, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                if ip:
                    print(f"[SUCCESS] 已清除IP {ip} 的统计数据")
                else:
                    print("[SUCCESS] 已清除所有IP的统计数据")
                return True
            else:
                print(f"[ERROR] {data.get('error')}")
                return False
        else:
            print(f"[ERROR] Server返回错误: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("[ERROR] 无法连接到Server，请检查Server是否启动")
        return False
    except Exception as e:
        print(f"[ERROR] 清除统计数据失败: {e}")
        return False

def show_blacklist(config):
    """显示IP黑名单"""
    blacklist = config.get('ip_blacklist', {}).get('blocked_ips', [])
    
    print("\n" + "="*60)
    print("IP黑名单")
    print("="*60)
    
    if not blacklist:
        print("黑名单为空")
    else:
        for i, ip in enumerate(blacklist, 1):
            print(f"{i}. {ip}")
    
    print("="*60 + "\n")

def add_to_blacklist(config, ip):
    """添加IP到黑名单"""
    import re
    
    # 验证IP格式
    ip_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
    if not re.match(ip_pattern, ip):
        print(f"[ERROR] 无效的IP地址格式: {ip}")
        return False
    
    # 验证IP地址范围
    parts = ip.split('.')
    for part in parts:
        if int(part) > 255:
            print(f"[ERROR] 无效的IP地址: {ip}")
            return False
    
    if 'ip_blacklist' not in config:
        config['ip_blacklist'] = {'enabled': True, 'blocked_ips': []}
    
    if ip in config['ip_blacklist']['blocked_ips']:
        print(f"[WARNING] IP {ip} 已在黑名单中")
        return False
    
    config['ip_blacklist']['blocked_ips'].append(ip)
    if save_config(config):
        print(f"[SUCCESS] 已将 {ip} 添加到黑名单")
        print("[提示] 重启Server后生效")
        return True
    return False

def remove_from_blacklist(config, ip):
    """从黑名单移除IP"""
    if 'ip_blacklist' not in config or ip not in config['ip_blacklist']['blocked_ips']:
        print(f"[WARNING] IP {ip} 不在黑名单中")
        return False
    
    config['ip_blacklist']['blocked_ips'].remove(ip)
    if save_config(config):
        print(f"[SUCCESS] 已将 {ip} 从黑名单移除")
        print("[提示] 重启Server后生效")
        return True
    return False

def main():
    parser = argparse.ArgumentParser(
        description='AI模型和系统管理工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
使用示例:
  模型管理:
    %(prog)s list                          列出所有模型
    %(prog)s show openai                   查看模型详情
    %(prog)s enable openai                 启用模型
    %(prog)s disable openai                禁用模型
    %(prog)s set-default openai            设置默认模型
    %(prog)s set-key openai sk-xxx         设置API密钥
    %(prog)s update openai api_url https://api.openai.com/v1/chat/completions
    %(prog)s add mymodel "My Model" https://api.xxx.com/v1/chat/completions gpt-4
    %(prog)s delete mymodel                删除模型
  
  IP限流管理:
    %(prog)s rate-limit                    查看IP限流配置
    %(prog)s set-rate-limit enabled true   启用/禁用限流
    %(prog)s set-rate-limit max_requests_per_ip 20  设置最大请求数
    %(prog)s set-rate-limit time_window_hours 4     设置时间窗口
  
  IP统计与黑名单:
    %(prog)s ip-stats                      查看IP访问统计
    %(prog)s clear-stats                   清除所有IP统计
    %(prog)s clear-stats 192.168.1.100     清除指定IP统计
    %(prog)s blacklist                     查看IP黑名单
    %(prog)s add-blacklist 1.2.3.4         添加IP到黑名单
    %(prog)s remove-blacklist 1.2.3.4      从黑名单移除IP
        '''
    )
    
    parser.add_argument('action', 
                       choices=['list', 'show', 'enable', 'disable', 'set-default', 
                               'set-key', 'update', 'add', 'delete', 
                               'rate-limit', 'set-rate-limit',
                               'ip-stats', 'clear-stats', 'blacklist', 
                               'add-blacklist', 'remove-blacklist', 'full-analysis-model'],
                       help='操作类型')
    parser.add_argument('model_key', nargs='?', help='模型标识或配置字段')
    parser.add_argument('value', nargs='?', help='配置值')
    parser.add_argument('extra', nargs='*', help='额外参数')
    
    args = parser.parse_args()
    
    # 加载配置
    config = load_config()
    if not config:
        sys.exit(1)
    
    # 执行操作
    if args.action == 'list':
        list_models(config)
    
    elif args.action == 'show':
        if not args.model_key:
            print("[ERROR] 请指定模型标识")
            sys.exit(1)
        show_model(config, args.model_key)
    
    elif args.action == 'enable':
        if not args.model_key:
            print("[ERROR] 请指定模型标识")
            sys.exit(1)
        enable_model(config, args.model_key)
    
    elif args.action == 'disable':
        if not args.model_key:
            print("[ERROR] 请指定模型标识")
            sys.exit(1)
        disable_model(config, args.model_key)
    
    elif args.action == 'set-default':
        if not args.model_key:
            print("[ERROR] 请指定模型标识")
            sys.exit(1)
        set_default(config, args.model_key)
    
    elif args.action == 'set-key':
        if not args.model_key or not args.value:
            print("[ERROR] 请指定模型标识和API密钥")
            print(f"用法: python {sys.argv[0]} set-key <model_key> <api_key>")
            sys.exit(1)
        update_api_key(config, args.model_key, args.value)
    
    elif args.action == 'update':
        if not args.model_key or not args.value:
            print("[ERROR] 请指定模型标识和配置值")
            print(f"用法: python {sys.argv[0]} update <model_key> <field> <value>")
            sys.exit(1)
        if len(args.extra) < 1:
            print("[ERROR] update命令需要3个参数: model_key, field, value")
            sys.exit(1)
        update_config(config, args.model_key, args.value, args.extra[0])
    
    elif args.action == 'add':
        if not args.model_key or not args.value:
            print("[ERROR] 请指定模型标识和名称")
            print(f"用法: python {sys.argv[0]} add <model_key> <name> <api_url> <model_name>")
            sys.exit(1)
        if len(args.extra) < 2:
            print("[ERROR] add命令需要4个参数: model_key, name, api_url, model_name")
            sys.exit(1)
        add_model(config, args.model_key, args.value, args.extra[0], args.extra[1])
    
    elif args.action == 'delete':
        if not args.model_key:
            print("[ERROR] 请指定模型标识")
            sys.exit(1)
        confirm = input(f"确定要删除模型 '{args.model_key}' 吗？(y/n): ")
        if confirm.lower() == 'y':
            delete_model(config, args.model_key)
        else:
            print("已取消删除")
    
    elif args.action == 'rate-limit':
        show_rate_limit(config)
    
    elif args.action == 'set-rate-limit':
        if not args.model_key or not args.value:
            print("[ERROR] 请指定配置字段和值")
            print(f"用法: python {sys.argv[0]} set-rate-limit <field> <value>")
            print("允许的字段: enabled, max_requests_per_ip, time_window_hours")
            sys.exit(1)
        set_rate_limit(config, args.model_key, args.value)
    
    elif args.action == 'ip-stats':
        show_ip_stats(config)
    
    elif args.action == 'clear-stats':
        clear_ip_stats(config, args.model_key)
    
    elif args.action == 'blacklist':
        show_blacklist(config)
    
    elif args.action == 'add-blacklist':
        if not args.model_key:
            print("[ERROR] 请指定IP地址")
            print(f"用法: python {sys.argv[0]} add-blacklist <ip_address>")
            sys.exit(1)
        add_to_blacklist(config, args.model_key)
    
    elif args.action == 'remove-blacklist':
        if not args.model_key:
            print("[ERROR] 请指定IP地址")
            print(f"用法: python {sys.argv[0]} remove-blacklist <ip_address>")
            sys.exit(1)
        remove_from_blacklist(config, args.model_key)
    
    elif args.action == 'full-analysis-model':
        if not args.model_key:
            show_full_analysis_model(config)
        else:
            set_full_analysis_model(config, args.model_key)

if __name__ == '__main__':
    main()