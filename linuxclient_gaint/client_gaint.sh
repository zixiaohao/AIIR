#!/bin/bash

# CS架构 Client端 - 一次性发送版本
# 功能：收集系统数据，一次性发送到Server进行分析

# 定义路径变量
PATH=/bin:/sbin:/usr/bin:/usr/sbin

# ================= 配置区域 =================
# Server地址（可通过环境变量AIIR_SERVER_URL设置默认值）
DEFAULT_SERVER_URL="${AIIR_SERVER_URL:-}"
SERVER_URL=""
# ===========================================

# Linux格式转换建议: dos2unix client_gaint.sh

# 检查是否具有root权限
if [ "$(id -u)" -ne 0 ]; then
  echo "请使用root权限运行此脚本！"
  exit 1
fi

# 检查 busybox 是否在当前目录中并赋予执行权限
if [ ! -f "./busybox" ]; then
  echo "busybox 文件不在当前目录中，为了脚本兼容性，建议放置 busybox！"
  echo "尝试使用系统默认命令..."
  # 定义兼容函数，如果没有busybox则直接执行命令
  function run_cmd() {
      "$@"
  }
else
  chmod +x ./busybox
  function run_cmd() {
      ./busybox "$@"
  }
fi

# 检查 vuln 程序是否存在并赋予执行权限
if [ ! -f "./vuln" ]; then
  echo "vuln 文件不在当前目录中 (可选功能受到限制)"
else
  chmod +x ./vuln
fi

# 获取IP地址、主机名和日期
internal_ip=$(run_cmd ip a | run_cmd grep inet | run_cmd grep -v '127.0.0.1' | run_cmd grep -v inet6 | run_cmd awk '{print $2}' | run_cmd cut -d/ -f1 | head -n 1)
hostname=$(run_cmd hostname)
date=$(run_cmd date +%Y%m%d)

# 提示用户输入工单号/标识
read -p "请输入工单号(用于文件名):" input_string
if [ -z "$input_string" ]; then
    echo "输入不能为空！"
    exit 1
fi
filename="${input_string}_log.md"
# 清空或创建日志文件
> "$filename"

# 打印消息到控制台和日志文件
print_msg() {
  echo -e "$1\n" | tee -a "$filename"
}

# 打印代码块到控制台和日志文件
print_code() {
  echo -e "\`\`\`shell\n$1\n\`\`\`\n" | tee -a "$filename"
}

# 反弹shell关键词
KEYWORDS='(tftp\s-i|scp\s|sftp\s|bash\s-i|nc\s-e|sh\s-i|wget\s|curl\s|\bexec|/dev/tcp/|/dev/udp/|useradd|groupadd|chattr|fsockopen|socat|base64|socket|perl|openssl)'

echo "================开始信息收集================"

### 1.系统基础信息 ###
print_msg "## 系统基础信息"

# 1.1 获取操作系统版本信息
print_msg "### 操作系统版本信息"
os_version=$(run_cmd uname -a)
print_code "$os_version"

# 1.2 发行版本信息
print_msg "### 发行版本信息"
print_code "$(cat /etc/os-release 2>/dev/null || cat /etc/issue 2>/dev/null)"

# 1.3 获取CPU信息
print_msg "### CPU信息"
cpu_info=$(run_cmd grep -m 1 'model name' /proc/cpuinfo | awk -F': ' '{print $2}')
print_code "${cpu_info:-未找到CPU信息}"

# 1.4 获取内存信息
print_msg "### 内存信息"
memory_info=$(run_cmd free -h)
print_code "$memory_info"

# 1.5 获取磁盘空间使用情况
print_msg "### 磁盘空间使用情况"
disk_space=$(run_cmd df -h)
print_code "$disk_space"

# 1.6 获取内网 IP
print_msg "### 内网 IP 地址"
print_code "${internal_ip:-未找到内网 IP 地址}"

# 1.7 获取公网 IP
print_msg "### 公网 IP 地址"
public_ip=$(curl --silent --max-time 3 members.3322.org/dyndns/getip 2>&1 || echo "无法获取公网 IP")
print_code "$public_ip"

# 1.8 获取主机名
print_msg "### 主机名"
print_code "$hostname"

# 1.9 获取当前用户
print_msg "### 当前用户"
current_user=$(run_cmd whoami)
print_code "$current_user"

