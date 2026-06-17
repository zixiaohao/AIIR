#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AIIR 国际化模块 / Internationalization Module

Usage:
    from i18n import T, get_server_lang, set_server_lang
    print(T("key", lang))  # Get translated text
"""

import os

# ==================== Translation Dictionaries ====================

TRANSLATIONS = {
    "en": {
        # ── Server Console / Banner ──
        "banner_header": "Emergency Response Analysis System - Server (One-Shot Analysis)",
        "banner_feature_1": "1. Receive client system check data (one-shot send)",
        "banner_feature_2": "2. Multi-AI model one-shot analysis + auto-repair command generation",
        "banner_feature_3": "3. Return analysis results and repair actions to client",
        "banner_feature_4": "4. Save raw logs and analysis reports, generate 12h download links",
        "banner_listen_addr": "Listen address",
        "banner_default_model": "Default model",
        "banner_debug_mode": "Debug mode",
        "banner_enabled_models": "Enabled AI models",
        "banner_model_mgmt": "Model management: use ai_manager.py CLI tool",
        "banner_cli_args": "CLI arguments",
        "banner_cli_debug": "--debug    Enable debug mode (output API request details)",
        "banner_cli_port": "--port     Specify listening port",
        "banner_cli_host": "--host     Specify listening address",
        "banner_cli_lang": "--lang     Set UI language (en/zh, default: en)",
        "banner_api_endpoints": "API endpoints",
        "banner_api_models": "- GET  /models           View model list (read-only)",
        "banner_api_analyze": "- POST /analyze          One-shot full analysis (with repair commands)",
        "banner_api_upload": "- POST /upload           Upload file (returns download link)",
        "banner_api_download": "- GET  /d/<token>        Short-link download (same as /download)",
        "banner_api_download2": "- GET  /download/<token> Download file (12h valid)",
        "banner_no_models": "(No enabled models)",
        "debug_enabled": "Enabled",
        "debug_disabled": "Disabled",

        # ── Server Startup ──
        "server_starting": "[*] Server starting...",
        "debug_note": "[DEBUG] Note: Full request/response info will be output on API call failure",
        "debug_mode_enabled": "[DEBUG] Debug mode enabled - API request details will be output on failure",
        "warning_dep_missing": "[WARNING] Optional dependency not installed: {}",
        "warning_storage_unavailable": "[WARNING] Object storage functionality will be unavailable",
        "error_config_load_failed": "[ERROR] Failed to load config file: {}",
        "info_config_path": "[INFO] Config file path: {}",
        "error_cannot_load_config": "[ERROR] Cannot load config file, exiting",
        "warning_aes_init_failed": "[WARNING] AES init failed: {}",
        "warning_s3_init_failed": "[WARNING] S3 client init failed: {}",

        # ── Analysis Logs ──
        "log_detected_platform": "[*] Detected platform type: {}",
        "log_using_model": "[*] Using model: {}",
        "log_performing_analysis": "[*] Performing one-shot full analysis (with auto-repair commands)...",
        "log_calling_ai": "[*] Calling {} for analysis...",
        "log_error_api_call": "[ERROR] API call failed: {}",
        "log_parsed_actions": "[*] Parsed {} repair actions from analysis result",
        "log_analysis_complete": "[*] One-shot full analysis complete",
        "log_starting_analysis": "[*] Starting analysis for ticket {} - host {}",
        "log_storage_dir_created": "[*] Created local storage directory: {}",
        "log_file_backed_up_s3": "[*] File backed up to S3: {}",
        "log_s3_backup_failed": "[WARNING] S3 backup failed (service unaffected): {}",
        "log_file_saved_local": "[*] File saved locally: {}",
        "log_download_token": "[*] Download token: {} (expires: {})",
        "log_error_local_storage": "[ERROR] Local storage failed: {}",

        # ── API Error Messages ──
        "error_rate_limit": "Request rate limit exceeded. Max {} requests per {} hours for the same IP.",
        "error_invalid_request": "Invalid request data",
        "error_empty_log": "Log content is empty",
        "error_model_not_found": "Model {} is not enabled or does not exist",
        "error_model_no_api_key": "Model {} has no API key configured",
        "error_missing_filename_content": "Missing filename or content",
        "error_download_not_found": "Download link does not exist or has expired",
        "error_download_expired": "Download link has expired (valid for 12 hours)",
        "error_file_not_found": "File not found",
        "error_missing_ip": "Please provide IP address",
        "error_invalid_ip_format": "Invalid IP address format: {}",
        "error_invalid_ip": "Invalid IP address: {}",
        "error_ip_already_blacklisted": "IP {} is already in the blacklist",
        "error_ip_not_in_blacklist": "IP {} is not in the blacklist",
        "error_pattern_file_not_found": "Pattern file does not exist",

        # ── API Success Messages ──
        "msg_upload_success": "Upload successful: {}",
        "msg_upload_failed": "Upload failed: {}",
        "msg_ip_stats_cleared_single": "Cleared statistics for IP {}",
        "msg_ip_stats_cleared_all": "Cleared statistics for all IPs",
        "msg_ip_added_blacklist": "Added {} to blacklist",
        "msg_ip_removed_blacklist": "Removed {} from blacklist",

        # ── /models Response ──
        "models_note": "Model management: use ai_manager.py CLI tool",

        # ── Health Check ──
        "health_status_ok": "ok",

        # ── Report / Prompt Text (en, for English reports) ──
        "expert_role_windows": "You are a senior Windows security emergency response expert",
        "expert_role_linux": "You are a senior Linux security emergency response expert",
        "shell_hint_windows": "PowerShell/cmd",
        "shell_hint_linux": "bash/sh",
        "prompt_analysis_requirements": """### Analysis Requirements:
