#!/bin/bash

# ============================================================
# 自动修复命令执行器
# 功能：解析AI分析返回的修复动作列表，逐条询问用户确认后执行
# 基底：基于gaint版本（client_gaint.sh配套使用）
# 特点：每条操作都需要用户确认，高风险操作有醒目提示
# ============================================================

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# 执行统计
EXECUTED_COUNT=0
SKIPPED_COUNT=0
FAILED_COUNT=0
LOG_FILE=""

# 显示横幅
show_banner() {
    echo ""
    echo "=============================================="
    echo "     🛠️  自动修复命令执行器"
    echo "     逐条确认 · 安全可控"
    echo "=============================================="
    echo ""
}

# 记录操作日志
log_action() {
    local status=$1
    local action_desc=$2
    local command=$3
    local output=$4
    
    if [ -n "$LOG_FILE" ] && [ -f "$LOG_FILE" ]; then
        {
            echo "--- [$(date '+%Y-%m-%d %H:%M:%S')] ---"
            echo "状态: $status"
            echo "描述: $action_desc"
            echo "命令: $command"
            echo "输出: $output"
            echo ""
        } >> "$LOG_FILE"
    fi
}

# 显示操作详情
show_action_detail() {
    local index=$1
    local total=$2
    local description=$3
    local command=$4
    local risk_level=$5
    local category=$6
    
    echo ""
    echo "════════════════════════════════════════════"
    echo -e "  ${BOLD}操作 [$index/$total]${NC}"
    echo "════════════════════════════════════════════"
    
    # 风险等级颜色
    case "$risk_level" in
        high)
            echo -e "  ${RED}${BOLD}风险等级: 🔴 高危${NC}"
            ;;
        medium)
            echo -e "  ${YELLOW}${BOLD}风险等级: 🟡 中危${NC}"
            ;;
        low)
            echo -e "  ${GREEN}${BOLD}风险等级: 🟢 低危${NC}"
            ;;
        *)
            echo -e "  ${WHITE}风险等级: ⚪ 未知${NC}"
            ;;
    esac
    
    echo -e "  ${BLUE}类别:${NC} $category"
    echo ""
    echo -e "  ${WHITE}描述:${NC}"
    echo -e "  ${description}"
    echo ""
    echo -e "  ${CYAN}命令:${NC}"
    echo -e "  ${BOLD}$command${NC}"
    
    # 高风险额外警告
    if [ "$risk_level" = "high" ]; then
        echo ""
        echo -e "  ${RED}${BOLD}⚠️  高风险操作警告！${NC}"
        echo -e "  ${RED}此操作可能会对系统产生重大影响，请谨慎确认。${NC}"
    fi
    
    echo "════════════════════════════════════════════"
}