# 1.10 获取系统启动时间
print_msg "### 系统启动时间"
system_uptime=$(run_cmd uptime)
print_code "$system_uptime"

### 2.网络连接 ###
print_msg "## 网络连接"

# 2.1 ARP表项
print_msg "### ARP表项"
print_code "$(run_cmd arp -an 2>/dev/null)"

# 2.3 网络连接信息
print_msg "### 网络连接情况"
print_code "$(run_cmd netstat -anp 2>/dev/null)"

# 2.4 网络路由
print_msg "### 网络路由表"
print_code "$(run_cmd route -n 2>/dev/null)"

# 2.5 防火墙策略
print_msg "### 防火墙规则 (iptables)"
iptables_rules=$(run_cmd iptables -L -v -n 2>/dev/null)
print_code "${iptables_rules:-未找到iptables规则或无权限}"

### 3.端口信息 ###
print_msg "## 端口信息"
print_msg "### TCP开放端口"
print_code "$(run_cmd netstat -tuln 2>/dev/null)"

### 4.系统进程 ###
print_msg "## 系统进程"
print_msg "### 进程列表"
ps_output=$(run_cmd ps aux)
print_code "$ps_output"
print_msg "### 可疑进程匹配"
suspicious_processes=$(echo "$ps_output" | run_cmd grep -E "$KEYWORDS")
print_code "${suspicious_processes:-未发现明显关键字匹配进程}"

### 5.自启动项 ###
print_msg "## 自启动项"
print_msg "### init.d与systemd启用服务"
init_files=$(run_cmd find /etc/init.d/ -type f 2>/dev/null)
systemd_units=$(run_cmd systemctl list-unit-files --state=enabled 2>/dev/null)
print_code "Init.d:\n$init_files\n\nSystemd:\n$systemd_units"

### 6.定时任务 ###
print_msg "## 定时任务"
print_msg "### 系统与用户Crontab"
cron_content=""
cron_files="/etc/crontab /etc/cron.d/* /var/spool/cron/* /var/spool/cron/crontabs/*"
for file in $cron_files; do
  if [ -r "$file" ]; then
    cron_content+="File: $file\n$(cat "$file")\n----------------\n"
  fi
done
print_code "${cron_content:-未发现定时任务文件内容}"

### 7.关键文件检查 ###
print_msg "## 关键文件检查"

print_msg "### hosts文件"
print_code "$(cat /etc/hosts 2>/dev/null)"

print_msg "### SSH 公钥/私钥/Authorized_keys"
ssh_files=$(find /root /home -name "*.pub" -o -name "id_rsa" -o -name "authorized_keys" 2>/dev/null | xargs ls -l 2>/dev/null)
print_code "${ssh_files:-未找到SSH相关密钥文件}"
if [ -n "$ssh_files" ]; then
    print_msg "### Authorized_keys 内容预览"
    ak_content=$(find /root /home -name "authorized_keys" 2>/dev/null | xargs cat 2>/dev/null)
    print_code "${ak_content:-文件为空}"
fi

print_msg "### /tmp 目录列举"
print_code "$(ls -la /tmp 2>/dev/null)"

print_msg "### LD_PRELOAD 检查"
print_code "$(env | grep LD_PRELOAD)"

### 8.用户登录情况 ###
print_msg "## 用户登录情况"
print_msg "### Passwd文件"
print_code "$(cat /etc/passwd)"
print_msg "### 特权用户(UID 0)"
print_code "$(awk -F: '$3==0 {print $1}' /etc/passwd)"
print_msg "### 当前登录"
print_code "$(w)"

### 9.历史命令 ###
print_msg "## 历史命令检查"
history_files=$(find /root /home -name ".bash_history" 2>/dev/null)
hist_suspicious=""
for f in $history_files; do
    matches=$(grep -E "$KEYWORDS" "$f" 2>/dev/null)
    if [ -n "$matches" ]; then
        hist_suspicious+="File: $f\n$matches\n"
    fi
done
print_code "${hist_suspicious:-未在历史命令中发现高危关键字}"

### 10.日志简要 ###
print_msg "## 最近登录成功记录"
print_code "$(grep "Accepted " /var/log/secure /var/log/auth.log 2>/dev/null | tail -n 20)"

echo ""
echo "================信息收集完成================"
echo "日志已保存至: $filename"

# =========================================================
#                   发送数据到Server - 一次性发送
# =========================================================
echo -e "\n================发送数据到Server进行AI分析================"

