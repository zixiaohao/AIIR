#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CS架构 Server端 - 模块化AI分析版本
功能：
1. 接收Client发送的系统检查数据
2. 支持多AI模型的模块化分析
3. 将结果返回给Client
4. 将数据上传至对象存储

模型管理请使用 ai_manager.py 命令行工具
"""

import os
import json
import requests
import sys
from datetime import datetime, timedelta
from collections import defaultdict
from flask import Flask, request, jsonify

app = Flask(__name__)

# ================= Debug模式 =================
DEBUG_MODE = False

# 尝试导入可选依赖
try:
    from boto3.session import Session
    from aescode import AESCoder
    BOTO3_AVAILABLE = True
except ImportError as e:
    print(f"[WARNING] 可选依赖未安装: {e}")
    print("[WARNING] 对象存储功能将不可用")
    BOTO3_AVAILABLE = False

# ================= IP限流 =================
class RateLimiter:
    """IP请求限流器"""
    
    def __init__(self):
        self.requests = defaultdict(list)  # IP -> [timestamp, ...]
        self.total_requests = defaultdict(int)  # IP -> 总请求数（历史累计）
        self.blocked_ips = set()  # 黑名单IP集合
        self._load_blacklist()
    
    def _load_blacklist(self):
        """加载IP黑名单"""
        blacklist_config = config.get('ip_blacklist', {})
        if blacklist_config.get('enabled', False):
            blocked = blacklist_config.get('blocked_ips', [])
            self.blocked_ips.update(blocked)
    
    def is_blacklisted(self, ip):
        """检查IP是否在黑名单中"""
        return ip in self.blocked_ips
    
    def add_to_blacklist(self, ip):
        """添加IP到黑名单"""
        self.blocked_ips.add(ip)
        # 更新配置文件
        if 'ip_blacklist' not in config:
            config['ip_blacklist'] = {'enabled': True, 'blocked_ips': []}
        if ip not in config['ip_blacklist']['blocked_ips']:
            config['ip_blacklist']['blocked_ips'].append(ip)
            save_config(config)
    
    def remove_from_blacklist(self, ip):
        """从黑名单移除IP"""
        if ip in self.blocked_ips:
            self.blocked_ips.remove(ip)
            # 更新配置文件
            if 'ip_blacklist' in config and ip in config['ip_blacklist']['blocked_ips']:
                config['ip_blacklist']['blocked_ips'].remove(ip)
                save_config(config)
    
    def is_allowed(self, ip, max_requests, time_window_hours):
        """检查是否允许请求"""
        # 先检查黑名单
        if self.is_blacklisted(ip):
            return False
        
        # 使用全局config（由reload_config刷新），避免每次请求都读磁盘
        if not config.get('rate_limit', {}).get('enabled', False):
            self.total_requests[ip] += 1
            return True
        
        # 使用全局配置
        max_requests = config['rate_limit'].get('max_requests_per_ip', max_requests)
        time_window_hours = config['rate_limit'].get('time_window_hours', time_window_hours)
        
        now = datetime.now()
        window_start = now - timedelta(hours=time_window_hours)
        
        # 清理过期的请求记录
        self.requests[ip] = [ts for ts in self.requests[ip] if ts > window_start]
        
        # 检查是否超过限制
        if len(self.requests[ip]) >= max_requests:
            return False
        
        # 记录本次请求
        self.requests[ip].append(now)
        self.total_requests[ip] += 1
        return True
    
    def get_remaining_requests(self, ip, max_requests, time_window_hours):
        """获取剩余请求次数"""
        if not config.get('rate_limit', {}).get('enabled', False):
            return max_requests
        
        now = datetime.now()
        window_start = now - timedelta(hours=time_window_hours)
        
        # 清理过期的请求记录
        self.requests[ip] = [ts for ts in self.requests[ip] if ts > window_start]
        
        return max(0, max_requests - len(self.requests[ip]))
    
    def get_ip_stats(self, ip=None):
        """获取IP统计信息"""
        if ip:
            # 获取单个IP的统计
            return {
                'ip': ip,
                'total_requests': self.total_requests.get(ip, 0),
                'current_window_requests': len(self.requests.get(ip, [])),
                'is_blacklisted': self.is_blacklisted(ip)
            }
        else:
            # 获取所有IP的统计
            stats = {}
            all_ips = set(list(self.requests.keys()) + list(self.total_requests.keys()) + list(self.blocked_ips))
            for ip_addr in all_ips:
                stats[ip_addr] = {
                    'total_requests': self.total_requests.get(ip_addr, 0),
                    'current_window_requests': len(self.requests.get(ip_addr, [])),
                    'is_blacklisted': self.is_blacklisted(ip_addr)
                }
            return stats
    
    def clear_stats(self, ip=None):
        """清除统计数据"""
        if ip:
            # 清除单个IP的统计
            if ip in self.requests:
                del self.requests[ip]
            if ip in self.total_requests:
                del self.total_requests[ip]
        else:
            # 清除所有IP的统计
            self.requests.clear()
            self.total_requests.clear()

# ================= 配置加载 =================
# 使用绝对路径加载配置文件
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.json")

def load_config():
    """加载配置文件"""
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"[ERROR] 加载配置文件失败: {e}")
        print(f"[INFO] 配置文件路径: {CONFIG_FILE}")
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

# 加载配置
config = load_config()
if not config:
    print("[ERROR] 无法加载配置文件，程序退出")
    exit(1)

# 初始化AES解密（如果可用）
if BOTO3_AVAILABLE:
    try:
        aes = AESCoder()
    except Exception as e:
        print(f"[WARNING] AES初始化失败: {e}")
        aes = None
else:
    aes = None

# 创建IP限流器实例
rate_limiter = RateLimiter()

# 初始化S3客户端（如果可用）
def init_s3_client():
    """初始化对象存储客户端"""
    if not BOTO3_AVAILABLE:
        return None
    
    try:
        obj_config = config['object_storage']
        access_key = obj_config['access_key']
        secret_key = aes.decrypt(obj_config['secret_key_encrypted'].encode())
        endpoint = obj_config['endpoint']
        
        session = Session(access_key, secret_key)
        return session.client('s3', endpoint_url=endpoint)
    except Exception as e:
        print(f"[WARNING] S3客户端初始化失败: {e}")
        return None

s3_client = init_s3_client()

# ================= AI模型管理 =================
class AIModelManager:
    """AI模型管理器"""
    
    def __init__(self, config):
        self.config = config
        self.models = config['ai_models']['models']
        self.default_model = config['ai_models']['default']
    
    def reload_config(self):
        """重新加载配置"""
        global config
        config = load_config()
        if config:
            self.config = config
            self.models = config['ai_models']['models']
            self.default_model = config['ai_models']['default']
            return True
        return False
    
    def get_enabled_models(self):
        """获取所有启用的模型"""
        return {k: v for k, v in self.models.items() if v.get('enabled', False)}
    
    def get_model(self, model_key=None):
        """获取指定模型配置"""
        if model_key is None:
            model_key = self.default_model
        return self.models.get(model_key)

ai_manager = AIModelManager(config)

# ================= AI分析模块 =================
def call_openai_compatible_api(model_config, system_prompt, user_content):
    """
    调用OPENAI兼容接口
    支持: OpenAI, DeepSeek, Moonshot, 通义千问, 智谱等
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {model_config['api_key']}"
    }
    
    payload = {
        "model": model_config['model_name'],
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ],
        "temperature": model_config.get('temperature', 0.1),
        "max_tokens": model_config.get('max_tokens', 4096),
        "stream": False
    }
    
    response = requests.post(
        model_config['api_url'],
        headers=headers,
        json=payload,
        timeout=120
    )
    
    # 检查HTTP状态码
    if response.status_code != 200:
        error_text = response.text[:500] if response.text else "Unknown error"
        
        # Debug模式：输出完整请求报文
        if DEBUG_MODE:
            print("\n" + "="*80)
            print("[DEBUG] API请求失败 - 详细信息")
            print("="*80)
            print(f"请求URL: {model_config['api_url']}")
            print(f"HTTP状态码: {response.status_code}")
            print(f"请求头: {json.dumps(headers, indent=2, ensure_ascii=False)}")
            print(f"请求体: {json.dumps(payload, indent=2, ensure_ascii=False)}")
            print(f"响应内容: {error_text}")
            print("="*80 + "\n")
        
        raise Exception(f"{response.status_code} Client Error: {error_text} for url: {model_config['api_url']}")
    
    result = response.json()
    
    # 检查API响应格式
    if 'choices' not in result or len(result['choices']) == 0:
        # Debug模式：输出响应格式错误
        if DEBUG_MODE:
            print("\n" + "="*80)
            print("[DEBUG] API响应格式错误 - 详细信息")
            print("="*80)
            print(f"请求URL: {model_config['api_url']}")
            print(f"响应内容: {json.dumps(result, indent=2, ensure_ascii=False)}")
            print("="*80 + "\n")
        
        raise Exception(f"API响应格式错误: {json.dumps(result, ensure_ascii=False)[:200]}")
    
    return result['choices'][0]['message']['content']