1. Provide an overall security score (out of 100, where 100 means completely secure; the lower the score, the worse the security: 90+ Excellent, 70-89 Good, 50-69 Fair, below 50 Dangerous)
2. Categorize findings by risk level (High/Medium/Low/Normal)
3. For each finding, provide:
   - Issue description
   - Relevant evidence (specific log content)
   - Remediation recommendations and fixes
4. Provide a comprehensive security assessment conclusion
5. Output format: structured Markdown""",
        "prompt_auto_repair_output": """### Auto-Repair Action Output Requirements:
At the end of the analysis report, output all recommended repair actions in JSON format as follows:

```json
[
  {{
    "command": "specific repair command",
    "description": "action description, explaining why this command should be executed",
    "risk_level": "high/medium/low",
    "category": "process/user/network/file/service/config"
  }}
]
```

Requirements:
1. Each command must be a standalone command executable in {shell_hint}
2. Commands should be idempotent (safe to execute multiple times)
3. Prefer gentle repair methods (e.g., disable rather than delete)
4. High-risk commands (e.g., deleting users, killing processes, modifying config) must be marked risk_level: high
5. All commands must be listed completely within the JSON block
6. If no repair action is needed, output an empty array []
7. The JSON block must be wrapped with ```json and ```

### Command Writing Guidelines:
- {shell_hint} standard commands
- One command per line
- Avoid interactive commands
- Include necessary error handling

Focus on:
- Abnormal processes and network connections
- Suspicious user activity
- Security configuration issues
- Potential attack traces
- System vulnerabilities and risks

Ignore whitelisted security items and focus on real security threats.""",
        "prompt_user_content": """## Target Information
- Hostname: {hostname}
- IP Address: {ip_info}
- Platform: {platform}
- Detection Time: {detection_time}

## System Security Logs

{log_content}

Please perform a complete security analysis and output executable repair commands (in JSON format).""",
        "whitelist_section_header": """[Important: Analysis Whitelist - Please ignore the following known security items]
