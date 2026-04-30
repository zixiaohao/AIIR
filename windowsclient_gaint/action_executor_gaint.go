//go:build ignore

package main

import (
	"bufio"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"os"
	"os/exec"
	"strings"
	"syscall"
	"time"
	"unsafe"
)

// ============================================================
// 自动修复命令执行器
// 功能：解析AI分析返回的修复动作列表，逐条询问用户确认后执行
// 特点：每条操作都需要用户确认，高风险操作有醒目提示
// ============================================================

// ServerResponse Server响应结构
type ServerResponse struct {
	Success        bool     `json:"success"`
	AnalysisReport string   `json:"analysis_report"`
	Actions        []Action `json:"actions"`
	ModelUsed      string   `json:"model_used"`
	Error          string   `json:"error"`
}

// 执行统计
var (
	executedCount = 0
	skippedCount  = 0
	failedCount   = 0
	logFilePath   = ""
)

// 颜色定义 (Windows控制台)
const (
	colorReset  = ""
	colorRed    = ""
	colorGreen  = ""
	colorYellow = ""
	colorBlue   = ""
	colorCyan   = ""
	colorWhite  = ""
	colorBold   = ""
)

func init() {
	// 尝试启用ANSI颜色支持
	enableAnsiColors()
}

// enableAnsiColors 尝试启用Windows控制台的ANSI颜色支持
func enableAnsiColors() {
	// 尝试加载ENABLE_VIRTUAL_TERMINAL_PROCESSING
	kernel32 := syscall.NewLazyDLL("kernel32.dll")
	setConsoleMode := kernel32.NewProc("SetConsoleMode")
	getConsoleMode := kernel32.NewProc("GetConsoleMode")

	handle, err := syscall.GetStdHandle(syscall.STD_OUTPUT_HANDLE)
	if err != nil {
		return
	}

	var mode uint32
	// 获取当前控制台模式
	ret, _, _ := getConsoleMode.Call(uintptr(handle), uintptr(unsafe.Pointer(&mode)))
	if ret == 0 {
		return
	}
	mode |= 0x0004 // ENABLE_VIRTUAL_TERMINAL_PROCESSING
	setConsoleMode.Call(uintptr(handle), uintptr(mode))
}

// 显示横幅
func showBanner() {
	fmt.Println()
	fmt.Println("==============================================")
	fmt.Println("     🛠️  自动修复命令执行器")
	fmt.Println("     逐条确认 · 安全可控")
	fmt.Println("==============================================")
	fmt.Println()
}

// 记录操作日志
func logAction(status, desc, command, output string) {
	if logFilePath == "" {
		return
	}

	f, err := os.OpenFile(logFilePath, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		return
	}
	defer f.Close()

	timestamp := time.Now().Format("2006-01-02 15:04:05")
	logEntry := fmt.Sprintf("--- [%s] ---\n状态: %s\n描述: %s\n命令: %s\n输出: %s\n\n",
		timestamp, status, desc, command, output)
	f.WriteString(logEntry)
}

// showActionDetail 显示操作详情
func showActionDetail(index, total int, description, command, riskLevel, category string) {
	fmt.Println()
	fmt.Println("════════════════════════════════════════════")
	fmt.Printf("  操作 [%d/%d]\n", index, total)
	fmt.Println("════════════════════════════════════════════")

	// 风险等级
	riskIcon := "⚪"
	riskColor := ""
	switch riskLevel {
	case "high":
		riskIcon = "🔴"
		fmt.Printf("  风险等级: 🔴 高危\n")
	case "medium":
		riskIcon = "🟡"
		fmt.Printf("  风险等级: 🟡 中危\n")
	case "low":
		riskIcon = "🟢"
		fmt.Printf("  风险等级: 🟢 低危\n")
	default:
		fmt.Printf("  风险等级: ⚪ 未知\n")
	}
	_ = riskIcon
	_ = riskColor

	fmt.Printf("  类别: %s\n", category)
	fmt.Println()
	fmt.Println("  描述:")
	fmt.Printf("  %s\n", description)
	fmt.Println()
	fmt.Println("  命令:")
	fmt.Printf("  %s\n", command)

	// 高风险额外警告
	if riskLevel == "high" {
		fmt.Println()
		fmt.Println("  ⚠️  高风险操作警告！")
		fmt.Println("  此操作可能会对系统产生重大影响，请谨慎确认。")
	}

	fmt.Println("════════════════════════════════════════════")
}