def call_claude_api(model_config, system_prompt, user_content):
    """调用Claude API (Anthropic)"""
    headers = {
        "Content-Type": "application/json",
        "x-api-key": model_config['api_key'],
        "anthropic-version": "2023-06-01"
    }
    
    payload = {
        "model": model_config['model_name'],
        "max_tokens": model_config.get('max_tokens', 4096),
        "system": system_prompt,
        "messages": [
            {"role": "user", "content": user_content}
        ]
    }
    
    response = requests.post(
        model_config['api_url'],
        headers=headers,
        json=payload,
        timeout=120
    )
    
    # 检查HTTP状态码
    if response.status_code != 200:
        error_text = response.text[:500] if response.text else "Unknown error"
        
        # Debug模式：输出完整请求报文
        if DEBUG_MODE:
            print("\n" + "="*80)
            print("[DEBUG] Claude API请求失败 - 详细信息")
            print("="*80)
            print(f"请求URL: {model_config['api_url']}")
            print(f"HTTP状态码: {response.status_code}")
            print(f"请求头: {json.dumps(headers, indent=2, ensure_ascii=False)}")
            print(f"请求体: {json.dumps(payload, indent=2, ensure_ascii=False)}")
            print(f"响应内容: {error_text}")
            print("="*80 + "\n")
        
        raise Exception(f"{response.status_code} Client Error: {error_text} for url: {model_config['api_url']}")
    
    result = response.json()
    
    # 检查API响应格式
    if 'content' not in result or len(result['content']) == 0:
        # Debug模式：输出响应格式错误
        if DEBUG_MODE:
            print("\n" + "="*80)
            print("[DEBUG] Claude API响应格式错误 - 详细信息")
            print("="*80)
            print(f"请求URL: {model_config['api_url']}")
            print(f"响应内容: {json.dumps(result, indent=2, ensure_ascii=False)}")
            print("="*80 + "\n")
        
        raise Exception(f"API响应格式错误: {json.dumps(result, ensure_ascii=False)[:200]}")
    
    return result['content'][0]['text']

def call_ai_api(model_key, system_prompt, user_content, raise_error=False):
    """
    统一的AI API调用接口
    自动识别模型类型并调用相应的API
    
    Args:
        model_key: 模型标识
        system_prompt: 系统提示词
        user_content: 用户内容
        raise_error: 是否在失败时抛出异常（True）或返回错误字符串（False）
    """
    model_config = ai_manager.get_model(model_key)
    if not model_config:
        error_msg = f"错误: 未找到模型 {model_key}"
        if raise_error:
            raise Exception(error_msg)
        return error_msg
    
    if not model_config.get('enabled', False):
        error_msg = f"错误: 模型 {model_config['name']} 未启用"
        if raise_error:
            raise Exception(error_msg)
        return error_msg
    
    if not model_config.get('api_key'):
        error_msg = f"错误: 模型 {model_config['name']} 未配置API密钥"
        if raise_error:
            raise Exception(error_msg)
        return error_msg
    
    # Claude使用不同的API格式
    if model_key == 'claude':
        return call_claude_api(model_config, system_prompt, user_content)
    else:
        # 其他模型使用OPENAI兼容接口
        return call_openai_compatible_api(model_config, system_prompt, user_content)