# 检查curl是否可用
if ! command -v curl &> /dev/null; then
  echo "[提示] 系统未安装curl，已跳过AI分析"
  echo "[提示] 系统信息已保存至本地日志文件"
  echo "[日志文件] $filename"
  echo ""
  echo "请检查网络连接或联系安全团队处理日志文件"
  echo "按任意键退出..."
  read
  exit 0
fi

# 提示用户输入Server地址
if [ -z "$SERVER_URL" ]; then
    if [ -n "$DEFAULT_SERVER_URL" ]; then
        read -p "请输入Server地址 (格式: http://IP:端口) [默认: ${DEFAULT_SERVER_URL}]: " input_server
        SERVER_URL=$(echo "$input_server" | tr -d ' \n\r')
        if [ -z "$SERVER_URL" ]; then
            SERVER_URL="$DEFAULT_SERVER_URL"
        fi
    else
        read -p "请输入Server地址 (格式: http://IP:端口): " input_server
        SERVER_URL=$(echo "$input_server" | tr -d ' \n\r')
    fi
    if [ -z "$SERVER_URL" ]; then
        echo "[错误] Server地址不能为空！"
        echo "按任意键退出..."
        read
        exit 1
    fi
    case "$SERVER_URL" in
        http://*|https://*) ;;
        *) SERVER_URL="http://$SERVER_URL" ;;
    esac
    echo "[Server地址] ${SERVER_URL}"
    echo ""
fi

# 检查Server连接
server_connected=false
echo -n "[连接测试] "
if curl -s --connect-timeout 5 "${SERVER_URL}/health" > /dev/null 2>&1; then
    echo "✅ 成功"
    echo "[Server地址] ${SERVER_URL}"
    server_connected=true
else
    echo "❌ 失败"
    echo "[错误] 无法连接到Server: ${SERVER_URL}"
    echo "[提示] 网络连接失败或Server未启动"
    server_connected=false
fi
echo ""

# 如果Server连接失败，进行离线安全检查
if [ "$server_connected" = false ]; then
    echo "═══════════════════════════════════════════════════════════════"
    echo "                    ⚠️ 网络连接失败                            "
    echo "═══════════════════════════════════════════════════════════════"
    echo "[提示] 无法连接到Server，正在进行离线安全检查..."
    echo ""
    
    # 执行离线安全检查
    perform_offline_security_check
    
    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo "[提示] 系统信息已保存至本地日志文件"
    echo "[日志文件] $filename"
    echo "═══════════════════════════════════════════════════════════════"
    echo ""
    echo "请检查网络连接或联系安全团队处理日志文件"
    echo "按任意键退出..."
    read
    exit 0
fi

# 构建IP信息
ip_info="${internal_ip} / ${public_ip}"

# 一次性发送所有数据
echo "正在发送数据到Server进行分析..."

# 读取日志内容
log_content=$(cat "$filename")

# 发送完整日志到Server（使用 /analyze_with_actions 接口获取分析报告和修复动作）
echo "[AI模式] 带自动修复动作的分析"
response=$(curl -s -X POST "${SERVER_URL}/analyze_with_actions" \
  -H "Content-Type: application/json" \
  -d "{
    \"ticket_id\": \"${input_string}\",
    \"hostname\": \"${hostname}\",
    \"ip_info\": \"${ip_info}\",
    \"platform\": \"linux\",
    \"log_content\": $(echo "$log_content" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))' 2>/dev/null || echo "\"$log_content\"")
  }" 2>&1)

# 解析响应
if command -v python3 &> /dev/null; then
    success=$(echo "$response" | python3 -c "import sys,json; print(json.load(sys.stdin).get('success', False))" 2>/dev/null)
    
    if [ "$success" = "True" ]; then
        echo "分析完成！"
        
        # 保存分析报告到本地
        analysis_file="${input_string}_analysis_report.md"
        echo "$response" | ANALYSIS_FILE="$analysis_file" python3 -c "
import sys, json, os
data = json.load(sys.stdin)
report = data.get('analysis_report', '')
with open(os.environ['ANALYSIS_FILE'], 'w', encoding='utf-8') as f:
    f.write(report)
