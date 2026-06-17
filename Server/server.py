#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CS架构 Server端 - 一次性AI分析版本
功能：
1. 接收Client发送的系统检查数据
2. 支持多AI模型的一次性全量分析（含自动修复命令）
3. 将分析结果和原始日志保存到对象存储/本地
4. 生成12小时有效的下载短链接

模型管理请使用 ai_manager.py 命令行工具
"""

import os
import json
import string
import secrets
import requests
import sys
from datetime import datetime, timedelta
from collections import defaultdict
from flask import Flask, request, jsonify, send_file
from i18n import T, report_T, set_server_lang, get_server_lang, init_lang

app = Flask(__name__)

# ================= Debug模式 =================
DEBUG_MODE = False

# 尝试导入可选依赖
try:
    from boto3.session import Session
    from botocore.signers import RequestSigner
    from aescode import AESCoder
    BOTO3_AVAILABLE = True
except ImportError as e:
    print(T("warning_dep_missing", e=e))
    print(T("warning_storage_unavailable"))
    BOTO3_AVAILABLE = False

# ================= 本地下载令牌管理 =================
download_tokens = {}  # token -> {"filepath": str, "expires_at": datetime}

def cleanup_expired_tokens():
    """清理过期的下载令牌"""
    now = datetime.now()
    expired = [t for t, v in download_tokens.items() if v['expires_at'] < now]
    for t in expired:
        del download_tokens[t]

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
        if 'ip_blacklist' not in config:
            config['ip_blacklist'] = {'enabled': True, 'blocked_ips': []}
        if ip not in config['ip_blacklist']['blocked_ips']:
            config['ip_blacklist']['blocked_ips'].append(ip)
            save_config(config)
    
    def remove_from_blacklist(self, ip):
        """从黑名单移除IP"""
        if ip in self.blocked_ips:
            self.blocked_ips.remove(ip)
            if 'ip_blacklist' in config and ip in config['ip_blacklist']['blocked_ips']:
                config['ip_blacklist']['blocked_ips'].remove(ip)
                save_config(config)
    
    def is_allowed(self, ip, max_requests, time_window_hours):
        """检查是否允许请求"""
        if self.is_blacklisted(ip):
            return False
        
        if not config.get('rate_limit', {}).get('enabled', False):
            self.total_requests[ip] += 1
            return True
        
        max_requests = config['rate_limit'].get('max_requests_per_ip', max_requests)
        time_window_hours = config['rate_limit'].get('time_window_hours', time_window_hours)
        
        now = datetime.now()
        window_start = now - timedelta(hours=time_window_hours)
        
        self.requests[ip] = [ts for ts in self.requests[ip] if ts > window_start]
        
        if len(self.requests[ip]) >= max_requests:
            return False
        
        self.requests[ip].append(now)
        self.total_requests[ip] += 1
        return True
    
    def get_remaining_requests(self, ip, max_requests, time_window_hours):
        """获取剩余请求次数"""
        if not config.get('rate_limit', {}).get('enabled', False):
            return max_requests
        
        now = datetime.now()
        window_start = now - timedelta(hours=time_window_hours)
        
        self.requests[ip] = [ts for ts in self.requests[ip] if ts > window_start]
        
        return max(0, max_requests - len(self.requests[ip]))
    
    def get_ip_stats(self, ip=None):
        """获取IP统计信息"""
        if ip:
            return {
                'ip': ip,
                'total_requests': self.total_requests.get(ip, 0),
                'current_window_requests': len(self.requests.get(ip, [])),
                'is_blacklisted': self.is_blacklisted(ip)
            }
        else:
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
            if ip in self.requests:
                del self.requests[ip]
            if ip in self.total_requests:
                del self.total_requests[ip]
        else:
            self.requests.clear()
            self.total_requests.clear()

# ================= 配置加载 =================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.json")

def load_config():
    """加载配置文件"""
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(T("error_config_load_failed", e=e))
        print(T("info_config_path", path=CONFIG_FILE))
        return None

def save_config(config_obj):
    """保存配置文件"""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config_obj, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"[ERROR] 保存配置文件失败: {e}")
        return False

# 加载配置
config = load_config()
if not config:
    print(T("error_cannot_load_config"))
    exit(1)

# 初始化AES解密（如果可用）
if BOTO3_AVAILABLE:
    try:
        aes = AESCoder()
    except Exception as e:
        print(T("warning_aes_init_failed", e=e))
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
        print(T("warning_s3_init_failed", e=e))
        return None

s3_client = init_s3_client()

# ================= AI模型管理 =================
class AIModelManager:
    """AI模型管理器"""
    
    def __init__(self, config_obj):
        self.config = config_obj
        self.models = config_obj['ai_models']['models']
        self.default_model = config_obj['ai_models']['default']
    
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
    
    if response.status_code != 200:
        error_text = response.text[:500] if response.text else "Unknown error"
        
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
    
    if 'choices' not in result or len(result['choices']) == 0:
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
    
    if response.status_code != 200:
        error_text = response.text[:500] if response.text else "Unknown error"
        
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
    
    if 'content' not in result or len(result['content']) == 0:
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
    """
    model_config = ai_manager.get_model(model_key)
    if not model_config:
        error_msg = T("error_model_not_found", model=model_key)
        if raise_error:
            raise Exception(error_msg)
        return error_msg
    
    if not model_config.get('enabled', False):
        error_msg = T("error_model_not_found", model=model_config['name'])
        if raise_error:
            raise Exception(error_msg)
        return error_msg
    
    if not model_config.get('api_key'):
        error_msg = T("error_model_no_api_key", name=model_config['name'])
        if raise_error:
            raise Exception(error_msg)
        return error_msg
    
    if model_key == 'claude':
        return call_claude_api(model_config, system_prompt, user_content)
    else:
        return call_openai_compatible_api(model_config, system_prompt, user_content)