# ================= 分析功能 =================
def get_whitelist_prompt():
    """生成白名单提示词"""
    if not config['analysis']['enable_whitelist']:
        return ""
    
    keywords = config['analysis']['whitelist_keywords']
    return f"""
【重要：分析白名单 - 请忽略以下已知安全项】
1. 本次应急响应工具：
   - 进程/文件名: {', '.join(keywords[:4])}
   - 路径特征: 通常位于 /tmp 目录或 /root 下，这是正常的应急工具运行行为，非恶意。
2. 安全软件/云代理：
   - {', '.join(keywords[4:])}
   - 以上进程属于合法的云安全监控组件，请勿将其识别为恶意进程、挖矿或木马。
3. 判定标准：
   - 仅当上述进程出现明显异常行为（如连接矿池、修改 /etc/shadow）时才需标记，否则视为安全。
"""

def analyze_section(section_title, content_block, model_key=None, platform="linux"):
    """分析单个模块"""
    if len(content_block.strip()) < 10:
        return None
    
    whitelist = get_whitelist_prompt()
    
    # 根据平台选择不同的分析专家角色
    if platform == "windows":
        expert_role = "你是一名Windows安全专家"
    else:
        expert_role = "你是一名Linux安全专家"
    
    system_prompt = f"""{expert_role}。请分析提交的[{section_title}]日志片段。{whitelist} 

分析要求：
1. 如果没有异常，请直接回答"无异常"
2. 如果发现可疑点（且不在白名单内），请按以下格式输出：
   - 风险等级：[高/中/低]
   - 可疑现象：描述发现的问题
   - 相关证据：具体的日志内容
   - 处置建议：建议采取的措施

注意：不要使用"安全专家"、"分析师"等自称，直接给出分析结果。"""
    
    result = call_ai_api(model_key, system_prompt, content_block)
    
    # 保留所有分析结果，包括"无异常"的详细分析
    return f"【模块：{section_title}】\n{result}\n"

def detect_platform(log_content):
    """检测日志内容来自哪个平台"""
    # Windows特征
    windows_indicators = [
        'wmic', 'powershell', 'cmd.exe', 'reg query', 'wevtutil',
        'HKLM\\', 'HKCU\\', 'C:\\Windows', 'C:\\inetpub',
        'Administrator', 'SYSTEM', 'Winlogon', 'IFEO'
    ]
    
    # Linux特征
    linux_indicators = [
        '/etc/passwd', '/etc/shadow', '/tmp', '/root',
        'uname -a', 'iptables', 'systemctl', 'crontab',
        'ps aux', 'netstat', '/var/log'
    ]
    
    windows_score = sum(1 for indicator in windows_indicators if indicator.lower() in log_content.lower())
    linux_score = sum(1 for indicator in linux_indicators if indicator.lower() in log_content.lower())
    
    if windows_score > linux_score:
        return "windows"
    else:
        return "linux"

def full_analysis(log_content, hostname, ip_info, model_key=None):
    """
    完整分析流程 - 模块化分析+汇总
    1. 逐个模块进行AI分析
    2. 收集各模块分析结果
    3. 将汇总结果发送给AI进行最终研判
    """
    # 使用默认模型
    if model_key is None:
        model_key = ai_manager.default_model
    
    # 检测平台类型
    platform = detect_platform(log_content)
    print(f"[*] 检测到平台类型: {platform}")
    print(f"[*] 使用智能分析系统进行检测")
    
    # 按模块分割内容
    lines = log_content.split('\n')
    sections = []
    current_section = None
    current_content = []
    
    for line in lines:
        if line.startswith('## '):
            if current_section:
                sections.append((current_section, '\n'.join(current_content)))
            current_section = line[3:].strip()
            current_content = []
        else:
            current_content.append(line)
    
    if current_section:
        sections.append((current_section, '\n'.join(current_content)))
    
    # ========== 第一步：逐个模块进行AI分析 ==========
    print(f"[*] 开始逐个模块分析，共 {len(sections)} 个模块...")
    section_analyses = []
    analysis_count = 0
    
    for title, content in sections:
        analysis_count += 1
        print(f"[*] 正在分析模块 [{analysis_count}/{len(sections)}]: {title}")
        
        result = analyze_section(title, content, model_key, platform)
        if result:
            section_analyses.append(result)
            print(f"    -> 发现异常")
        else:
            print(f"    -> 无异常")
    
    # 汇总各模块分析结果
    if section_analyses:
        full_summary = '\n'.join(section_analyses)
        print(f"[*] 共发现 {len(section_analyses)} 个模块存在异常")
    else:
        full_summary = "各项基础检查均未发现明显异常指标。"
        print(f"[*] 所有模块均无异常")
    
    # ========== 第二步：将汇总结果发送给AI进行最终研判 ==========
    print(f"[*] 正在进行最终综合研判...")
    
    whitelist = get_whitelist_prompt()
    
    # 根据平台选择不同的专家角色
    if platform == "windows":
        expert_role = "你是一名高级Windows安全应急响应专家"
    else:
        expert_role = "你是一名高级Linux安全应急响应专家"
    
    final_system_prompt = f"""{expert_role}。我将提供一份系统安全检查的分项分析汇总。请基于这些信息，进行最终的综合安全研判。

{whitelist}

要求：
1. 给出整体安全评分（百分制，100分为完全安全，分数越低安全性越差：90+优秀 70-89良好 50-69一般 50以下危险）
2. 按风险等级（高/中/低）列出发现的问题
3. 给出具体的处置建议和修复方案
4. 输出格式为Markdown

注意：
- 忽略白名单中的安全项
- 重点关注高危漏洞和异常行为
- 提供可操作的修复建议"""
    
    meta_info = f"""## 检测目标信息
- 主机名: {hostname}
- IP地址: {ip_info}
- 检测平台: {platform}
- 检测时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- 分析模块数: {len(sections)}
- 异常模块数: {len(section_analyses)}"""
    
    final_content = f"""{meta_info}

## 各模块分析结果

{full_summary}

请基于以上各模块的分析结果，给出最终的综合安全研判报告。"""
    
    final_report = call_ai_api(model_key, final_system_prompt, final_content)
    
    # 生成完整报告
    model_info = ai_manager.get_model(model_key)
    report = f"""# 安全应急响应分析报告

{meta_info}

---

## 综合安全研判

{final_report}

---

## 各模块详细分析

{full_summary}
"""
    
    print(f"[*] 分析完成")
    
    return report