# 执行单条命令
execute_command() {
    local command=$1
    local description=$2
    local risk_level=$3
    local category=$4
    local index=$5
    local total=$6
    
    show_action_detail "$index" "$total" "$description" "$command" "$risk_level" "$category"
    
    # 如果是高风险，需要额外确认
    if [ "$risk_level" = "high" ]; then
        echo ""
        echo -ne "${RED}⚠️  高风险操作，请再次输入 YES 确认执行:${NC} "
        read -r double_confirm
        if [ "$double_confirm" != "YES" ]; then
            echo -e "${YELLOW}↻ 已跳过${NC}"
            SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
            log_action "SKIPPED" "$description" "$command" "高风险未确认"
            return
        fi
    fi
    
    echo ""
    echo -ne "${CYAN}是否执行此操作? (y=执行 / n=跳过 / v=查看详情) [默认: n]:${NC} "
    read -r confirm
    
    case "$confirm" in
        y|Y|yes|YES)
            echo ""
            echo -e "${BLUE}正在执行...${NC}"
            
            # 执行命令并捕获输出
            output=$(eval "$command" 2>&1)
            exit_code=$?
            
            if [ $exit_code -eq 0 ]; then
                echo -e "${GREEN}✅ 执行成功${NC}"
                if [ -n "$output" ]; then
                    echo -e "${WHITE}输出:${NC}"
                    echo "$output" | head -20
                    lines=$(echo "$output" | wc -l)
                    if [ "$lines" -gt 20 ]; then
                        echo -e "${YELLOW}... (输出已截断，共 $lines 行)${NC}"
                    fi
                fi
                EXECUTED_COUNT=$((EXECUTED_COUNT + 1))
                log_action "SUCCESS" "$description" "$command" "$output"
            else
                echo -e "${RED}❌ 执行失败 (退出码: $exit_code)${NC}"
                if [ -n "$output" ]; then
                    echo -e "${RED}错误信息:${NC}"
                    echo "$output" | head -10
                fi
                FAILED_COUNT=$((FAILED_COUNT + 1))
                log_action "FAILED" "$description" "$command" "Exit: $exit_code\n$output"
            fi
            ;;
        v|V)
            echo ""
            echo -e "${WHITE}预执行详情查看:${NC}"
            echo -e "${YELLOW}此操作会执行以下命令:${NC}"
            echo "  $command"
            echo ""
            echo -e "${WHITE}建议:${NC}"
            echo "  如果确认要执行，请输入 y"
            echo "  如果不确定，请输入 n 跳过"
            echo ""
            echo -ne "${CYAN}是否执行此操作? (y/n) [默认: n]:${NC} "
            read -r retry_confirm
            if [ "$retry_confirm" = "y" ] || [ "$retry_confirm" = "Y" ]; then
                # 递归调用执行
                execute_command "$command" "$description" "$risk_level" "$category" "$index" "$total"
                return
            else
                echo -e "${YELLOW}↻ 已跳过${NC}"
                SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
                log_action "SKIPPED" "$description" "$command" "用户跳过"
            fi
            ;;
        *)
            echo -e "${YELLOW}↻ 已跳过${NC}"
            SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
            log_action "SKIPPED" "$description" "$command" "用户跳过"
            ;;
    esac
}