# ================= 分析功能 =================
def get_whitelist_prompt(report_lang="zh"):
    """生成白名单提示词"""
    if not config['analysis']['enable_whitelist']:
        return ""
    
    keywords = config['analysis']['whitelist_keywords']
    return report_T("whitelist_section_header", report_lang,
        whitelist_keywords_1=', '.join(keywords[:4]),
        whitelist_keywords_2=', '.join(keywords[4:]))

def detect_platform(log_content):
    """检测日志内容来自哪个平台"""
    windows_indicators = [
        'wmic', 'powershell', 'cmd.exe', 'reg query', 'wevtutil',
        'HKLM\\', 'HKCU\\', 'C:\\Windows', 'C:\\inetpub',
        'Administrator', 'SYSTEM', 'Winlogon', 'IFEO'
    ]
    
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


def perform_one_shot_analysis(log_content, hostname, ip_info, model_key, report_lang="zh"):
    """
    一次性全量分析 - 含自动修复命令
    使用指定大模型一次性处理所有日志内容，生成分析报告 + 可执行修复动作
    返回: {"report": "...", "actions": [...]}
    """
    # 检测平台类型
    platform = detect_platform(log_content)
    print(T("log_detected_platform", platform=platform))
    print(T("log_using_model", model_key=model_key))
    print(T("log_performing_analysis"))

    whitelist = get_whitelist_prompt(report_lang)

    if platform == "windows":
        expert_role = report_T("expert_role_windows", report_lang)
        shell_hint = report_T("shell_hint_windows", report_lang)
    else:
        expert_role = report_T("expert_role_linux", report_lang)
        shell_hint = report_T("shell_hint_linux", report_lang)

    analysis_req = report_T("prompt_analysis_requirements", report_lang)
    repair_req = report_T("prompt_auto_repair_output", report_lang, shell_hint=shell_hint)

    # Intro line for the system prompt (language-dependent)
    if report_lang == "zh":
        prompt_intro = "请对以下系统安全日志进行全面分析，并给出可执行的修复命令。"
    else:
        prompt_intro = "Please perform a comprehensive analysis of the following system security logs and provide executable repair commands."

    system_prompt = f"""{expert_role}。{prompt_intro}

{whitelist}

{analysis_req}

{repair_req}"""

    detection_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    user_content = report_T("prompt_user_content", report_lang,
        hostname=hostname, ip_info=ip_info, platform=platform,
        detection_time=detection_time, log_content=log_content)

    print(T("log_calling_ai", model_key=model_key))
    try:
        analysis_report = call_ai_api(model_key, system_prompt, user_content, raise_error=True)
    except Exception as e:
        print(T("log_error_api_call", error=str(e)))
        raise e

    actions = parse_actions_from_report(analysis_report, platform)
    print(T("log_parsed_actions", count=len(actions)))

    # 生成最终报告
    detection_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    report = f"""{report_T('report_title', report_lang)}

{report_T('report_target_info', report_lang)}
{report_T('report_label_hostname', report_lang)}: {hostname}
{report_T('report_label_ip', report_lang)}: {ip_info}
{report_T('report_label_platform', report_lang)}: {platform}
{report_T('report_label_time', report_lang)}: {detection_time}
{report_T('report_label_model', report_lang)}: {model_key}

---

{report_T('report_section_analysis', report_lang)}

{analysis_report}

---

{report_T('report_section_actions', report_lang)}

{report_T('report_actions_total', report_lang, count=len(actions))}

{report_T('report_actions_table_header', report_lang)}
{report_T('report_actions_table_sep', report_lang)}
"""

    for i, action in enumerate(actions, 1):
        risk_icon = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}.get(action['risk_level'], '⚪')
        report += f"| {i} | {risk_icon} {action['risk_level']} | {action['category']} | {action['description']} | `{action['command']}` |\n"

    report += f"""
---

{report_T('report_footer', report_lang, model_key=model_key)}
"""

    print(T("log_analysis_complete"))
    
    return {
        "report": report,
        "actions": actions
    }