1. This emergency response tool:
   - Process/filename: {whitelist_keywords_1}
   - Path characteristics: usually located in /tmp or /root directories. This is normal emergency response tool behavior, not malicious.
2. Security software/cloud agents:
   - {whitelist_keywords_2}
   - The above processes are legitimate cloud security monitoring components. Do NOT identify them as malicious processes, mining software, or trojans.
3. Judgment criteria:
   - Only flag the above processes if they exhibit clearly abnormal behavior (e.g., connecting to mining pools, modifying /etc/shadow), otherwise treat them as safe.""",

        # Report labels (en)
        "report_title": "# Security Emergency Response Analysis Report (with Auto-Repair Recommendations)",
        "report_target_info": "## Target Information",
        "report_label_hostname": "- Hostname",
        "report_label_ip": "- IP Address",
        "report_label_platform": "- Platform",
        "report_label_time": "- Detection Time",
        "report_label_model": "- Analysis Model",
        "report_section_analysis": "## Analysis Report",
        "report_section_actions": "## Auto-Repair Action List",
        "report_actions_total": "Total {count} recommended actions:",
        "report_actions_table_header": "| # | Risk Level | Category | Description | Command |",
        "report_actions_table_sep": "|---|---------|------|------|------|",
        "report_footer": """## Notes