"
        
        # 显示报告
        echo ""
        echo "=========================================="
        echo "         AI 安全应急响应分析报告          "
        echo "=========================================="
        cat "$analysis_file"
        echo "=========================================="
        echo "报告已保存至: $analysis_file"
        
        # =========================================================
        #                   上传生成的md文件到Server
        # =========================================================
        echo ""
        echo "================上传生成的md文件到Server================"
        
        # 上传日志文件
        if [ -f "$filename" ]; then
            echo "[上传] 正在上传日志文件: $filename"
            log_content=$(cat "$filename" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))' 2>/dev/null)
            upload_response=$(curl -s -X POST "${SERVER_URL}/upload" \
              -H "Content-Type: application/json" \
              -d "{
                \"filename\": \"${filename}\",
                \"content\": ${log_content}
              }" 2>&1)
            
            if command -v python3 &> /dev/null; then
                upload_success=$(echo "$upload_response" | python3 -c "import sys,json; print(json.load(sys.stdin).get('success', False))" 2>/dev/null)
                if [ "$upload_success" = "True" ]; then
                    echo "  ✅ 日志文件上传成功"
                else
                    upload_msg=$(echo "$upload_response" | python3 -c "import sys,json; print(json.load(sys.stdin).get('message', '未知错误'))" 2>/dev/null)
                    echo "  ❌ 日志文件上传失败: $upload_msg"
                fi
            fi
        else
            echo "[警告] 日志文件不存在: $filename"
        fi
        
        # 上传分析报告文件
        if [ -f "$analysis_file" ]; then
            echo "[上传] 正在上传分析报告: $analysis_file"
            report_content=$(cat "$analysis_file" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))' 2>/dev/null)
            upload_response=$(curl -s -X POST "${SERVER_URL}/upload" \
              -H "Content-Type: application/json" \
              -d "{
                \"filename\": \"${analysis_file}\",
                \"content\": ${report_content}
              }" 2>&1)
            
            if command -v python3 &> /dev/null; then
                upload_success=$(echo "$upload_response" | python3 -c "import sys,json; print(json.load(sys.stdin).get('success', False))" 2>/dev/null)
                if [ "$upload_success" = "True" ]; then
                    echo "  ✅ 分析报告上传成功"
                else
                    upload_msg=$(echo "$upload_response" | python3 -c "import sys,json; print(json.load(sys.stdin).get('message', '未知错误'))" 2>/dev/null)
                    echo "  ❌ 分析报告上传失败: $upload_msg"
                fi
            fi
        else
            echo "[警告] 分析报告文件不存在: $analysis_file"
        fi
        
        # =========================================================
        #                   自动修复操作执行（新增）
        # =========================================================
        echo ""
        echo "=========================================="
        echo "         🛠️  自动修复操作建议              "
        echo "=========================================="
        
        # 检查是否有 actions
        actions_count=$(echo "$response" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('actions', [])))" 2>/dev/null || echo "0")
        
        if [ -n "$actions_count" ] && [ "$actions_count" != "0" ]; then
            echo "[信息] AI分析了 $actions_count 条可执行的修复操作"
            echo ""
            
            # 询问用户是否执行自动修复操作
            read -p "是否执行自动修复操作？每条操作都会单独确认 (y/n): " execute_actions
            
            if [[ "$execute_actions" == "y" || "$execute_actions" == "Y" || "$execute_actions" == "yes" || "$execute_actions" == "YES" ]]; then
                # 保存 actions 到临时文件
                actions_file="${input_string}_actions.json"
                echo "$response" > "$actions_file"
                echo "[信息] 已生成操作文件: $actions_file"
                
                # 检查 action_executor.sh 是否存在
                if [ -f "./action_executor.sh" ]; then
                    chmod +x ./action_executor.sh
                    echo "[信息] 正在调用 action_executor.sh 执行操作..."
                    echo ""
                    
                    # 调用 action_executor.sh 执行操作
                    ./action_executor.sh "$actions_file"
                    
                    echo ""
                    echo "[信息] 自动修复操作执行完成"
                else
                    echo "[警告] 未找到 action_executor.sh 脚本，无法执行自动修复"
                    echo "[提示] 请确保 action_executor.sh 与本脚本在同一目录下"
                fi
            else
                echo "[信息] 用户取消执行自动修复操作"
            fi
        else
            echo "[信息] AI分析未发现需要自动修复的问题"
        fi
        
        echo ""
    else
        error=$(echo "$response" | python3 -c "import sys,json; print(json.load(sys.stdin).get('error', '未知错误'))" 2>/dev/null)
        echo "分析失败: $error"
    fi
