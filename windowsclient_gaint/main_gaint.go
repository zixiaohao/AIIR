package main

import (
	"bufio"
	"bytes"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strings"
	"syscall"
	"time"

	"golang.org/x/text/encoding/simplifiedchinese"
	"golang.org/x/text/transform"
	"golang.org/x/sys/windows"
)

// 全局变量
var (
	serverURL        string
	logFile          string
	keywordsRegex    *regexp.Regexp
	attackPatterns   map[string][]AttackPattern
)

// AttackPattern 攻击模式定义
type AttackPattern struct {
	Pattern     string `json:"pattern"`
	CVE         string `json:"cve"`
	Description string `json:"description"`
	Severity    string `json:"severity"`
	Category    string `json:"category"`
}

// AttackPatternsResponse 特征库响应
type AttackPatternsResponse struct {
	Success  bool                      `json:"success"`
	Patterns map[string][]AttackPattern `json:"patterns"`
	Error    string                    `json:"error"`
}

func init() {
	keywordsRegex = regexp.MustCompile(`(powershell.*-enc|cmd\.exe|certutil|bitsadmin|wmic|vssadmin|net user|net group|net localgroup|whoami|ipconfig|sc stop|sc delete|reg add|reg delete|rundll32|mshta|cscript|wscript)`)
	attackPatterns = make(map[string][]AttackPattern)
}

// 检查是否以管理员权限运行
func checkAdmin() bool {
	_, err := os.Open("\\\\.\\PHYSICALDRIVE0")
	return err == nil
}

// 请求管理员权限（UAC提升）
func requestElevation() {
	verb := "runas"
	exe, _ := os.Executable()
	cwd, _ := os.Getwd()

	verbPtr, _ := syscall.UTF16PtrFromString(verb)
	exePtr, _ := syscall.UTF16PtrFromString(exe)
	cwdPtr, _ := syscall.UTF16PtrFromString(cwd)
	argPtr, _ := syscall.UTF16PtrFromString("")

	var showCmd int32 = 1 // SW_SHOWNORMAL

	err := windows.ShellExecute(0, verbPtr, exePtr, argPtr, cwdPtr, showCmd)
	if err != nil {
		fmt.Printf("[错误] 无法请求管理员权限: %v\n", err)
		fmt.Println("请手动右键点击程序，选择'以管理员身份运行'")
		fmt.Println("按回车键退出...")
		fmt.Scanln()
		os.Exit(1)
	}
	os.Exit(0)
}

// 显示标题
func showBanner() {
	fmt.Println("╔══════════════════════════════════════════════════════════════╗")
	fmt.Println("║           Windows 安全应急响应检测工具                      ║")
	fmt.Println("║                    CS客户端版 v3.1                          ║")
	fmt.Println("╠══════════════════════════════════════════════════════════════╣")
	fmt.Println("║  功能: 收集系统安全信息，发送到Server进行AI分析             ║")
	fmt.Println("║  特点: 分批分析、动态特征库、报告保存                       ║")
	fmt.Println("╚══════════════════════════════════════════════════════════════╝")
	fmt.Println()
}

// 显示进度条
func showProgress(current, total int, message string) {
	percent := int(float64(current) / float64(total) * 100)
	barLength := 40
	filledLength := int(float64(barLength) * float64(percent) / 100)

	bar := strings.Repeat("█", filledLength) + strings.Repeat("░", barLength-filledLength)
	fmt.Printf("\r[%s] %d%% %s", bar, percent, message)
	if current == total {
		fmt.Println()
	}
}

// 显示状态
func showStatus(status string, success bool) {
	if success {
		fmt.Printf("  ✅ %s\n", status)
	} else {
		fmt.Printf("  ❌ %s\n", status)
	}
}