# ================= 对象存储与下载链接 =================
LOCAL_STORAGE_DIR = os.path.join(SCRIPT_DIR, "uploaded_files")

def ensure_local_storage_dir():
    """确保本地存储目录存在"""
    if not os.path.exists(LOCAL_STORAGE_DIR):
        os.makedirs(LOCAL_STORAGE_DIR)
        print(T("log_storage_dir_created", dir=LOCAL_STORAGE_DIR))

def upload_to_s3(content, filename):
    """
    上传内容到对象存储（S3作为备份，本地作为主存储）
    返回值始终包含本地下载令牌，不对外暴露S3
    """
    # 尝试上传到S3作为备份（静默处理，不影响正常流程）
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
            print(T("log_file_backed_up_s3", key=key))
        except Exception as e:
            print(T("log_s3_backup_failed", error=str(e)))
    
    # 始终使用本地存储提供下载服务
    try:
        ensure_local_storage_dir()
        
        local_file_path = os.path.join(LOCAL_STORAGE_DIR, filename)
        with open(local_file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # 生成本地下载令牌（12小时有效）
        # 6位短令牌（62^6 ≈ 568亿组合），如 /d/K2xoNP
        alphabet = string.ascii_letters + string.digits
        token = ''.join(secrets.choice(alphabet) for _ in range(6))
        expires_at = datetime.now() + timedelta(hours=12)
        download_tokens[token] = {
            "filepath": local_file_path,
            "expires_at": expires_at
        }
        
        print(T("log_file_saved_local", path=local_file_path))
        print(T("log_download_token", token=token, expires=expires_at.strftime('%Y-%m-%d %H:%M:%S')))
        
        return True, T("msg_upload_success", filename=filename), "local", token
    except Exception as e:
        print(T("log_error_local_storage", error=str(e)))
        return False, T("msg_upload_failed", error=str(e)), None, None


def generate_download_url(content, filename, request_host):
    """
    生成文件下载链接
    始终通过服务器自身IP提供短链接下载，不暴露外部存储
    返回: download_url 或 None
    """
    success, msg, storage_type, storage_ref = upload_to_s3(content, filename)
    
    if not success:
        return None
    
    # 构建服务器自身下载URL（不暴露S3等外部存储）
    server_host = config.get('server', {}).get('host', '127.0.0.1')
    server_port = config.get('server', {}).get('port', 8000)
    
    # 如果监听0.0.0.0，使用请求来源的host
    if server_host == '0.0.0.0':
        download_host = request_host.split(':')[0] if ':' in request_host else request_host
    else:
        download_host = server_host
    
    # 清理过期的下载令牌
    cleanup_expired_tokens()
    
    return f"http://{download_host}:{server_port}/d/{storage_ref}"


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
        "server_version": "4.0"
    })

@app.route('/attack_patterns', methods=['GET'])
def get_attack_patterns():
    """获取攻击特征库接口"""
    try:
        pattern_file = os.path.join(SCRIPT_DIR, "attack_patterns.json")
        if os.path.exists(pattern_file):
            with open(pattern_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            patterns = data.get('patterns', {})
            return jsonify({
                "success": True,
                "patterns": patterns
            })
        else:
            return jsonify({
                "success": False,
                "error": T("error_pattern_file_not_found")
            }), 404
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/models', methods=['GET'])
def list_models():
    """列出所有AI模型（只读）"""
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
        "note": T("models_note")
    })