This report was generated by {model_key} model using one-shot full analysis, including auto-repair recommendations.
Please verify each repair action individually; high-risk operations require careful evaluation.
""",
    },
    "zh": {
        # ── Server Console / Banner ──
        "banner_header": "应急响应分析系统 - Server端 (一次性全量分析版)",
        "banner_feature_1": "1. 接收Client系统检查数据（一次性全量发送）",
        "banner_feature_2": "2. 多AI模型一次性分析 + 自动修复命令生成",
        "banner_feature_3": "3. 返回分析结果、修复动作给Client",
        "banner_feature_4": "4. 保存原始日志和分析报告，生成12h下载短链接",
        "banner_listen_addr": "监听地址",
        "banner_default_model": "默认模型",
        "banner_debug_mode": "Debug模式",
        "banner_enabled_models": "已启用的AI模型",
        "banner_model_mgmt": "模型管理: 使用 ai_manager.py 命令行工具",
        "banner_cli_args": "命令行参数",
        "banner_cli_debug": "--debug    启用Debug模式（输出API请求详情）",
        "banner_cli_port": "--port     指定监听端口",
        "banner_cli_host": "--host     指定监听地址",
        "banner_cli_lang": "--lang     设置界面语言 (en/zh, 默认: en)",
        "banner_api_endpoints": "API接口",
        "banner_api_models": "- GET  /models           查看模型列表（只读）",
        "banner_api_analyze": "- POST /analyze          一次性全量分析（含修复命令）",
        "banner_api_upload": "- POST /upload           上传文件（返回下载短链接）",
        "banner_api_download": "- GET  /d/<token>        短链接下载（等同 /download）",
        "banner_api_download2": "- GET  /download/<token> 下载文件（12h有效）",
        "banner_no_models": "（无已启用模型）",
        "debug_enabled": "已启用",
        "debug_disabled": "已禁用",

        # ── Server Startup ──
        "server_starting": "[*] Server正在启动...",
        "debug_note": "[DEBUG] 注意: API调用失败时将输出完整请求/响应信息",
        "debug_mode_enabled": "[DEBUG] Debug模式已启用 - API请求失败时将输出详细信息",
        "warning_dep_missing": "[WARNING] 可选依赖未安装: {}",
        "warning_storage_unavailable": "[WARNING] 对象存储功能将不可用",
        "error_config_load_failed": "[ERROR] 加载配置文件失败: {}",
        "info_config_path": "[INFO] 配置文件路径: {}",
        "error_cannot_load_config": "[ERROR] 无法加载配置文件，程序退出",
        "warning_aes_init_failed": "[WARNING] AES初始化失败: {}",
        "warning_s3_init_failed": "[WARNING] S3客户端初始化失败: {}",

        # ── Analysis Logs ──
        "log_detected_platform": "[*] 检测到平台类型: {}",
        "log_using_model": "[*] 使用模型: {}",
        "log_performing_analysis": "[*] 正在执行一次性全量分析（含自动修复命令）...",
        "log_calling_ai": "[*] 正在调用 {} 进行分析...",
        "log_error_api_call": "[ERROR] API调用失败: {}",
        "log_parsed_actions": "[*] 从分析结果中解析出 {} 条修复动作",
        "log_analysis_complete": "[*] 一次性全量分析完成",
        "log_starting_analysis": "[*] 开始分析工单 {} - 主机 {}",
        "log_storage_dir_created": "[*] 创建本地存储目录: {}",
        "log_file_backed_up_s3": "[*] 文件已备份到S3: {}",
        "log_s3_backup_failed": "[WARNING] S3备份失败（不影响服务）: {}",
        "log_file_saved_local": "[*] 文件已保存到本地: {}",
        "log_download_token": "[*] 下载令牌: {} (过期时间: {})",
        "log_error_local_storage": "[ERROR] 本地存储失败: {}",

        # ── API Error Messages ──
        "error_rate_limit": "请求频率超限，同一IP在{}小时内最多请求{}次",
        "error_invalid_request": "无效的请求数据",
        "error_empty_log": "日志内容为空",
        "error_model_not_found": "模型 {} 未启用或不存在",
        "error_model_no_api_key": "模型 {} 未配置API密钥",
        "error_missing_filename_content": "缺少文件名或内容",
        "error_download_not_found": "下载链接不存在或已过期",
        "error_download_expired": "下载链接已过期（有效期12小时）",
        "error_file_not_found": "文件不存在",
        "error_missing_ip": "请提供IP地址",
        "error_invalid_ip_format": "无效的IP地址格式: {}",
        "error_invalid_ip": "无效的IP地址: {}",
        "error_ip_already_blacklisted": "IP {} 已在黑名单中",
        "error_ip_not_in_blacklist": "IP {} 不在黑名单中",
        "error_pattern_file_not_found": "特征库文件不存在",

        # ── API Success Messages ──
        "msg_upload_success": "上传成功: {}",
        "msg_upload_failed": "上传失败: {}",
        "msg_ip_stats_cleared_single": "已清除IP {} 的统计数据",
        "msg_ip_stats_cleared_all": "已清除所有IP的统计数据",
        "msg_ip_added_blacklist": "已将 {} 添加到黑名单",
        "msg_ip_removed_blacklist": "已将 {} 从黑名单移除",

        # ── /models Response ──
        "models_note": "模型管理请使用 ai_manager.py 命令行工具",

        # ── Health Check ──
        "health_status_ok": "ok",

        # ── Report / Prompt Text (zh, for Chinese reports) ──
        "expert_role_windows": "你是一名高级Windows安全应急响应专家",
        "expert_role_linux": "你是一名高级Linux安全应急响应专家",
        "shell_hint_windows": "PowerShell/cmd",
        "shell_hint_linux": "bash/sh",
        "prompt_analysis_requirements": """### 分析要求：
1. 给出整体安全评分（百分制，100分为完全安全，分数越低安全性越差：90+优秀 70-89良好 50-69一般 50以下危险）
2. 按风险等级（高危/中危/低危/正常）分类列出发现的问题
3. 对每个问题提供：
   - 问题描述
   - 相关证据（具体的日志内容）
   - 处置建议和修复方案
4. 给出综合安全评估结论
5. 输出格式为结构化Markdown""",
        "prompt_auto_repair_output": """### 自动修复动作输出要求：
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
7. JSON块必须用 ```json 和 ``` 包裹