// 从Server获取攻击特征库
func fetchAttackPatterns() bool {
	fmt.Print("[特征库] 正在从Server获取攻击特征库...")

	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Get(serverURL + "/attack_patterns")
	if err != nil {
		fmt.Println(" ❌ 失败")
		fmt.Printf("[警告] 无法获取特征库: %v\n", err)
		return false
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		fmt.Println(" ❌ 失败")
		fmt.Printf("[警告] 读取响应失败: %v\n", err)
		return false
	}

	var response AttackPatternsResponse
	err = json.Unmarshal(body, &response)
	if err != nil {
		fmt.Println(" ❌ 失败")
		fmt.Printf("[警告] 解析特征库失败: %v\n", err)
		return false
	}

	if response.Success {
		attackPatterns = response.Patterns
		fmt.Println(" ✅ 成功")
		fmt.Printf("[特征库] 已加载 %d 类攻击特征\n", len(attackPatterns))
		return true
	} else {
		fmt.Println(" ❌ 失败")
		fmt.Printf("[警告] %s\n", response.Error)
		return false
	}
}

func main() {
	// 解析命令行参数
	var serverAddr string
	var showHelp bool
	flag.StringVar(&serverAddr, "s", "", "Server地址 (格式: http://IP:端口)")
	flag.StringVar(&serverAddr, "server", "", "Server地址 (格式: http://IP:端口)")
	flag.BoolVar(&showHelp, "h", false, "显示帮助信息")
	flag.BoolVar(&showHelp, "help", false, "显示帮助信息")
	flag.Parse()

	// 显示帮助信息
	if showHelp {
		fmt.Println("Windows 安全应急响应检测工具 v3.1 (gaint版本)")
		fmt.Println()
		fmt.Println("用法:")
		fmt.Println("  windows_check_gaint.exe -s <Server地址>")
		fmt.Println("  windows_check_gaint.exe --server <Server地址>")
		fmt.Println()
		fmt.Println("参数:")
		fmt.Println("  -s, --server    指定Server地址 (格式: http://IP:端口)")
		fmt.Println("  -h, --help      显示此帮助信息")
		fmt.Println()
		fmt.Println("示例:")
		fmt.Println("  windows_check_gaint.exe -s http://192.168.1.100:8000")
		fmt.Println("  windows_check_gaint.exe --server http://10.0.0.50:8000")
		fmt.Println()
		fmt.Println("注意:")
		fmt.Println("  - 程序需要管理员权限运行")
		fmt.Println("  - 如果不指定Server地址，程序将询问用户输入")
		fmt.Println("  - gaint版本采用一次性发送模式，适合大上下文窗口模型")
		return
	}

	// 设置Server地址
	if serverAddr == "" {
		fmt.Print("请输入Server地址 (格式: http://IP:端口): ")
		reader := bufio.NewReader(os.Stdin)
		input, _ := reader.ReadString('\n')
		serverURL = strings.TrimSpace(input)
		
		if serverURL == "" {
			fmt.Println("[错误] Server地址不能为空！")
			fmt.Println("[提示] 使用 -h 参数查看帮助信息")
			fmt.Println("按回车键退出...")
			fmt.Scanln()
			return
		}
	} else {
		serverURL = serverAddr
	}

	// 验证Server地址格式
	if !strings.HasPrefix(serverURL, "http://") && !strings.HasPrefix(serverURL, "https://") {
		serverURL = "http://" + serverURL
	}
	
	fmt.Printf("[Server地址] %s\n", serverURL)
	fmt.Println()

	// 检查管理员权限
	if !checkAdmin() {
		fmt.Println("[提示] 程序需要管理员权限才能完整收集系统信息")
		fmt.Println("[提示] 正在请求管理员权限...")
		time.Sleep(1 * time.Second)
		requestElevation()
	}

	showBanner()

	fmt.Println("[权限状态] ✅ 管理员权限")
	fmt.Println()

	// 从Server获取攻击特征库
	fetchAttackPatterns()
	fmt.Println()

	// 检查Server连接
	serverConnected := false
	fmt.Print("[连接测试] ")
	client := &http.Client{Timeout: 5 * time.Second}
	resp, err := client.Get(serverURL + "/health")
	if err != nil {
		fmt.Println("❌ 失败")
		fmt.Printf("[错误] 无法连接到Server: %s\n", serverURL)
		fmt.Println("[提示] 网络连接失败或Server未启动")
		serverConnected = false
	} else {
		resp.Body.Close()
		fmt.Println("✅ 成功")
		serverConnected = true
	}
	fmt.Println()

	// 获取工单ID
	fmt.Print("请输入工单ID: ")
	reader := bufio.NewReader(os.Stdin)
	ticketID, _ := reader.ReadString('\n')
	ticketID = strings.TrimSpace(ticketID)

	if ticketID == "" {
		fmt.Println("[错误] 工单ID不能为空！")
		fmt.Println("按回车键退出...")
		fmt.Scanln()
		return
	}

	// 获取主机名
	hostname, _ := os.Hostname()

	// 设置文件名
	logFile = fmt.Sprintf("%s_log.md", ticketID)

	// 创建日志文件
	f, err := os.Create(logFile)
	if err != nil {
		fmt.Printf("[错误] 创建日志文件失败: %v\n", err)
		fmt.Println("按回车键退出...")
		fmt.Scanln()
		return
	}
	f.Close()

	fmt.Println()
	fmt.Println("═══════════════════════════════════════════════════════════════")
	fmt.Println("                    开始收集系统信息                          ")
	fmt.Println("═══════════════════════════════════════════════════════════════")
	fmt.Println()

	// 显示收集进度
	totalSteps := 10
	currentStep := 0

	currentStep++
	showProgress(currentStep, totalSteps, "正在收集系统信息...")
	checkSystemInfo()
	showStatus("系统信息收集完成", true)

	currentStep++
	showProgress(currentStep, totalSteps, "正在检查用户账户...")
	checkUsers()
	showStatus("用户账户检查完成", true)

	currentStep++
	showProgress(currentStep, totalSteps, "正在检查持久化...")
	checkAdvancedPersistence()
	showStatus("持久化检查完成", true)

	currentStep++
	showProgress(currentStep, totalSteps, "正在检查网络连接...")
	checkNetwork()
	showStatus("网络连接检查完成", true)

	currentStep++
	showProgress(currentStep, totalSteps, "正在检查用户活动...")
	checkUserActivity()
	showStatus("用户活动检查完成", true)

	currentStep++
	showProgress(currentStep, totalSteps, "正在检查WebShell...")
	checkWebShell()
	showStatus("WebShell检查完成", true)

	currentStep++
	showProgress(currentStep, totalSteps, "正在检查进程...")
	checkProcesses()
	showStatus("进程检查完成", true)

	currentStep++
	showProgress(currentStep, totalSteps, "正在检查启动项...")
	checkStartup()
	showStatus("启动项检查完成", true)

	currentStep++
	showProgress(currentStep, totalSteps, "正在检查安全日志...")
	checkSecurityLogs()
	showStatus("安全日志检查完成", true)

	currentStep++
	showProgress(currentStep, totalSteps, "正在检查OA/ERP系统...")
	checkOASecurity()
	showStatus("OA/ERP检查完成", true)

	fmt.Println()
	fmt.Println("═══════════════════════════════════════════════════════════════")
	fmt.Println("                    信息收集完成                              ")
	fmt.Println("═══════════════════════════════════════════════════════════════")
	fmt.Printf("[日志文件] %s\n", logFile)
	fmt.Println()

	// 根据Server连接状态决定是否发送数据
	if !serverConnected {
		fmt.Println()
		fmt.Println("═══════════════════════════════════════════════════════════════")
		fmt.Println("                    ⚠️ 网络连接失败                            ")
		fmt.Println("═══════════════════════════════════════════════════════════════")
		fmt.Println("[提示] 无法连接到Server，正在进行离线安全检查...")
		fmt.Println()
		
		// 执行离线安全检查
		performOfflineSecurityCheck()
		
		fmt.Println()
		fmt.Println("═══════════════════════════════════════════════════════════════")
		fmt.Println("[提示] 系统信息已保存至本地日志文件")
		fmt.Printf("[日志文件] %s\n", logFile)
		fmt.Println("═══════════════════════════════════════════════════════════════")
		fmt.Println()
		fmt.Println("请检查网络连接或联系安全团队处理日志文件")
		fmt.Println("按任意键退出程序...")
		fmt.Scanln()
		return
	}

	// Server连接正常，启动AI分析（使用Server默认模型）
	fmt.Println("[AI分析] 正在发送数据到Server进行分析...")
	sendDataToServer(ticketID, hostname)

	// AI分析完成后询问是否进行OA/ERP深度分析
	fmt.Println()
	fmt.Print("是否进行OA/ERP系统高频漏洞日志深度分析? (y/n): ")
	confirm, _ := reader.ReadString('\n')
	confirm = strings.TrimSpace(confirm)

	if strings.ToLower(confirm) == "y" {
		checkOASecurityDeepScan()
	}

	fmt.Println()
	fmt.Println("═══════════════════════════════════════════════════════════════")
	fmt.Println("按回车键退出程序...")
	fmt.Scanln()
}