# ================= 对象存储 =================
def upload_to_s3(content, filename):
    """上传内容到对象存储"""
    # 优先使用S3客户端
    if s3_client:
        try:
            bucket = config['object_storage']['bucket']
            prefix = config['object_storage']['prefix']
            key = f"{prefix}{filename}"
            
            s3_client.put_object(
                Bucket=bucket,
                Key=key,
                Body=content.encode('utf-8')
            )
            print(f"[*] 文件已上传到S3: {key}")
            return True, f"上传成功: {key}"
        except Exception as e:
            print(f"[WARNING] S3上传失败，尝试本地存储: {str(e)}")
    
    # S3不可用时，使用本地存储作为备选方案
    try:
        # 创建本地存储目录（使用绝对路径）
        import os.path
        script_dir = os.path.dirname(os.path.abspath(__file__))
        local_storage_dir = os.path.join(script_dir, "uploaded_files")
        
        if not os.path.exists(local_storage_dir):
            os.makedirs(local_storage_dir)
            print(f"[*] 创建本地存储目录: {local_storage_dir}")
        
        # 保存文件到本地
        local_file_path = os.path.join(local_storage_dir, filename)
        with open(local_file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"[*] 文件已保存到本地: {local_file_path}")
        return True, f"上传成功（本地存储）: {filename}"
    except Exception as e:
        print(f"[ERROR] 本地存储也失败: {str(e)}")
        return False, f"上传失败: {str(e)}"

# ================= API路由 =================
@app.route('/health', methods=['GET'])
def health_check():
    """健康检查接口（不受IP限流限制）"""
    ai_manager.reload_config()
    enabled_models = list(ai_manager.get_enabled_models().keys())
    return jsonify({
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "default_model": ai_manager.default_model,
        "enabled_models": enabled_models,
        "server_version": "3.0"
    })