# 从Server响应中解析并执行动作
# 参数: 
#   $1: Server返回的JSON响应（包含actions数组）
#   $2: 日志文件路径（可选，用于记录操作日志）
execute_actions_from_response() {
    local response=$1
    LOG_FILE=$2
    
    show_banner
    
    # 检查是否安装了jq或python3用于JSON解析
    if command -v python3 &> /dev/null; then
        # 使用python3解析JSON
        local actions_json
        actions_json=$(echo "$response" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    actions = data.get('actions', [])
    if not actions:
        # 尝试直接从analysis_report中解析
        report = data.get('analysis_report', '')
        if report:
            # 在报告中查找JSON块
            import re
            json_blocks = re.findall(r'\`\`\`json\s*\n(.*?)\n\`\`\`', report, re.DOTALL)
            for block in json_blocks:
                try:
                    parsed = json.loads(block.strip())
                    if isinstance(parsed, list):
                        actions = parsed
                        break
                except:
                    pass
    print(json.dumps(actions))
except Exception as e:
    print('[]')
" 2>/dev/null)
        
        local action_count
        action_count=$(echo "$actions_json" | python3 -c "
import sys, json
try:
    actions = json.load(sys.stdin)
    print(len(actions))
except:
    print('0')
" 2>/dev/null)
        
        if [ -z "$action_count" ] || [ "$action_count" = "0" ]; then
            echo -e "${YELLOW}⚠️  没有发现可执行的修复操作。${NC}"
            echo ""
            return
        fi
        
        echo -e "${GREEN}发现 $action_count 条建议修复操作${NC}"
        echo -e "${YELLOW}请逐条确认是否执行:${NC}"
        echo ""
        
        # 逐条处理
        for i in $(seq 1 $action_count); do
            local idx=$((i - 1))
            
            # 从JSON数组中提取每条action
            local item
            item=$(echo "$actions_json" | python3 -c "
import sys, json
actions = json.load(sys.stdin)
if $idx < len(actions):
    print(json.dumps(actions[$idx]))
else:
    print('{}')
" 2>/dev/null)
            
            local command=$(echo "$item" | python3 -c "
import sys, json
try:
    item = json.load(sys.stdin)
    print(item.get('command', ''))
except:
    print('')
" 2>/dev/null)
            
            local description=$(echo "$item" | python3 -c "
import sys, json
try:
    item = json.load(sys.stdin)
    print(item.get('description', ''))
except:
    print('')
" 2>/dev/null)
            
            local risk_level=$(echo "$item" | python3 -c "
import sys, json
try:
    item = json.load(sys.stdin)
    print(item.get('risk_level', 'medium'))
except:
    print('medium')
" 2>/dev/null)
            
            local category=$(echo "$item" | python3 -c "
import sys, json
try:
    item = json.load(sys.stdin)
    print(item.get('category', 'general'))
except:
    print('general')
" 2>/dev/null)
            
            if [ -n "$command" ]; then
                execute_command "$command" "$description" "$risk_level" "$category" "$i" "$action_count"
                echo ""
            fi
        done
        
    elif command -v jq &> /dev/null; then
        # 使用jq解析JSON（如果jq可用）
        local action_count
        action_count=$(echo "$response" | jq '.actions | length' 2>/dev/null)
        
        if [ -z "$action_count" ] || [ "$action_count" = "0" ] || [ "$action_count" = "null" ]; then
            echo -e "${YELLOW}⚠️  没有发现可执行的修复操作。${NC}"
            return
        fi
        
        echo -e "${GREEN}发现 $action_count 条建议修复操作${NC}"
        
        for i in $(seq 0 $((action_count - 1))); do
            local command=$(echo "$response" | jq -r ".actions[$i].command")
            local description=$(echo "$response" | jq -r ".actions[$i].description")
            local risk_level=$(echo "$response" | jq -r ".actions[$i].risk_level")
            local category=$(echo "$response" | jq -r ".actions[$i].category")
            local idx=$((i + 1))
            
            execute_command "$command" "$description" "$risk_level" "$category" "$idx" "$action_count"
            echo ""
        done
    else
        echo -e "${RED}❌ 错误: 需要 python3 或 jq 来解析JSON响应${NC}"
        echo -e "${YELLOW}请安装其中之一:${NC}"
        echo "  apt-get install python3    # Debian/Ubuntu"
        echo "  yum install python3        # CentOS/RHEL"
        echo "  apk add python3            # Alpine"
        return 1
    fi
    
    # 显示执行总结
    echo ""
    echo "=============================================="
    echo -e "     ${BOLD}执行总结${NC}"
    echo "=============================================="
    echo -e "  ${GREEN}✅ 已执行: $EXECUTED_COUNT${NC}"
    echo -e "  ${YELLOW}↻ 已跳过: $SKIPPED_COUNT${NC}"
    echo -e "  ${RED}❌ 执行失败: $FAILED_COUNT${NC}"
    
    TOTAL_ACTIONS=$((EXECUTED_COUNT + SKIPPED_COUNT + FAILED_COUNT))
    if [ $TOTAL_ACTIONS -gt 0 ]; then
        echo ""
        echo -e "  ${BLUE}执行率: $((EXECUTED_COUNT * 100 / TOTAL_ACTIONS))%${NC}"
    fi
    echo "=============================================="
    echo ""
}

# 从本地JSON文件读取并执行动作
# 参数: 
#   $1: JSON文件路径
#   $2: 日志文件路径（可选）
execute_actions_from_file() {
    local json_file=$1
    LOG_FILE=$2
    
    if [ ! -f "$json_file" ]; then
        echo -e "${RED}❌ 文件不存在: $json_file${NC}"
        return 1
    fi
    
    local content
    content=$(cat "$json_file")
    execute_actions_from_response "$content" "$LOG_FILE"
}

# ============================================================
# 主入口
# ============================================================
if [ $# -lt 1 ]; then
    echo ""
    echo "用法:"
    echo "  $0 <response.json> [log_file]"
    echo ""
    echo "参数:"
    echo "  response.json  Server返回的JSON响应文件"
    echo "  log_file       操作日志文件路径 (可选)"
    echo ""
    echo "示例:"
    echo "  $0 response.json action_log.md"
    echo ""
    echo "管道模式:"
    echo "  curl -X POST ... | $0 -"
    echo ""
    exit 1
fi

if [ "$1" = "-" ]; then
    # 从stdin读取
    input=$(cat)
    execute_actions_from_response "$input" "$2"
else
    execute_actions_from_file "$1" "$2"
fi