// 检查Server连接
func checkServerConnection() bool {
	client := &http.Client{Timeout: 5 * time.Second}
	resp, err := client.Get(serverURL + "/health")
	if err != nil {
		return false
	}
	defer resp.Body.Close()
	return resp.StatusCode == 200
}

// 写入日志并输出到控制台
func writeLog(section string) {
	fmt.Printf("\n[%s]\n", section)
	content := fmt.Sprintf("\n## %s\n\n", section)
	appendToFile(logFile, content)
}

// 写入代码块到日志
func writeCode(code string) {
	fmt.Println(code)
	content := fmt.Sprintf("```\n%s\n```\n\n", code)
	appendToFile(logFile, content)
}

// 追加内容到文件
func appendToFile(filename, content string) {
	f, err := os.OpenFile(filename, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		return
	}
	defer f.Close()
	f.WriteString(content)
}

// GBK转UTF-8
func gbkToUtf8(s []byte) ([]byte, error) {
	reader := transform.NewReader(bytes.NewReader(s), simplifiedchinese.GBK.NewDecoder())
	return io.ReadAll(reader)
}

// 执行命令并返回输出（自动处理GBK编码）
func execCommand(name string, args ...string) string {
	cmd := exec.Command(name, args...)
	cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true}
	output, err := cmd.CombinedOutput()
	if err != nil {
		return fmt.Sprintf("错误: %v\n%s", err, string(output))
	}

	// 尝试将GBK编码转换为UTF-8
	utf8Output, err := gbkToUtf8(output)
	if err != nil {
		// 转换失败，返回原始内容
		return string(output)
	}
	return string(utf8Output)
}