else
    echo "Server响应:"
    echo "$response"
fi

# =========================================================
#             后续可选操作：本地漏洞扫描
# =========================================================
echo -e "\n================后续操作：本地漏洞扫描================"
read -p "数据传输流程已结束。是否继续执行本地漏洞扫描 (vuln)? (y/n): " run_vuln

if [[ "$run_vuln" == "y" || "$run_vuln" == "Y" ]]; then
    if [ -f "./vuln" ]; then
        print_msg "## 本地漏洞扫描结果"
        echo "正在执行漏洞扫描，这可能需要一些时间，请稍候..."
        
        # 执行扫描
        vuln_out=$(./vuln scan -all 2>&1 | grep 'INFO' | head -n 50)
        
        # 将结果追加到日志文件
        print_code "${vuln_out:-扫描完成，未发现严重问题或无输出}"
        echo "漏洞扫描结束，结果已追加至日志文件。"
    else
         echo "错误：未在当前目录找到 'vuln' 可执行文件，无法执行扫描。"
    fi
else
    echo "跳过漏洞扫描。"
fi

echo ""
echo "=========================================="
echo "Client端执行完毕"
echo "=========================================="
echo "注意: 本脚本不保留任何密钥数据"
echo "所有敏感信息已由Server端处理"

# =========================================================
#                   离线安全检查函数
# =========================================================
perform_offline_security_check() {
    echo "正在执行离线安全检查..."
    echo ""
    
    local findings_count=0
    
    # 1. 检查可疑进程
    echo "[1/8] 检查可疑进程..."
    local suspicious_procs=$(ps aux 2>/dev/null | grep -E "(nc|ncat|netcat|nc.traditional|/bin/sh|/bin/bash|python.*-c|perl.*-e|ruby.*-e|wget.*\|.*sh|curl.*\|.*sh)" | grep -v grep)
    if [ -n "$suspicious_procs" ]; then
        echo "  ⚠️  发现可疑进程:"
        echo "$suspicious_procs" | while read line; do
            echo "    - $line"
        done
        findings_count=$((findings_count + 1))
        print_msg "## ⚠️ 离线检查 - 可疑进程"
        print_code "$suspicious_procs"
    else
        echo "  ✅ 未发现可疑进程"
    fi
    
    # 2. 检查异常网络连接
    echo "[2/8] 检查异常网络连接..."
    local suspicious_net=$(netstat -anp 2>/dev/null | grep ESTABLISHED | grep -E "(:4444|:5555|:6666|:7777|:8888|:9999|:1234|:31337|:12345|:54321)" | head -20)
    if [ -n "$suspicious_net" ]; then
        echo "  ⚠️  发现异常网络连接:"
        echo "$suspicious_net" | while read line; do
            echo "    - $line"
        done
        findings_count=$((findings_count + 1))
        print_msg "## ⚠️ 离线检查 - 异常网络连接"
        print_code "$suspicious_net"
    else
        echo "  ✅ 未发现异常网络连接"
    fi
    
    # 3. 检查SUID/SGID文件
    echo "[3/8] 检查SUID/SGID文件..."
    local suid_files=$(find / -perm /6000 -type f 2>/dev/null | grep -E "(nmap|nc|ncat|netcat|wget|curl|python|perl|ruby|php|node)" | head -10)
    if [ -n "$suid_files" ]; then
        echo "  ⚠️  发现可疑SUID/SGID文件:"
        echo "$suid_files" | while read line; do
            echo "    - $line"
        done
        findings_count=$((findings_count + 1))
        print_msg "## ⚠️ 离线检查 - 可疑SUID/SGID文件"
        print_code "$suid_files"
    else
        echo "  ✅ 未发现可疑SUID/SGID文件"
    fi
    
    # 4. 检查最近修改的可执行文件
    echo "[4/8] 检查最近修改的可执行文件..."
    local recent_execs=$(find /tmp /var/tmp /dev/shm -type f -executable -mtime -7 2>/dev/null | head -20)
    if [ -n "$recent_execs" ]; then
        echo "  ⚠️  发现最近修改的可执行文件:"
        echo "$recent_execs" | while read line; do
            echo "    - $line"
        done
        findings_count=$((findings_count + 1))
        print_msg "## ⚠️ 离线检查 - 最近修改的可执行文件"
        print_code "$recent_execs"
    else
        echo "  ✅ 未发现最近修改的可执行文件"
    fi
    
    # 5. 检查异常crontab
    echo "[5/8] 检查异常定时任务..."
    local suspicious_cron=$(cat /etc/crontab /var/spool/cron/* /var/spool/cron/crontabs/* 2>/dev/null | grep -E "(wget|curl|nc|ncat|netcat|/dev/tcp|/dev/udp|base64|python|perl|ruby)" | grep -v "^#")
    if [ -n "$suspicious_cron" ]; then
        echo "  ⚠️  发现可疑定时任务:"
        echo "$suspicious_cron" | while read line; do
            echo "    - $line"
        done
        findings_count=$((findings_count + 1))
        print_msg "## ⚠️ 离线检查 - 可疑定时任务"
        print_code "$suspicious_cron"
    else
        echo "  ✅ 未发现可疑定时任务"
    fi
    
    # 6. 检查异常用户
    echo "[6/8] 检查异常用户..."
    local suspicious_users=$(awk -F: '$3 == 0 && $1 != "root" {print $1}' /etc/passwd 2>/dev/null)
    local shell_users=$(awk -F: '$7 ~ /(bash|sh|zsh|csh|tcsh|ksh)/ && $1 != "root" {print $1}' /etc/passwd 2>/dev/null | head -10)
    if [ -n "$suspicious_users" ]; then
        echo "  ⚠️  发现非root的UID=0用户:"
        echo "$suspicious_users" | while read line; do
            echo "    - $line"
        done
        findings_count=$((findings_count + 1))
        print_msg "## ⚠️ 离线检查 - 异常用户"
        print_code "UID=0用户:\n$suspicious_users\n\nShell用户:\n$shell_users"
    else
        echo "  ✅ 未发现异常用户"
    fi
    
    # 7. 检查异常SSH配置
    echo "[7/8] 检查SSH配置..."
    local ssh_issues=""
    if grep -q "^PermitRootLogin yes" /etc/ssh/sshd_config 2>/dev/null; then
        ssh_issues+="PermitRootLogin yes\n"
    fi
    if grep -q "^PasswordAuthentication yes" /etc/ssh/sshd_config 2>/dev/null; then
        ssh_issues+="PasswordAuthentication yes\n"
    fi
    if grep -q "^PermitEmptyPasswords yes" /etc/ssh/sshd_config 2>/dev/null; then
        ssh_issues+="PermitEmptyPasswords yes\n"
    fi
    if [ -n "$ssh_issues" ]; then
        echo "  ⚠️  发现SSH配置问题:"
        echo -e "$ssh_issues" | while read line; do
            [ -n "$line" ] && echo "    - $line"
        done
        findings_count=$((findings_count + 1))
        print_msg "## ⚠️ 离线检查 - SSH配置问题"
        print_code "$ssh_issues"
    else
        echo "  ✅ SSH配置正常"
    fi
    
    # 8. 检查异常文件权限
    echo "[8/8] 检查关键文件权限..."
    local perm_issues=""
    if [ -w /etc/passwd ] && [ ! -L /etc/passwd ]; then
        perm_issues+="/etc/passwd 可写\n"
    fi
    if [ -w /etc/shadow ] && [ ! -L /etc/shadow ]; then
        perm_issues+="/etc/shadow 可写\n"
    fi
    if [ -w /etc/sudoers ] && [ ! -L /etc/sudoers ]; then
        perm_issues+="/etc/sudoers 可写\n"
    fi
    if [ -n "$perm_issues" ]; then
        echo "  ⚠️  发现文件权限问题:"
        echo -e "$perm_issues" | while read line; do
            [ -n "$line" ] && echo "    - $line"
        done
        findings_count=$((findings_count + 1))
        print_msg "## ⚠️ 离线检查 - 文件权限问题"
        print_code "$perm_issues"
    else
        echo "  ✅ 关键文件权限正常"
    fi
    
    # 输出总结
    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo "                    离线安全检查完成                          "
    echo "═══════════════════════════════════════════════════════════════"
    if [ $findings_count -gt 0 ]; then
        echo "[警告] 发现 $findings_count 项安全问题，请人工复核"
        echo "[提示] 详细信息已记录在日志文件中"
    else
        echo "[正常] 未发现明显安全问题"
    fi
    echo "═══════════════════════════════════════════════════════════════"
}