@app.route('/attack_patterns', methods=['GET'])
def get_attack_patterns():
    """获取攻击特征库接口"""
    try:
        pattern_file = "attack_patterns.json"
        if os.path.exists(pattern_file):
            with open(pattern_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # 只返回patterns子对象，而不是整个文件
            patterns = data.get('patterns', {})
            return jsonify({
                "success": True,
                "patterns": patterns
            })
        else:
            return jsonify({
                "success": False,
                "error": "特征库文件不存在"
            }), 404
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/models', methods=['GET'])
def list_models():
    """列出所有AI模型（只读）"""
    # 重新加载配置以获取最新状态
    ai_manager.reload_config()
    models_info = {}
    for key, model in config['ai_models']['models'].items():
        models_info[key] = {
            "name": model['name'],
            "enabled": model.get('enabled', False),
            "model_name": model['model_name'],
            "has_api_key": bool(model.get('api_key'))
        }
    
    return jsonify({
        "default": ai_manager.default_model,
        "models": models_info,
        "note": "模型管理请使用 ai_manager.py 命令行工具"
    })

@app.route('/analyze', methods=['POST'])
def analyze():
    """
    接收Client数据并进行分析
    
    请求体JSON格式:
    {
        "ticket_id": "工单号",
        "hostname": "主机名",
        "ip_info": "IP信息",
        "log_content": "日志内容",
        "model": "可选，指定使用的AI模型"
    }
    """
    try:
        # 重新加载配置以获取最新模型设置
        ai_manager.reload_config()
        
        # IP限流检查
        client_ip = request.remote_addr
        if config.get('rate_limit', {}).get('enabled', False):
            max_requests = config['rate_limit'].get('max_requests_per_ip', 10)
            time_window = config['rate_limit'].get('time_window_hours', 2)
            
            if not rate_limiter.is_allowed(client_ip, max_requests, time_window):
                remaining = rate_limiter.get_remaining_requests(client_ip, max_requests, time_window)
                return jsonify({
                    "success": False,
                    "error": f"请求频率超限，同一IP在{time_window}小时内最多请求{max_requests}次",
                    "remaining_requests": remaining,
                    "time_window_hours": time_window
                }), 429
        
        data = request.get_json()
        
        if not data:
            return jsonify({"success": False, "error": "无效的请求数据"}), 400
        
        ticket_id = data.get('ticket_id', 'unknown')
        hostname = data.get('hostname', 'unknown')
        ip_info = data.get('ip_info', 'unknown')
        log_content = data.get('log_content', '')
        model_key = data.get('model')  # 可选参数
        
        if not log_content:
            return jsonify({"success": False, "error": "日志内容为空"}), 400
        
        # 验证模型
        if model_key and model_key not in ai_manager.get_enabled_models():
            return jsonify({"success": False, "error": f"模型 {model_key} 未启用或不存在"}), 400
        
        # 生成文件名
        log_filename = f"{ticket_id}_{hostname}_log.md"
        analysis_filename = f"{ticket_id}_{hostname}_analysis_report.md"
        
        # 1. 上传原始日志到对象存储
        upload_success, upload_msg = upload_to_s3(log_content, log_filename)
        
        # 2. 进行AI分析
        actual_model = model_key or ai_manager.default_model
        print(f"[*] 开始分析工单 {ticket_id} - 主机 {hostname}")
        analysis_report = full_analysis(log_content, hostname, ip_info, actual_model)
        
        # 3. 上传分析报告到对象存储
        upload_to_s3(analysis_report, analysis_filename)
        
        # 4. 返回结果给Client
        return jsonify({
            "success": True,
            "ticket_id": ticket_id,
            "hostname": hostname,
            "analysis_report": analysis_report,
            "log_uploaded": upload_success,
            "log_filename": log_filename,
            "analysis_filename": analysis_filename
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/upload', methods=['POST'])
def upload_file():
    """直接上传文件接口"""
    try:
        data = request.get_json()
        filename = data.get('filename')
        content = data.get('content')
        
        if not filename or not content:
            return jsonify({"success": False, "error": "缺少文件名或内容"}), 400
        
        success, msg = upload_to_s3(content, filename)
        return jsonify({"success": success, "message": msg})
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/analyze_section', methods=['POST'])
def analyze_section_api():
    """
    分析单个模块（用于分批分析）
    
    请求体JSON格式:
    {
        "section_title": "模块标题",
        "section_content": "模块内容",
        "platform": "linux/windows",
        "model": "可选，指定使用的AI模型"
    }
    """
    try:
        ai_manager.reload_config()
        
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "无效的请求数据"}), 400
        
        section_title = data.get('section_title', '')
        section_content = data.get('section_content', '')
        platform = data.get('platform', 'linux')
        model_key = data.get('model')
        
        if not section_title or not section_content:
            return jsonify({"success": False, "error": "缺少模块标题或内容"}), 400
        
        # 验证模型
        if model_key and model_key not in ai_manager.get_enabled_models():
            return jsonify({"success": False, "error": f"模型 {model_key} 未启用或不存在"}), 400
        
        actual_model = model_key or ai_manager.default_model
        
        # 分析单个模块
        result = analyze_section(section_title, section_content, actual_model, platform)
        
        return jsonify({
            "success": True,
            "section_title": section_title,
            "analysis_result": result,
            "model_used": actual_model
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/analyze_summary', methods=['POST'])
def analyze_summary_api():
    """
    汇总分析（接收多个模块的分析结果进行最终研判）
    
    请求体JSON格式:
    {
        "ticket_id": "工单号",
        "hostname": "主机名",
        "ip_info": "IP信息",
        "platform": "linux/windows",
        "section_results": ["模块1分析结果", "模块2分析结果", ...],
        "model": "可选，指定使用的AI模型"
    }
    """
    try:
        ai_manager.reload_config()
        
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "无效的请求数据"}), 400
        
        ticket_id = data.get('ticket_id', 'unknown')
        hostname = data.get('hostname', 'unknown')
        ip_info = data.get('ip_info', 'unknown')
        platform = data.get('platform', 'linux')
        section_results = data.get('section_results', [])
        model_key = data.get('model')
        
        # 允许空的section_results（所有模块都无异常的情况）
        if section_results is None:
            section_results = []
        
        # 验证模型
        if model_key and model_key not in ai_manager.get_enabled_models():
            return jsonify({"success": False, "error": f"模型 {model_key} 未启用或不存在"}), 400
        
        actual_model = model_key or ai_manager.default_model
        
        # 汇总所有分析结果（保留所有详细分析，包括无异常的）
        full_summary = '\n'.join([r for r in section_results if r])
        if not full_summary:
            full_summary = "各项基础检查均未发现明显异常指标。"
        
        # 最终汇总研判
        whitelist = get_whitelist_prompt()
        
        if platform == "windows":
            expert_role = "你是一名高级Windows安全应急响应专家"
        else:
            expert_role = "你是一名高级Linux安全应急响应专家"
        
        final_system_prompt = f"""{expert_role}。我将提供一份自动化巡检分项分析汇总。请基于这些汇总信息，进行最终的综合研判。{whitelist} 
要求：1. 给出整体安全评分（百分制，100分为完全安全，分数越低安全性越差）。2. 按优先级列出威胁。3. 给出处置建议。4. 输出格式为Markdown。"""
        
        meta_info = f"主机名: {hostname}, IP: {ip_info}, 平台: {platform}, 分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        final_content = f"主机元数据：{meta_info}\n\n分项分析汇总如下：\n{full_summary}"
        
        final_report = call_ai_api(actual_model, final_system_prompt, final_content)
        
        # 生成完整报告
        report = f"""# 安全应急响应分析报告
生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
检测平台: {platform}
----------------------------------------
{final_report}
----------------------------------------
## 原始异常汇总数据
{full_summary}
"""
        
        # 上传到对象存储
        log_filename = f"{ticket_id}_{hostname}_log.md"
        analysis_filename = f"{ticket_id}_{hostname}_analysis_report.md"
        upload_to_s3(full_summary, log_filename)
        upload_to_s3(report, analysis_filename)
        
        return jsonify({
            "success": True,
            "ticket_id": ticket_id,
            "hostname": hostname,
            "platform": platform,
            "analysis_report": report,
            "log_uploaded": True,
            "log_filename": log_filename,
            "analysis_filename": analysis_filename
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ================= IP管理API =================
@app.route('/ip_stats', methods=['GET'])
def get_ip_stats():
    """获取IP统计信息"""
    try:
        ip = request.args.get('ip')
        stats = rate_limiter.get_ip_stats(ip)
        return jsonify({
            "success": True,
            "stats": stats,
            "blacklist": list(rate_limiter.blocked_ips)
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/ip_stats/clear', methods=['POST'])
def clear_ip_stats():
    """清除IP统计数据"""
    try:
        data = request.get_json() or {}
        ip = data.get('ip')
        rate_limiter.clear_stats(ip)
        
        if ip:
            message = f"已清除IP {ip} 的统计数据"
        else:
            message = "已清除所有IP的统计数据"
        
        return jsonify({
            "success": True,
            "message": message
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/blacklist/add', methods=['POST'])
def add_to_blacklist():
    """添加IP到黑名单"""
    try:
        data = request.get_json()
        if not data or 'ip' not in data:
            return jsonify({
                "success": False,
                "error": "请提供IP地址"
            }), 400
        
        ip = data['ip']
        
        # 验证IP格式
        import re
        ip_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
        if not re.match(ip_pattern, ip):
            return jsonify({
                "success": False,
                "error": f"无效的IP地址格式: {ip}"
            }), 400
        
        # 验证IP地址范围
        parts = ip.split('.')
        for part in parts:
            if int(part) > 255:
                return jsonify({
                    "success": False,
                    "error": f"无效的IP地址: {ip}"
                }), 400
        
        if rate_limiter.is_blacklisted(ip):
            return jsonify({
                "success": False,
                "error": f"IP {ip} 已在黑名单中"
            }), 400
        
        rate_limiter.add_to_blacklist(ip)
        
        return jsonify({
            "success": True,
            "message": f"已将 {ip} 添加到黑名单"
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/blacklist/remove', methods=['POST'])
def remove_from_blacklist():
    """从黑名单移除IP"""
    try:
        data = request.get_json()
        if not data or 'ip' not in data:
            return jsonify({
                "success": False,
                "error": "请提供IP地址"
            }), 400
        
        ip = data['ip']
        
        if not rate_limiter.is_blacklisted(ip):
            return jsonify({
                "success": False,
                "error": f"IP {ip} 不在黑名单中"
            }), 400
        
        rate_limiter.remove_from_blacklist(ip)
        
        return jsonify({
            "success": True,
            "message": f"已将 {ip} 从黑名单移除"
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/blacklist', methods=['GET'])
def get_blacklist():
    """获取黑名单列表"""
    try:
        blacklist = list(rate_limiter.blocked_ips)
        return jsonify({
            "success": True,
            "blacklist": blacklist
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

# ================= 一次性分析接口 =================
@app.route('/analyze_with_actions', methods=['POST'])
def analyze_with_actions():
    """
    一次性分析接口 - 含自动操作命令（用于gaint版本客户端）
    除了分析报告外，还会让AI输出可执行的修复命令
    
    请求体JSON格式:
    {
        "ticket_id": "工单号",
        "hostname": "主机名",
        "ip_info": "IP信息",
        "platform": "linux/windows",
        "log_content": "完整的日志内容",
        "model": "可选，指定使用的AI模型"
    }
    
    响应格式:
    {
        "success": true,
        "analysis_report": "...",
        "actions": [...],
        "model_used": "..."
    }
    """
    try:
        ai_manager.reload_config()
        
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "无效的请求数据"}), 400
        
        ticket_id = data.get('ticket_id', 'unknown')
        hostname = data.get('hostname', 'unknown')
        ip_info = data.get('ip_info', 'unknown')
        platform = data.get('platform', 'linux')
        log_content = data.get('log_content', '')
        model_key = data.get('model')
        
        if not log_content:
            return jsonify({"success": False, "error": "日志内容为空"}), 400
        
        # 验证模型
        if model_key and model_key not in ai_manager.get_enabled_models():
            return jsonify({"success": False, "error": f"模型 {model_key} 未启用或不存在"}), 400
        
        actual_model = model_key or config['ai_models'].get('full_analysis_model', ai_manager.default_model)
        
        # 带动作增强的分析
        analysis_result = analyze_with_actions_content(log_content, hostname, ip_info, actual_model)
        
        analysis_report = analysis_result.get('report', '')
        actions = analysis_result.get('actions', [])
        
        # 上传到对象存储
        log_filename = f"{ticket_id}_{hostname}_log.md"
        analysis_filename = f"{ticket_id}_{hostname}_analysis_report.md"
        upload_to_s3(log_content, log_filename)
        upload_to_s3(analysis_report, analysis_filename)
        
        return jsonify({
            "success": True,
            "ticket_id": ticket_id,
            "hostname": hostname,
            "platform": platform,
            "analysis_report": analysis_report,
            "actions": actions,
            "model_used": actual_model,
            "log_uploaded": True,
            "log_filename": log_filename,
            "analysis_filename": analysis_filename
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/analyze_full', methods=['POST'])
def analyze_full():
    """
    一次性分析接口（用于gaint版本客户端）
    使用用户指定的大模型一次性分析所有数据
    
    请求体JSON格式:
    {
        "ticket_id": "工单号",
        "hostname": "主机名",
        "ip_info": "IP信息",
        "platform": "linux/windows",
        "log_content": "完整的日志内容",
        "model": "可选，指定使用的AI模型"
    }
    """
    try:
        ai_manager.reload_config()
        
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "无效的请求数据"}), 400
        
        ticket_id = data.get('ticket_id', 'unknown')
        hostname = data.get('hostname', 'unknown')
        ip_info = data.get('ip_info', 'unknown')
        platform = data.get('platform', 'linux')
        log_content = data.get('log_content', '')
        model_key = data.get('model')  # 用户指定的模型
        
        if not log_content:
            return jsonify({"success": False, "error": "日志内容为空"}), 400
        
        # 验证模型
        if model_key and model_key not in ai_manager.get_enabled_models():
            return jsonify({"success": False, "error": f"模型 {model_key} 未启用或不存在"}), 400
        
        # 使用用户指定的模型或full_analysis_model（独立配置）
        actual_model = model_key or config['ai_models'].get('full_analysis_model', ai_manager.default_model)
        
        # 一次性分析所有数据（不分段）
        analysis_report = analyze_full_content(log_content, hostname, ip_info, actual_model)
        
        # 上传到对象存储
        log_filename = f"{ticket_id}_{hostname}_log.md"
        analysis_filename = f"{ticket_id}_{hostname}_analysis_report.md"
        upload_to_s3(log_content, log_filename)
        upload_to_s3(analysis_report, analysis_filename)
        
        return jsonify({
            "success": True,
            "ticket_id": ticket_id,
            "hostname": hostname,
            "platform": platform,
            "analysis_report": analysis_report,
            "model_used": actual_model,
            "log_uploaded": True,
            "log_filename": log_filename,
            "analysis_filename": analysis_filename
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

def parse_actions_from_report(report_text, platform):
    """
    从AI分析报告中解析出结构化的修复动作
    支持格式：
    1. JSON代码块：```json\n[{"command": "...", "description": "...", ...}]\n```
    2. 命令行格式：```bash/cmd/powershell\n...\n```
    """
    import re
    actions = []
    
    # 查找JSON格式的动作列表
    json_pattern = r'```json\s*\n(.*?)\n```'
    json_matches = re.findall(json_pattern, report_text, re.DOTALL)
    for json_str in json_matches:
        try:
            parsed = json.loads(json_str.strip())
            if isinstance(parsed, list):
                for item in parsed:
                    if isinstance(item, dict) and 'command' in item:
                        actions.append({
                            'command': item.get('command', ''),
                            'description': item.get('description', ''),
                            'risk_level': item.get('risk_level', 'medium'),
                            'category': item.get('category', 'general')
                        })
            elif isinstance(parsed, dict) and 'actions' in parsed:
                for item in parsed['actions']:
                    if isinstance(item, dict) and 'command' in item:
                        actions.append({
                            'command': item.get('command', ''),
                            'description': item.get('description', ''),
                            'risk_level': item.get('risk_level', 'medium'),
                            'category': item.get('category', 'general')
                        })
        except json.JSONDecodeError:
            pass
    
    # 如果没有找到JSON格式，尝试从命令行代码块解析
    if not actions:
        if platform == 'windows':
            cmd_patterns = [r'```cmd\s*\n(.*?)\n```', r'```powershell\s*\n(.*?)\n```', r'```batch\s*\n(.*?)\n```']
        else:
            cmd_patterns = [r'```bash\s*\n(.*?)\n```', r'```sh\s*\n(.*?)\n```', r'```shell\s*\n(.*?)\n```']
        
        for pattern in cmd_patterns:
            cmd_matches = re.findall(pattern, report_text, re.DOTALL)
            for block in cmd_matches:
                lines = block.strip().split('\n')
                for line in lines:
                    line = line.strip()
                    if line and not line.startswith('#') and not line.startswith('//') and not line.startswith('REM '):
                        actions.append({
                            'command': line,
                            'description': f"执行命令: {line[:80]}",
                            'risk_level': 'medium',
                            'category': 'general'
                        })
    
    # 去重（基于命令内容）
    seen_commands = set()
    unique_actions = []
    for action in actions:
        cmd = action['command'].strip()
        if cmd and cmd not in seen_commands:
            seen_commands.add(cmd)
            unique_actions.append(action)
    
    return unique_actions


def analyze_with_actions_content(log_content, hostname, ip_info, model_key):
    """
    带自动修复动作的分析
    除了生成安全报告外，还会让AI输出可执行的修复命令
    返回: {"report": "...", "actions": [...]}
    """
    # 检测平台类型
    platform = detect_platform(log_content)
    print(f"[*] 检测到平台类型: {platform}")
    print(f"[*] 使用模型: {model_key}")
    print(f"[*] 正在执行带自动修复动作的分析...")

    # 获取白名单
    whitelist = get_whitelist_prompt()

    # 根据平台选择不同的专家角色
    if platform == "windows":
        expert_role = "你是一名高级Windows安全应急响应专家"
        shell_hint = "PowerShell/cmd"
    else:
        expert_role = "你是一名高级Linux安全应急响应专家"
        shell_hint = "bash/sh"

    # 构建带自动修复动作的系统提示词
    system_prompt = f"""{expert_role}。请对以下系统安全日志进行全面分析，并给出可执行的修复命令。

{whitelist}

### 分析要求：
1. 给出整体安全评分（百分制，100分为完全安全，分数越低安全性越差：90+优秀 70-89良好 50-69一般 50以下危险）
2. 按风险等级（高危/中危/低危/正常）分类列出发现的问题
3. 对每个问题提供详细的处置建议和修复方案

### 自动修复动作输出要求：
在分析报告的末尾，请以JSON格式输出所有建议的修复操作，格式如下：

```json
[
  {{
    "command": "具体的修复命令",
    "description": "操作描述，说明为什么要执行此命令",
    "risk_level": "high/medium/low",
    "category": "process/user/network/file/service/config"
  }}
]
```

要求：
1. 每条命令必须是一个独立的、可直接在{shell_hint}中执行的命令
2. 命令应该是幂等的（多次执行不会造成额外损害）
3. 优先使用温和的修复手段（如禁用而非删除）
4. 高风险命令（如删除用户、杀进程、改配置）必须标注 risk_level 为 high
5. 所有命令必须在JSON块中完整列出
6. 如果不需要任何修复操作，输出空数组 []

### 命令编写规范：
- {shell_hint} 标准命令
- 每条命令单独一行
- 避免使用交互式命令
- 添加必要的错误处理"""

    # 构建用户消息
    user_content = f"""## 检测目标信息
- 主机名: {hostname}
- IP地址: {ip_info}
- 检测平台: {platform}
- 检测时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 系统安全日志

{log_content}

请进行完整的安全分析，并输出可执行的修复命令（JSON格式）。"""

    # 调用AI模型
    print(f"[*] 正在调用 {model_key} 进行分析...")
    try:
        analysis_report = call_ai_api(model_key, system_prompt, user_content, raise_error=True)
    except Exception as e:
        print(f"[ERROR] API调用失败: {str(e)}")
        raise e

    # 从报告中解析动作
    actions = parse_actions_from_report(analysis_report, platform)
    print(f"[*] 从分析结果中解析出 {len(actions)} 条修复动作")

    # 生成最终报告
    report = f"""# 安全应急响应分析报告（含自动修复建议）

## 检测目标信息
- 主机名: {hostname}
- IP地址: {ip_info}
- 检测平台: {platform}
- 检测时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- 分析模型: {model_key}

---

## 分析报告

{analysis_report}

---

## 自动修复操作清单

共 {len(actions)} 条建议操作：

| # | 风险等级 | 类别 | 描述 | 命令 |
|---|---------|------|------|------|
"""

    for i, action in enumerate(actions, 1):
        risk_icon = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}.get(action['risk_level'], '⚪')
        report += f"| {i} | {risk_icon} {action['risk_level']} | {action['category']} | {action['description']} | `{action['command']}` |\n"

    report += f"""
---

## 说明
本报告由 {model_key} 模型分析生成，包含自动修复建议。
执行修复操作时请逐条确认，高风险操作需谨慎评估。
"""

    print(f"[*] 带自动修复动作的分析完成")
    
    return {
        "report": report,
        "actions": actions
    }
def analyze_full_content(log_content, hostname, ip_info, model_key):
    """
    一次性分析所有数据（不分段）
    使用用户指定的大模型一次性处理所有日志内容
    """
    # 检测平台类型
    platform = detect_platform(log_content)
    print(f"[*] 检测到平台类型: {platform}")
    print(f"[*] 使用模型: {model_key}")
    print(f"[*] 正在一次性分析所有数据...")
    
    # 获取白名单
    whitelist = get_whitelist_prompt()
    
    # 根据平台选择不同的专家角色
    if platform == "windows":
        expert_role = "你是一名高级Windows安全应急响应专家"
    else:
        expert_role = "你是一名高级Linux安全应急响应专家"
    
    # 构建完整的系统提示词
    system_prompt = f"""{expert_role}。请对以下系统安全日志进行全面分析。

{whitelist}

分析要求：
1. 给出整体安全评分（百分制，100分为完全安全，分数越低安全性越差：90+优秀 70-89良好 50-69一般 50以下危险）
2. 按风险等级（高危/中危/低危/正常）分类列出发现的问题
3. 对每个问题提供：
   - 问题描述
   - 相关证据（具体的日志内容）
   - 处置建议和修复方案
4. 给出综合安全评估结论
5. 输出格式为结构化Markdown

重点关注：
- 异常进程和网络连接
- 可疑的用户活动
- 安全配置问题
- 潜在的攻击痕迹
- 系统漏洞和风险

请忽略白名单中的安全项，专注于真正的安全威胁。"""
    
    # 构建用户消息，包含所有日志内容
    user_content = f"""## 检测目标信息
- 主机名: {hostname}
- IP地址: {ip_info}
- 检测平台: {platform}
- 检测时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 系统安全日志

{log_content}

请对以上日志进行一次性全面分析，生成完整的安全应急响应报告。"""
    
    # 调用用户指定的AI模型进行分析（使用raise_error=True让错误抛出）
    print(f"[*] 正在调用 {model_key} 进行分析...")
    try:
        analysis_report = call_ai_api(model_key, system_prompt, user_content, raise_error=True)
    except Exception as e:
        # 打印错误并重新抛出，让上层接口捕获
        print(f"[ERROR] API调用失败: {str(e)}")
        raise e
    
    # 生成最终报告
    report = f"""# 安全应急响应分析报告

## 检测目标信息
- 主机名: {hostname}
- IP地址: {ip_info}
- 检测平台: {platform}
- 检测时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- 分析模型: {model_key}

---

## 分析报告

{analysis_report}

---

## 说明
本报告由 {model_key} 模型一次性分析生成，适用于具备大上下文窗口的AI模型。
"""
    
    print(f"[*] 一次性分析完成")
    return report

# ================= 主程序 =================
if __name__ == '__main__':
    # 解析命令行参数
    import argparse
    parser = argparse.ArgumentParser(description='应急响应分析系统 - Server端')
    parser.add_argument('--debug', action='store_true', help='启用Debug模式，输出API请求详情')
    parser.add_argument('--port', type=int, help='指定监听端口（覆盖配置文件）')
    parser.add_argument('--host', type=str, help='指定监听地址（覆盖配置文件）')
    args = parser.parse_args()
    
    # 设置debug模式
    if args.debug:
        DEBUG_MODE = True
        print("[DEBUG] Debug模式已启用 - API请求失败时将输出详细信息")
    else:
        DEBUG_MODE = False
    
    server_config = config['server']
    port = args.port if args.port else server_config['port']
    host = args.host if args.host else server_config['host']
    
    enabled_models = ai_manager.get_enabled_models()
    models_list = '\n'.join([f"║  - {k}: {v['name']}" for k, v in enabled_models.items()]) if enabled_models else "║  （无已启用模型）"
    
    debug_status = "已启用" if DEBUG_MODE else "已禁用"
    
    banner = f"""
╔══════════════════════════════════════════════════════════════╗
║           应急响应分析系统 - Server端 (模块化AI版)            ║
╠══════════════════════════════════════════════════════════════╣
║  功能:                                                       ║
║  1. 接收Client系统检查数据                                   ║
║  2. 多AI模型模块化分析                                       ║
║  3. 返回分析结果给Client                                     ║
║  4. 上传数据至对象存储                                        ║
╠══════════════════════════════════════════════════════════════╣
║  监听地址: {host}:{port}                                      ║
║  默认模型: {ai_manager.default_model}                         ║
║  Debug模式: {debug_status}                                     ║
╠══════════════════════════════════════════════════════════════╣
║  已启用的AI模型:                                             ║
{models_list}
╠══════════════════════════════════════════════════════════════╣
║  模型管理: 使用 ai_manager.py 命令行工具                     ║
║    python ai_manager.py list      - 查看所有模型             ║
║    python ai_manager.py enable    - 启用模型                 ║
║    python ai_manager.py set-default - 设置默认模型           ║
╠══════════════════════════════════════════════════════════════╣
║  命令行参数:                                                 ║
║    --debug    启用Debug模式（输出API请求详情）                ║
║    --port     指定监听端口                                    ║
║    --host     指定监听地址                                    ║
╠══════════════════════════════════════════════════════════════╣
║  API接口:                                                    ║
║  - GET  /models      查看模型列表（只读）                     ║
║  - POST /analyze     分析数据                                ║
║  - POST /upload      上传文件                                ║
╚══════════════════════════════════════════════════════════════╝
"""
    print(banner)
    print(f"[*] Server正在启动...")
    if DEBUG_MODE:
        print("[DEBUG] 注意: API调用失败时将输出完整请求/响应信息")
    app.run(host=host, port=port, debug=False)