// 发送数据到Server - 一次性发送模式
func sendDataToServer(ticketID, hostname string) {
	fmt.Println()
	fmt.Println("═══════════════════════════════════════════════════════════════")
	fmt.Println("              发送数据到Server - 一次性发送模式               ")
	fmt.Println("═══════════════════════════════════════════════════════════════")

	// 读取日志内容
	content, err := os.ReadFile(logFile)
	if err != nil {
		fmt.Printf("[错误] 读取日志文件失败: %v\n", err)
		return
	}

	// 获取IP信息
	ipInfo := getIPInfo()

	// 构建完整请求（使用Server默认模型）
	requestBody := map[string]interface{}{
		"ticket_id":   ticketID,
		"hostname":    hostname,
		"ip_info":     ipInfo,
		"platform":    "windows",
		"log_content": string(content),
	}

	jsonBody, err := json.Marshal(requestBody)
	if err != nil {
		fmt.Printf("[错误] JSON编码失败: %v\n", err)
		return
	}

	// 发送请求
	fmt.Printf("[发送请求] %s\n", serverURL)
	resp, err := http.Post(serverURL+"/analyze_full", "application/json", bytes.NewBuffer(jsonBody))
	if err != nil {
		fmt.Printf("[错误] 发送失败: %v\n", err)
		return
	}
	defer resp.Body.Close()

	// 读取响应
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		fmt.Printf("[错误] 读取响应失败: %v\n", err)
		return
	}

	// 解析响应
	var response struct {
		Success        bool   `json:"success"`
		Error          string `json:"error"`
		AnalysisReport string `json:"analysis_report"`
		ModelUsed      string `json:"model_used"`
	}

	err = json.Unmarshal(body, &response)
	if err != nil {
		fmt.Printf("[错误] 解析响应失败: %v\n", err)
		return
	}

	if response.Success {
		fmt.Println()
		fmt.Println("✅ 分析完成!")
		fmt.Printf("[分析系统] 安全应急响应分析平台\n")
		if response.ModelUsed != "" {
			fmt.Printf("[使用的模型] %s\n", response.ModelUsed)
		}

		// 保存分析报告到本地
		reportFile := fmt.Sprintf("%s_analysis_report.md", ticketID)
		err = os.WriteFile(reportFile, []byte(response.AnalysisReport), 0644)
		if err != nil {
			fmt.Printf("[警告] 保存报告失败: %v\n", err)
		} else {
			fmt.Println()
			fmt.Println("═══════════════════════════════════════════════════════════════")
			fmt.Println("                AI 安全应急响应分析报告                        ")
			fmt.Println("═══════════════════════════════════════════════════════════════")
			fmt.Println(response.AnalysisReport)
			fmt.Println("═══════════════════════════════════════════════════════════════")
			fmt.Printf("[报告已保存] %s\n", reportFile)
		}

		// =========================================================
		//                   上传生成的md文件到Server
		// =========================================================
		fmt.Println()
		fmt.Println("═══════════════════════════════════════════════════════════════")
		fmt.Println("              上传生成的md文件到Server                        ")
		fmt.Println("═══════════════════════════════════════════════════════════════")

		// 上传日志文件
		fmt.Printf("[上传] 正在上传日志文件: %s\n", logFile)
		logContent, err := os.ReadFile(logFile)
		if err != nil {
			fmt.Printf("  ❌ 读取日志文件失败: %v\n", err)
		} else {
			uploadLogRequest := map[string]interface{}{
				"filename": logFile,
				"content":  string(logContent),
			}
			uploadLogJsonBody, _ := json.Marshal(uploadLogRequest)
			uploadLogResp, err := http.Post(serverURL+"/upload", "application/json", bytes.NewBuffer(uploadLogJsonBody))
			if err != nil {
				fmt.Printf("  ❌ 日志文件上传失败: %v\n", err)
			} else {
				uploadLogBody, _ := io.ReadAll(uploadLogResp.Body)
				uploadLogResp.Body.Close()
				var uploadLogResponse struct {
					Success bool   `json:"success"`
					Message string `json:"message"`
				}
				json.Unmarshal(uploadLogBody, &uploadLogResponse)
				if uploadLogResponse.Success {
					fmt.Println("  ✅ 日志文件上传成功")
				} else {
					fmt.Printf("  ❌ 日志文件上传失败: %s\n", uploadLogResponse.Message)
				}
			}
		}

		// 上传分析报告文件
		if _, err := os.Stat(reportFile); err == nil {
			fmt.Printf("[上传] 正在上传分析报告: %s\n", reportFile)
			reportContent, err := os.ReadFile(reportFile)
			if err != nil {
				fmt.Printf("  ❌ 读取分析报告失败: %v\n", err)
			} else {
				uploadReportRequest := map[string]interface{}{
					"filename": reportFile,
					"content":  string(reportContent),
				}
				uploadReportJsonBody, _ := json.Marshal(uploadReportRequest)
				uploadReportResp, err := http.Post(serverURL+"/upload", "application/json", bytes.NewBuffer(uploadReportJsonBody))
				if err != nil {
					fmt.Printf("  ❌ 分析报告上传失败: %v\n", err)
				} else {
					uploadReportBody, _ := io.ReadAll(uploadReportResp.Body)
					uploadReportResp.Body.Close()
					var uploadReportResponse struct {
						Success bool   `json:"success"`
						Message string `json:"message"`
					}
					json.Unmarshal(uploadReportBody, &uploadReportResponse)
					if uploadReportResponse.Success {
						fmt.Println("  ✅ 分析报告上传成功")
					} else {
						fmt.Printf("  ❌ 分析报告上传失败: %s\n", uploadReportResponse.Message)
					}
				}
			}
		} else {
			fmt.Printf("[警告] 分析报告文件不存在: %s\n", reportFile)
		}

		fmt.Println()
	} else {
		fmt.Printf("[错误] Server返回错误: %s\n", response.Error)
	}
}