### 命令编写规范：
- {shell_hint} 标准命令
- 每条命令单独一行
- 避免使用交互式命令
- 添加必要的错误处理

重点关注：
- 异常进程和网络连接
- 可疑的用户活动
- 安全配置问题
- 潜在的攻击痕迹
- 系统漏洞和风险

请忽略白名单中的安全项，专注于真正的安全威胁。""",
        "prompt_user_content": """## 检测目标信息
- 主机名: {hostname}
- IP地址: {ip_info}
- 检测平台: {platform}
- 检测时间: {detection_time}

## 系统安全日志

{log_content}

请进行完整的安全分析，并输出可执行的修复命令（JSON格式）。""",
        "whitelist_section_header": """【重要：分析白名单 - 请忽略以下已知安全项】
1. 本次应急响应工具：
   - 进程/文件名: {whitelist_keywords_1}
   - 路径特征: 通常位于 /tmp 目录或 /root 下，这是正常的应急工具运行行为，非恶意。
2. 安全软件/云代理：
   - {whitelist_keywords_2}
   - 以上进程属于合法的云安全监控组件，请勿将其识别为恶意进程、挖矿或木马。
3. 判定标准：
   - 仅当上述进程出现明显异常行为（如连接矿池、修改 /etc/shadow）时才需标记，否则视为安全。""",

        # Report labels (zh)
        "report_title": "# 安全应急响应分析报告（含自动修复建议）",
        "report_target_info": "## 检测目标信息",
        "report_label_hostname": "- 主机名",
        "report_label_ip": "- IP地址",
        "report_label_platform": "- 检测平台",
        "report_label_time": "- 检测时间",
        "report_label_model": "- 分析模型",
        "report_section_analysis": "## 分析报告",
        "report_section_actions": "## 自动修复操作清单",
        "report_actions_total": "共 {count} 条建议操作：",
        "report_actions_table_header": "| # | 风险等级 | 类别 | 描述 | 命令 |",
        "report_actions_table_sep": "|---|---------|------|------|------|",
        "report_footer": """## 说明
本报告由 {model_key} 模型一次性全量分析生成，包含自动修复建议。
执行修复操作时请逐条确认，高风险操作需谨慎评估。
""",
    },
}


# ==================== Language Management ====================

_server_lang = "en"  # default server UI language
_report_lang_default = "zh"  # default report language


def set_server_lang(lang):
    """Set the server UI language"""
    global _server_lang
    if lang in ("en", "zh"):
        _server_lang = lang


def get_server_lang():
    """Get the current server UI language"""
    return _server_lang


def get_report_lang():
    """Get the default report language"""
    return _report_lang_default


def T(key, lang=None, **kwargs):
    """
    Get translated text.
    
    Args:
        key: Translation key
        lang: Language code (defaults to server lang if None)
        **kwargs: Format arguments
    
    Returns:
        Translated string
    """
    if lang is None:
        lang = _server_lang
    
    # Get the translation dictionary for the language, fall back to en
    t_dict = TRANSLATIONS.get(lang, TRANSLATIONS["en"])
    
    # Get the text
    text = t_dict.get(key, key)
    
    # Apply format if kwargs provided
    if kwargs:
        text = text.format(**kwargs)
    
    return text


def report_T(key, report_lang=None, **kwargs):
    """
    Get translated text for reports.
    
    Args:
        key: Translation key
        report_lang: Report language code (defaults to zh if None)
        **kwargs: Format arguments
    
    Returns:
        Translated string
    """
    if report_lang is None:
        report_lang = _report_lang_default
    
    return T(key, lang=report_lang, **kwargs)


def init_lang():
    """
    Initialize server language from environment variable or CLI args.
    Checks AIIR_LANG env var first.
    """
    env_lang = os.environ.get("AIIR_LANG", "").lower()
    if env_lang in ("en", "zh"):
        set_server_lang(env_lang)