// executeCommand 执行单条命令
func executeCommand(command, description, riskLevel, category string, index, total int) {
	showActionDetail(index, total, description, command, riskLevel, category)

	reader := bufio.NewReader(os.Stdin)

	// 如果是高风险，需要额外确认
	if riskLevel == "high" {
		fmt.Println()
		fmt.Print("⚠️  高风险操作，请再次输入 YES 确认执行: ")
		doubleConfirm, _ := reader.ReadString('\n')
		doubleConfirm = strings.TrimSpace(doubleConfirm)
		if doubleConfirm != "YES" {
			fmt.Println("↻ 已跳过")
			skippedCount++
			logAction("SKIPPED", description, command, "高风险未确认")
			return
		}
	}

	fmt.Println()
	fmt.Print("是否执行此操作? (y=执行 / n=跳过 / v=查看详情) [默认: n]: ")
	confirm, _ := reader.ReadString('\n')
	confirm = strings.TrimSpace(confirm)

	switch strings.ToLower(confirm) {
	case "y", "yes":
		fmt.Println()
		fmt.Println("正在执行...")

		// 执行命令（使用cmd /c包装以支持管道和重定向）
		cmd := exec.Command("cmd", "/c", command)
		cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: false}
		output, err := cmd.CombinedOutput()
		outputStr := string(output)

		if err == nil {
			fmt.Println("✅ 执行成功")
			if strings.TrimSpace(outputStr) != "" {
				fmt.Println("输出:")
				lines := strings.Split(outputStr, "\n")
				for i, line := range lines {
					if i >= 20 {
						fmt.Printf("... (输出已截断，共 %d 行)\n", len(lines))
						break
					}
					fmt.Println(line)
				}
			}
			executedCount++
			logAction("SUCCESS", description, command, outputStr)
		} else {
			fmt.Printf("❌ 执行失败: %v\n", err)
			if strings.TrimSpace(outputStr) != "" {
				fmt.Println("错误信息:")
				lines := strings.Split(outputStr, "\n")
				for i, line := range lines {
					if i >= 10 {
						break
					}
					fmt.Println(line)
				}
			}
			failedCount++
			logAction("FAILED", description, command, fmt.Sprintf("Error: %v\n%s", err, outputStr))
		}

	case "v", "view":
		fmt.Println()
		fmt.Println("预执行详情查看:")
		fmt.Println("此操作会执行以下命令:")
		fmt.Printf("  %s\n", command)
		fmt.Println()
		fmt.Println("建议:")
		fmt.Println("  如果确认要执行，请输入 y")
		fmt.Println("  如果不确定，请输入 n 跳过")
		fmt.Println()
		fmt.Print("是否执行此操作? (y/n) [默认: n]: ")
		retryConfirm, _ := reader.ReadString('\n')
		retryConfirm = strings.TrimSpace(retryConfirm)
		if strings.ToLower(retryConfirm) == "y" || strings.ToLower(retryConfirm) == "yes" {
			// 重新执行
			executeCommand(command, description, riskLevel, category, index, total)
			return
		} else {
			fmt.Println("↻ 已跳过")
			skippedCount++
			logAction("SKIPPED", description, command, "用户跳过")
		}

	default:
		fmt.Println("↻ 已跳过")
		skippedCount++
		logAction("SKIPPED", description, command, "用户跳过")
	}
}

// executeActionsFromResponse 从Server响应中解析并执行动作
func executeActionsFromResponse(responseData string) {
	showBanner()

	var response ServerResponse
	err := json.Unmarshal([]byte(responseData), &response)
	if err != nil {
		fmt.Printf("❌ 解析JSON响应失败: %v\n", err)
		return
	}

	actions := response.Actions

	// 如果actions为空，尝试从analysis_report中解析
	if len(actions) == 0 && response.AnalysisReport != "" {
		actions = parseActionsFromReport(response.AnalysisReport)
	}

	if len(actions) == 0 {
		fmt.Println("⚠️  没有发现可执行的修复操作。")
		fmt.Println()
		return
	}

	fmt.Printf("发现 %d 条建议修复操作\n", len(actions))
	fmt.Println("请逐条确认是否执行:")
	fmt.Println()

	for i, action := range actions {
		executeCommand(action.Command, action.Description, action.RiskLevel, action.Category, i+1, len(actions))
		fmt.Println()
	}

	// 显示执行总结
	showSummary()
}