// 获取IP信息
func getIPInfo() string {
	ipInfo := execCommand("ipconfig")
	lines := strings.Split(ipInfo, "\n")
	for _, line := range lines {
		line = strings.TrimSpace(line)
		if strings.Contains(line, "IPv4") || strings.Contains(line, "IP Address") {
			// 提取IP地址
			parts := strings.Split(line, ":")
			if len(parts) > 1 {
				ip := strings.TrimSpace(parts[1])
				if len(ip) > 7 && ip != "127.0.0.1" {
					return ip
				}
			}
		}
	}
	return "未知"
}

// 执行命令，如果失败则使用备选方案
func execCommandWithFallback(primary string, primaryArgs []string, fallback string, fallbackArgs []string) string {
	// 尝试主命令
	cmd := exec.Command(primary, primaryArgs...)
	cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true}
	output, err := cmd.CombinedOutput()

	if err == nil {
		// 主命令成功，尝试转换编码
		utf8Output, convErr := gbkToUtf8(output)
		if convErr == nil {
			return string(utf8Output)
		}
		return string(output)
	}

	// 主命令失败，使用备选方案
	fmt.Printf(" [wmic不可用，使用备选方案]")
	cmd = exec.Command(fallback, fallbackArgs...)
	cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true}
	output, err = cmd.CombinedOutput()
	if err != nil {
		return fmt.Sprintf("错误: %v\n%s", err, string(output))
	}

	utf8Output, convErr := gbkToUtf8(output)
	if convErr != nil {
		return string(output)
	}
	return string(utf8Output)
}