@app.route('/analyze', methods=['POST'])
def analyze():
    """
    一次性全量分析接口（含自动修复命令）
    
    请求体JSON格式:
    {
        "ticket_id": "工单号",
        "hostname": "主机名",
        "ip_info": "IP信息",
        "log_content": "完整的日志内容（一次性发送所有数据）",
        "model": "可选，指定使用的AI模型"
    }
    
    响应格式:
    {
        "success": true,
        "ticket_id": "...",
        "hostname": "...",
        "platform": "linux/windows",
        "analysis_report": "...",
        "actions": [...],
        "model_used": "...",
        "log_uploaded": true,
        "log_filename": "...",
        "analysis_filename": "...",
        "log_download_url": "http://...",
        "analysis_download_url": "http://..."
    }
    """
    try:
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
                    "error": T("error_rate_limit", max=max_requests, hours=time_window),
                    "remaining_requests": remaining,
                    "time_window_hours": time_window
                }), 429
        
        data = request.get_json()
        
        if not data:
            return jsonify({"success": False, "error": T("error_invalid_request")}), 400
        
        ticket_id = data.get('ticket_id', 'unknown')
        hostname = data.get('hostname', 'unknown')
        ip_info = data.get('ip_info', 'unknown')
        log_content = data.get('log_content', '')
        model_key = data.get('model')
        report_lang = data.get('lang', 'zh')  # 报告语言，默认中文
        
        if not log_content:
            return jsonify({"success": False, "error": T("error_empty_log")}), 400
        
        # 验证模型
        if model_key and model_key not in ai_manager.get_enabled_models():
            return jsonify({"success": False, "error": T("error_model_not_found", model=model_key)}), 400
        
        actual_model = model_key or config['ai_models'].get('full_analysis_model', ai_manager.default_model)
        
        # 生成文件名
        log_filename = f"{ticket_id}_{hostname}_log.md"
        analysis_filename = f"{ticket_id}_{hostname}_analysis_report.md"
        
        # 执行一次性全量分析（含自动修复命令）
        print(T("log_starting_analysis", ticket=ticket_id, host=hostname))
        analysis_result = perform_one_shot_analysis(log_content, hostname, ip_info, actual_model, report_lang)
        
        analysis_report = analysis_result.get('report', '')
        actions = analysis_result.get('actions', [])
        
        # 保存原始日志并生成下载链接
        log_download_url = generate_download_url(log_content, log_filename, request.host)
        
        # 保存分析报告并生成下载链接
        analysis_download_url = generate_download_url(analysis_report, analysis_filename, request.host)
        
        response_data = {
            "success": True,
            "ticket_id": ticket_id,
            "hostname": hostname,
            "platform": detect_platform(log_content),
            "analysis_report": analysis_report,
            "actions": actions,
            "model_used": actual_model,
            "log_uploaded": log_download_url is not None,
            "log_filename": log_filename,
            "analysis_filename": analysis_filename
        }
        
        # 只在成功生成时返回下载链接
        if log_download_url:
            response_data["log_download_url"] = log_download_url
        if analysis_download_url:
            response_data["analysis_download_url"] = analysis_download_url
        
        return jsonify(response_data)
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/upload', methods=['POST'])
def upload_file():
    """直接上传文件接口，返回12小时有效下载链接"""
    try:
        data = request.get_json()
        filename = data.get('filename')
        content = data.get('content')
        
        if not filename or not content:
            return jsonify({"success": False, "error": T("error_missing_filename_content")}), 400
        
        download_url = generate_download_url(content, filename, request.host)
        
        return jsonify({
            "success": download_url is not None,
            "download_url": download_url
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/d/<token>', methods=['GET'])
@app.route('/download/<token>', methods=['GET'])
def download_file(token):
    """本地文件下载接口（带令牌验证，12小时有效）"""
    cleanup_expired_tokens()
    
    if token not in download_tokens:
        return jsonify({"success": False, "error": T("error_download_not_found")}), 404
    
    token_info = download_tokens[token]
    
    if token_info['expires_at'] < datetime.now():
        del download_tokens[token]
        return jsonify({"success": False, "error": T("error_download_expired")}), 410
    
    filepath = token_info['filepath']
    
    if not os.path.exists(filepath):
        return jsonify({"success": False, "error": T("error_file_not_found")}), 404
    
    return send_file(filepath, as_attachment=True, download_name=os.path.basename(filepath))


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
            message = T("msg_ip_stats_cleared_single", ip=ip)
        else:
            message = T("msg_ip_stats_cleared_all")
        
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
                "error": T("error_missing_ip")
            }), 400
        
        ip = data['ip']
        
        import re
        ip_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
        if not re.match(ip_pattern, ip):
            return jsonify({
                "success": False,
                "error": T("error_invalid_ip_format", ip=ip)
            }), 400
        
        parts = ip.split('.')
        for part in parts:
            if int(part) > 255:
                return jsonify({
                    "success": False,
                    "error": T("error_invalid_ip", ip=ip)
                }), 400
        
        if rate_limiter.is_blacklisted(ip):
            return jsonify({
                "success": False,
                "error": T("error_ip_already_blacklisted", ip=ip)
            }), 400
        
        rate_limiter.add_to_blacklist(ip)
        
        return jsonify({
            "success": True,
            "message": T("msg_ip_added_blacklist", ip=ip)
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
                "error": T("error_missing_ip")
            }), 400
        
        ip = data['ip']
        
        if not rate_limiter.is_blacklisted(ip):
            return jsonify({
                "success": False,
                "error": T("error_ip_not_in_blacklist", ip=ip)
            }), 400
        
        rate_limiter.remove_from_blacklist(ip)
        
        return jsonify({
            "success": True,
            "message": T("msg_ip_removed_blacklist", ip=ip)
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


# ================= 主程序 =================
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Emergency Response Analysis System - Server (One-Shot Analysis)')
    parser.add_argument('--debug', action='store_true', help='Enable Debug mode (output API request details)')
    parser.add_argument('--port', type=int, help='Specify listening port (overrides config file)')
    parser.add_argument('--host', type=str, help='Specify listening address (overrides config file)')
    parser.add_argument('--lang', type=str, choices=['en', 'zh'], help='Set UI language (en/zh, default: en)')
    args = parser.parse_args()
    
    # 初始化语言设置
    init_lang()
    if args.lang:
        set_server_lang(args.lang)
    
    if args.debug:
        DEBUG_MODE = True
        print(T("debug_mode_enabled"))
    else:
        DEBUG_MODE = False
    
    server_config = config['server']
    port = args.port if args.port else server_config['port']
    host = args.host if args.host else server_config['host']
    
    enabled_models = ai_manager.get_enabled_models()
    models_list = '\n'.join([f"║  - {k}: {v['name']}" for k, v in enabled_models.items()]) if enabled_models else f"║  {T('banner_no_models')}"
    
    debug_status = T("debug_enabled") if DEBUG_MODE else T("debug_disabled")
    
    banner = f"""
╔══════════════════════════════════════════════════════════════╗
║       {T('banner_header'):^56}║
╠══════════════════════════════════════════════════════════════╣
║  {T('banner_feature_1'):<58}║
║  {T('banner_feature_2'):<58}║
║  {T('banner_feature_3'):<58}║
║  {T('banner_feature_4'):<58}║
╠══════════════════════════════════════════════════════════════╣
║  {T('banner_listen_addr')}: {host}:{port:<41}║
║  {T('banner_default_model')}: {ai_manager.default_model:<43}║
║  {T('banner_debug_mode')}: {debug_status:<43}║
╠══════════════════════════════════════════════════════════════╣
║  {T('banner_enabled_models')}:{'':>39}║
{models_list}
╠══════════════════════════════════════════════════════════════╣
║  {T('banner_model_mgmt'):<58}║
║    python ai_manager.py list      - View all models{'':>17}║
║    python ai_manager.py enable    - Enable model{'':>21}║
║    python ai_manager.py set-default - Set default model{'':>12}║
╠══════════════════════════════════════════════════════════════╣
║  {T('banner_cli_args')}:{'':>44}║
║    {T('banner_cli_debug'):<56}║
║    {T('banner_cli_port'):<56}║
║    {T('banner_cli_host'):<56}║
║    {T('banner_cli_lang'):<56}║
╠══════════════════════════════════════════════════════════════╣
║  {T('banner_api_endpoints')}:{'':>44}║
║  {T('banner_api_models'):<56}║
║  {T('banner_api_analyze'):<56}║
║  {T('banner_api_upload'):<56}║
║  {T('banner_api_download'):<56}║
║  {T('banner_api_download2'):<56}║
╚══════════════════════════════════════════════════════════════╝
"""
    print(banner)
    print(T("server_starting"))
    if DEBUG_MODE:
        print(T("debug_note"))
    app.run(host=host, port=port, debug=False)