// parseActionsFromReport 尝试从报告中解析JSON格式的动作
func parseActionsFromReport(report string) []Action {
	var actions []Action

	// 尝试寻找JSON代码块
	// 简单查找 ```json ... ``` 之间的内容
	lines := strings.Split(report, "\n")
	inJSONBlock := false
	var jsonLines []string

	for _, line := range lines {
		trimmed := strings.TrimSpace(line)
		if strings.HasPrefix(trimmed, "```json") {
			inJSONBlock = true
			jsonLines = nil
			continue
		}
		if inJSONBlock && strings.HasPrefix(trimmed, "```") {
			inJSONBlock = false
			// 尝试解析收集到的JSON
			jsonStr := strings.Join(jsonLines, "\n")
			var parsed []Action
			if err := json.Unmarshal([]byte(jsonStr), &parsed); err == nil {
				actions = append(actions, parsed...)
			}
			continue
		}
		if inJSONBlock {
			jsonLines = append(jsonLines, line)
		}
	}

	return actions
}

// showSummary 显示执行总结
func showSummary() {
	fmt.Println()
	fmt.Println("==============================================")
	fmt.Println("     执行总结")
	fmt.Println("==============================================")
	fmt.Printf("  ✅ 已执行: %d\n", executedCount)
	fmt.Printf("  ↻ 已跳过: %d\n", skippedCount)
	fmt.Printf("  ❌ 执行失败: %d\n", failedCount)

	total := executedCount + skippedCount + failedCount
	if total > 0 {
		rate := executedCount * 100 / total
		fmt.Printf("  执行率: %d%%\n", rate)
	}
	fmt.Println("==============================================")
	fmt.Println()
}

// readResponseFromFile 从文件读取JSON响应
func readResponseFromFile(filepath string) (string, error) {
	f, err := os.Open(filepath)
	if err != nil {
		return "", fmt.Errorf("无法打开文件: %v", err)
	}
	defer f.Close()

	data, err := io.ReadAll(f)
	if err != nil {
		return "", fmt.Errorf("读取文件失败: %v", err)
	}

	return string(data), nil
}

// main 主函数
func main() {
	// 命令行参数
	var (
		responseFile string
		logFile      string
		showHelp     bool
	)

	flag.StringVar(&responseFile, "f", "", "Server返回的JSON响应文件路径")
	flag.StringVar(&responseFile, "file", "", "Server返回的JSON响应文件路径")
	flag.StringVar(&logFile, "l", "", "操作日志文件路径")
	flag.StringVar(&logFile, "log", "", "操作日志文件路径")
	flag.BoolVar(&showHelp, "h", false, "显示帮助信息")
	flag.BoolVar(&showHelp, "help", false, "显示帮助信息")
	flag.Parse()

	if showHelp {
		fmt.Println("自动修复命令执行器")
		fmt.Println()
		fmt.Println("用法:")
		fmt.Println("  action_executor_gaint.exe -f <response.json> [-l <log_file>]")
		fmt.Println("  type response.json | action_executor_gaint.exe")
		fmt.Println()
		fmt.Println("参数:")
		fmt.Println("  -f, --file    Server返回的JSON响应文件路径 (必需或通过管道输入)")
		fmt.Println("  -l, --log     操作日志文件路径 (可选)")
		fmt.Println("  -h, --help    显示此帮助信息")
		fmt.Println()
		fmt.Println("示例:")
		fmt.Println("  action_executor_gaint.exe -f response.json")
		fmt.Println("  action_executor_gaint.exe -f response.json -l action_log.md")
		fmt.Println("  curl -X POST ... | action_executor_gaint.exe")
		fmt.Println()
		fmt.Println("JSON响应格式:")
		fmt.Println("  {\"actions\": [{\"command\": \"...\", \"description\": \"...\",")
		fmt.Println("    \"risk_level\": \"high/medium/low\", \"category\": \"...\"}]}")
		fmt.Println()
		return
	}

	// 设置日志文件
	logFilePath = logFile

	// 从文件或标准输入读取
	var responseData string

	if responseFile != "" {
		// 从文件读取
		data, err := readResponseFromFile(responseFile)
		if err != nil {
			fmt.Printf("❌ 读取文件失败: %v\n", err)
			os.Exit(1)
		}
		responseData = data
	} else {
		// 检查是否有管道输入
		stat, _ := os.Stdin.Stat()
		if (stat.Mode() & os.ModeCharDevice) == 0 {
			// 有管道输入
			data, err := io.ReadAll(os.Stdin)
			if err != nil {
				fmt.Printf("❌ 读取标准输入失败: %v\n", err)
				os.Exit(1)
			}
			responseData = string(data)
		} else {
			fmt.Println("❌ 请输入JSON响应文件路径 (-f 参数) 或通过管道传入数据")
			fmt.Println("使用 -h 参数查看帮助信息")
			os.Exit(1)
		}
	}

	// 执行动作
	executeActionsFromResponse(responseData)

	// 等待用户按回车退出
	if logFilePath != "" {
		fmt.Printf("[日志文件] %s\n", logFilePath)
	}
	fmt.Println("按回车键退出...")
	fmt.Scanln()
}