// 1. 系统信息
func checkSystemInfo() {
	writeLog("系统信息")

	// 操作系统信息 - 优先使用wmic，失败则使用systeminfo
	osInfo := execCommandWithFallback(
		"wmic", []string{"os", "get", "Caption,Version,LastBootUpTime", "/format:list"},
		"systeminfo", []string{"/fo", "list"},
	)
	// 只保留前30行避免输出过长
	lines := strings.Split(osInfo, "\n")
	if len(lines) > 30 {
		osInfo = strings.Join(lines[:30], "\n") + "\n... (已截断)"
	}
	writeCode(osInfo)

	// IP地址信息 - 优先使用wmic，失败则使用ipconfig
	ipInfo := execCommandWithFallback(
		"wmic", []string{"nicconfig", "where", "IPEnabled=True", "get", "Description,IPAddress", "/format:list"},
		"ipconfig", []string{"/all"},
	)
	writeCode(ipInfo)

	// 主机名
	hostname := execCommand("hostname")
	writeCode(fmt.Sprintf("主机名: %s", strings.TrimSpace(hostname)))
}

// 2. 用户取证
func checkUsers() {
	writeLog("用户取证")

	// 所有本地用户 - 优先使用wmic，失败则使用net user
	writeLog("所有本地用户")
	users := execCommandWithFallback(
		"wmic", []string{"useraccount", "get", "Name,Disabled,PasswordChangeable,PasswordExpires,PasswordRequired", "/format:list"},
		"net", []string{"user"},
	)
	writeCode(users)

	// 管理员组成员
	writeLog("管理员组成员")
	admins := execCommand("net", "localgroup", "Administrators")
	writeCode(admins)

	// 隐藏/影子账户（注册表检查）
	writeLog("隐藏/影子账户（注册表检查）")
	hiddenUsers := execCommand("reg", "query", "HKLM\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\Winlogon\\SpecialAccounts\\UserList", "/s")
	if strings.Contains(hiddenUsers, "ERROR") {
		writeCode("UserList注册表键不存在（干净）。")
	} else {
		writeCode(hiddenUsers)
	}

	// 带有'$'后缀的账户 - 优先使用wmic，失败则使用PowerShell
	writeLog("带有'$'后缀的账户")
	allUsers := execCommandWithFallback(
		"wmic", []string{"useraccount", "get", "Name", "/format:list"},
		"powershell", []string{"-Command", "Get-LocalUser | Where-Object {$_.Name -like '*$'} | Select-Object Name, Enabled | Format-Table -AutoSize"},
	)

	// 如果是wmic输出，过滤$后缀账户
	if strings.Contains(allUsers, "Name=") {
		lines := strings.Split(allUsers, "\n")
		var dollarUsers []string
		for _, line := range lines {
			if strings.Contains(line, "Name=") {
				name := strings.TrimPrefix(line, "Name=")
				name = strings.TrimSpace(name)
				if strings.HasSuffix(name, "$") {
					dollarUsers = append(dollarUsers, name)
				}
			}
		}
		if len(dollarUsers) > 0 {
			writeCode(strings.Join(dollarUsers, "\n"))
		} else {
			writeCode("未找到带有'$'后缀的账户。")
		}
	} else {
		// PowerShell输出
		if strings.TrimSpace(allUsers) != "" {
			writeCode(allUsers)
		} else {
			writeCode("未找到带有'$'后缀的账户。")
		}
	}
}

// 3. 高级持久化
func checkAdvancedPersistence() {
	writeLog("高级持久化")

	// IFEO镜像劫持
	writeLog("IFEO镜像劫持")
	ifeoPath := `HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options`
	ifeoOutput := execCommand("reg", "query", ifeoPath, "/s")

	// 过滤Debugger条目
	lines := strings.Split(ifeoOutput, "\n")
	var hijacks []string
	currentKey := ""
	for _, line := range lines {
		line = strings.TrimSpace(line)
		if strings.HasPrefix(line, "HKEY_") {
			currentKey = filepath.Base(line)
		}
		if strings.Contains(line, "Debugger") {
			hijacks = append(hijacks, fmt.Sprintf("[%s] %s", currentKey, line))
		}
	}

	if len(hijacks) > 0 {
		writeCode(strings.Join(hijacks, "\n"))
	} else {
		writeCode("无。")
	}

	// Winlogon助手
	writeLog("Winlogon助手")
	winlogon := execCommand("reg", "query", `HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon`, "/v", "Shell")
	winlogon += "\n" + execCommand("reg", "query", `HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon`, "/v", "Userinit")
	writeCode(winlogon)

	// WMI持久化 - 使用PowerShell替代wmic
	writeLog("WMI持久化")
	wmiCmd := `
		$filters = Get-WmiObject -Namespace root\subscription -Class __EventFilter | Select-Object Name, Query
		$consumers = Get-WmiObject -Namespace root\subscription -Class CommandLineEventConsumer | Select-Object Name, CommandLineTemplate
		Write-Host "过滤器:"
		$filters | Format-List
		Write-Host "消费者:"
		$consumers | Format-List
	`
	wmiResult := execCommand("powershell", "-Command", wmiCmd)

	if strings.Contains(wmiResult, "过滤器:") && !strings.Contains(wmiResult, "Name") {
		writeCode("未发现WMI持久化。")
	} else {
		writeCode(wmiResult)
	}
}

// 4. 网络取证
func checkNetwork() {
	writeLog("网络取证")

	// 隐藏端口代理
	writeLog("隐藏端口代理")
	portProxy := execCommand("netsh", "interface", "portproxy", "show", "all")
	if strings.TrimSpace(portProxy) == "" {
		writeCode("无。")
	} else {
		writeCode(portProxy)
	}

	// TCP连接
	writeLog("TCP连接")
	connections := execCommand("netstat", "-ano")
	writeCode(connections)

	// DNS缓存（限制行数避免数据过大）
	writeLog("DNS缓存")
	dns := execCommand("ipconfig", "/displaydns")
	// 只保留前100行避免数据过大
	dnsLines := strings.Split(dns, "\n")
	if len(dnsLines) > 100 {
		dns = strings.Join(dnsLines[:100], "\n") + "\n... (已截断)"
	}
	writeCode(dns)
}

// 5. 用户活动
func checkUserActivity() {
	writeLog("用户活动")

	// 最近文件
	writeLog("最近文件")
	recentPath := filepath.Join(os.Getenv("APPDATA"), "Microsoft", "Windows", "Recent")
	files, err := os.ReadDir(recentPath)
	if err == nil && len(files) > 0 {
		var recentFiles []string
		for i, file := range files {
			if i >= 20 {
				break
			}
			info, _ := file.Info()
			if info != nil {
				recentFiles = append(recentFiles, fmt.Sprintf("%s - %s", file.Name(), info.ModTime().Format("2006-01-02 15:04:05")))
			}
		}
		writeCode(strings.Join(recentFiles, "\n"))
	} else {
		writeCode("未找到最近文件。")
	}

	// PowerShell历史记录
	writeLog("PowerShell历史记录")
	historyPath := filepath.Join(os.Getenv("APPDATA"), "Microsoft", "Windows", "PowerShell", "PSReadLine", "ConsoleHost_history.txt")
	history, err := os.ReadFile(historyPath)
	if err == nil {
		lines := strings.Split(string(history), "\n")
		start := 0
		if len(lines) > 20 {
			start = len(lines) - 20
		}
		writeCode(strings.Join(lines[start:], "\n"))
	} else {
		writeCode("未找到PowerShell历史记录。")
	}
}

// 6. WebShell检查
func checkWebShell() {
	writeLog("Web服务器 (IIS)")

	webPath := `C:\inetpub\wwwroot`
	if _, err := os.Stat(webPath); os.IsNotExist(err) {
		writeCode("未找到IIS网站根目录。")
		return
	}

	// 查找最近30天内修改的Web脚本
	thirtyDaysAgo := time.Now().AddDate(0, 0, -30)
	var webShells []string

	err := filepath.Walk(webPath, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return nil
		}
		if info.IsDir() {
			return nil
		}

		ext := strings.ToLower(filepath.Ext(path))
		if ext == ".aspx" || ext == ".asp" || ext == ".php" || ext == ".jsp" || ext == ".cer" {
			if info.ModTime().After(thirtyDaysAgo) {
				webShells = append(webShells, fmt.Sprintf("%s - %s - %d 字节", path, info.ModTime().Format("2006-01-02 15:04:05"), info.Size()))
			}
		}
		return nil
	})

	if err != nil {
		writeCode(fmt.Sprintf("扫描错误: %v", err))
	} else if len(webShells) > 0 {
		writeCode(strings.Join(webShells, "\n"))
	} else {
		writeCode("未找到最近的脚本。")
	}
}

// 7. 进程检查 - 完整实现见 main_gaint_part2.go 中的 checkProcesses()
