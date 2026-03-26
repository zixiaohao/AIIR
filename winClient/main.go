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
		fmt.Println("Windows 安全应急响应检测工具 v3.1")
		fmt.Println()
		fmt.Println("用法:")
		fmt.Println("  win_client.exe -s <Server地址>")
		fmt.Println("  win_client.exe --server <Server地址>")
		fmt.Println()
		fmt.Println("参数:")
		fmt.Println("  -s, --server    指定Server地址 (格式: http://IP:端口)")
		fmt.Println("  -h, --help      显示此帮助信息")
		fmt.Println()
		fmt.Println("示例:")
		fmt.Println("  win_client.exe -s http://192.168.1.100:8000")
		fmt.Println("  win_client.exe --server http://10.0.0.50:8000")
		fmt.Println()
		fmt.Println("注意:")
		fmt.Println("  - 程序需要管理员权限运行")
		fmt.Println("  - 如果不指定Server地址，程序将询问用户输入")
		fmt.Println("  - 离线模式下程序仍可执行安全检查但无法发送分析请求")
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

	// Server连接正常，启动AI分析
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

// 发送数据到Server - 分批分析模式
func sendDataToServer(ticketID, hostname string) {
	fmt.Println()
	fmt.Println("═══════════════════════════════════════════════════════════════")
	fmt.Println("              发送数据到Server - 分批分析模式                 ")
	fmt.Println("═══════════════════════════════════════════════════════════════")

	// 读取日志内容
	content, err := os.ReadFile(logFile)
	if err != nil {
		fmt.Printf("[错误] 读取日志文件失败: %v\n", err)
		return
	}

	// 获取IP信息
	ipInfo := getIPInfo()

	// 按模块分割日志
	lines := strings.Split(string(content), "\n")
	var sections []struct {
		title   string
		content string
	}
	var currentSection string
	var currentContent []string

	for _, line := range lines {
		if strings.HasPrefix(line, "## ") {
			if currentSection != "" && len(currentContent) > 0 {
				sections = append(sections, struct {
					title   string
					content string
				}{
					title:   currentSection,
					content: strings.Join(currentContent, "\n"),
				})
			}
			currentSection = strings.TrimPrefix(line, "## ")
			currentContent = []string{}
		} else {
			currentContent = append(currentContent, line)
		}
	}

	// 处理最后一个模块
	if currentSection != "" && len(currentContent) > 0 {
		sections = append(sections, struct {
			title   string
			content string
		}{
			title:   currentSection,
			content: strings.Join(currentContent, "\n"),
		})
	}

	fmt.Printf("[模块数量] 共发现 %d 个模块，开始逐个分析...\n\n", len(sections))

	// 存储各模块分析结果
	var sectionResults []string
	successCount := 0
	failCount := 0

	// 逐个发送模块进行分析
	for i, section := range sections {
		fmt.Printf("[%d/%d] 正在分析: %s", i+1, len(sections), section.title)

		// 构建单模块请求
		requestBody := map[string]interface{}{
			"section_title":   section.title,
			"section_content": section.content,
			"platform":        "windows",
		}

		jsonBody, err := json.Marshal(requestBody)
		if err != nil {
			fmt.Printf(" [❌ JSON编码失败]\n")
			failCount++
			continue
		}

		// 发送请求
		resp, err := http.Post(serverURL+"/analyze_section", "application/json", bytes.NewBuffer(jsonBody))
		if err != nil {
			fmt.Printf(" [❌ 发送失败]\n")
			failCount++
			continue
		}

		// 读取响应
		body, err := io.ReadAll(resp.Body)
		resp.Body.Close()
		if err != nil {
			fmt.Printf(" [❌ 读取响应失败]\n")
			failCount++
			continue
		}

		// 解析响应
		var response struct {
			Success        bool   `json:"success"`
			Error          string `json:"error"`
			AnalysisResult string `json:"analysis_result"`
		}

		err = json.Unmarshal(body, &response)
		if err != nil {
			fmt.Printf(" [❌ 解析响应失败]\n")
			failCount++
			continue
		}

		if response.Success {
			if response.AnalysisResult != "" && !strings.Contains(response.AnalysisResult, "无异常") {
				fmt.Println(" [⚠️ 发现异常]")
				sectionResults = append(sectionResults, response.AnalysisResult)
			} else {
				fmt.Println(" [✅ 无异常]")
			}
			successCount++
		} else {
			fmt.Printf(" [❌ 失败: %s]\n", response.Error)
			failCount++
		}
	}

	fmt.Println()
	fmt.Printf("[分析统计] 成功: %d, 失败: %d\n", successCount, failCount)

	// 发送汇总分析请求
	fmt.Println()
	fmt.Println("═══════════════════════════════════════════════════════════════")
	fmt.Println("              发送汇总请求进行最终研判                        ")
	fmt.Println("═══════════════════════════════════════════════════════════════")

	summaryRequest := map[string]interface{}{
		"ticket_id":       ticketID,
		"hostname":        hostname,
		"ip_info":         ipInfo,
		"platform":        "windows",
		"section_results": sectionResults,
	}

	summaryJsonBody, err := json.Marshal(summaryRequest)
	if err != nil {
		fmt.Printf("[错误] JSON编码失败: %v\n", err)
		return
	}

	// 发送汇总请求
	fmt.Printf("[发送请求] %s\n", serverURL)
	summaryResp, err := http.Post(serverURL+"/analyze_summary", "application/json", bytes.NewBuffer(summaryJsonBody))
	if err != nil {
		fmt.Printf("[错误] 发送失败: %v\n", err)
		return
	}
	defer summaryResp.Body.Close()

	// 读取响应
	summaryBody, err := io.ReadAll(summaryResp.Body)
	if err != nil {
		fmt.Printf("[错误] 读取响应失败: %v\n", err)
		return
	}

	// 解析响应
	var summaryResponse struct {
		Success        bool   `json:"success"`
		Error          string `json:"error"`
		AnalysisReport string `json:"analysis_report"`
	}

	err = json.Unmarshal(summaryBody, &summaryResponse)
	if err != nil {
		fmt.Printf("[错误] 解析响应失败: %v\n", err)
		return
	}

	if summaryResponse.Success {
		fmt.Println()
		fmt.Println("✅ 汇总分析完成!")
		fmt.Printf("[分析系统] 安全应急响应分析平台\n")

		// 保存分析报告到本地
		reportFile := fmt.Sprintf("%s_analysis_report.md", ticketID)
		err = os.WriteFile(reportFile, []byte(summaryResponse.AnalysisReport), 0644)
		if err != nil {
			fmt.Printf("[警告] 保存报告失败: %v\n", err)
		} else {
			fmt.Println()
			fmt.Println("═══════════════════════════════════════════════════════════════")
			fmt.Println("                AI 安全应急响应分析报告                        ")
			fmt.Println("═══════════════════════════════════════════════════════════════")
			fmt.Println(summaryResponse.AnalysisReport)
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
		fmt.Printf("[错误] Server返回错误: %s\n", summaryResponse.Error)
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

// 7. 进程检查
func checkProcesses() {
	writeLog("进程")

	// 获取进程列表 - 优先使用wmic，失败则使用PowerShell
	processes := execCommandWithFallback(
		"wmic", []string{"process", "get", "ProcessId,Name,ExecutablePath,CommandLine", "/format:list"},
		"powershell", []string{"-Command", "Get-Process | Select-Object Id, Name, Path, CommandLine | Format-Table -AutoSize -Wrap"},
	)
	writeCode(processes)

	// 获取进程详细信息（带签名检查）
	writeLog("进程详细信息（带签名检查）")
	// 使用PowerShell获取进程和签名信息
	sigCheck := execCommand("powershell", "-Command", "Get-Process | Where-Object {$_.Path -ne $null} | Select-Object Name, Id, Path, @{Name='Signer';Expression={(Get-AuthenticodeSignature $_.Path).SignerCertificate.Subject}} | Format-List | Out-String -Width 200")
	writeCode(sigCheck)

	// 可疑进程
	writeLog("可疑进程检查")
	lines := strings.Split(processes, "\n")
	var suspicious []string
	for _, line := range lines {
		if keywordsRegex.MatchString(strings.ToLower(line)) {
			suspicious = append(suspicious, line)
		}
	}

	if len(suspicious) > 0 {
		writeCode("[警告] 发现可疑进程:\n" + strings.Join(suspicious, "\n"))
	} else {
		writeCode("无")
	}
}

// 8. 启动项
func checkStartup() {
	writeLog("启动项")

	// 注册表启动位置
	startupLocations := []string{
		`HKLM\Software\Microsoft\Windows\CurrentVersion\Run`,
		`HKCU\Software\Microsoft\Windows\CurrentVersion\Run`,
		`HKLM\Software\Microsoft\Windows\CurrentVersion\RunOnce`,
		`HKCU\Software\Microsoft\Windows\CurrentVersion\RunOnce`,
	}

	var allStartup []string
	for _, loc := range startupLocations {
		output := execCommand("reg", "query", loc, "/s")
		if !strings.Contains(output, "ERROR") {
			allStartup = append(allStartup, fmt.Sprintf("[%s]", loc))
			allStartup = append(allStartup, output)
		}
	}

	if len(allStartup) > 0 {
		writeCode(strings.Join(allStartup, "\n"))
	} else {
		writeCode("未找到启动项。")
	}

	// 启动文件夹
	writeLog("启动文件夹")
	startupFolders := []string{
		filepath.Join(os.Getenv("APPDATA"), "Microsoft", "Windows", "Start Menu", "Programs", "Startup"),
		`C:\ProgramData\Microsoft\Windows\Start Menu\Programs\Startup`,
	}

	for _, folder := range startupFolders {
		files, err := os.ReadDir(folder)
		if err == nil && len(files) > 0 {
			writeCode(fmt.Sprintf("[%s]", folder))
			for _, file := range files {
				writeCode(file.Name())
			}
		}
	}
}

// 9. 安全日志
func checkSecurityLogs() {
	writeLog("安全日志")

	// 使用wevtutil获取最近的安全事件
	logs := execCommand("wevtutil", "qe", "Security", "/c:30", "/f:text", "/q:*[System[(EventID=4624 or EventID=4625)]]")
	writeCode(logs)

	// 服务创建事件（事件ID 7045）
	writeLog("服务创建事件")
	serviceLogs := execCommand("wevtutil", "qe", "System", "/c:20", "/f:text", "/q:*[System[(EventID=7045)]]")
	writeCode(serviceLogs)
}

// 10. OA/ERP安全检查（基本信息收集）
func checkOASecurity() {
	writeLog("OA/ERP 系统识别")

	systems := identifySystems()

	if len(systems) == 0 {
		msg := "未识别到常见的OA/ERP系统或Web服务器 (如通达, 致远, 泛微, 用友, IIS, Nginx, Tomcat, Apache)。"
		writeCode(msg)
		return
	}

	for _, sys := range systems {
		writeCode(fmt.Sprintf("发现系统: %s (路径: %s)", sys.Name, sys.Path))
	}
}

// OA/ERP深度扫描（AI分析后调用）
func checkOASecurityDeepScan() {
	fmt.Println()
	fmt.Println("═══════════════════════════════════════════════════════════════")
	fmt.Println("              OA/ERP系统高频漏洞日志深度分析                  ")
	fmt.Println("═══════════════════════════════════════════════════════════════")

	writeLog("OA/ERP 安全深度分析")
	fmt.Println("正在识别业务系统...")

	systems := identifySystems()

	// 询问是否进行深度扫描（多盘符多目录）
	fmt.Println()
	fmt.Print("是否进行深度扫描（搜索所有盘符的Nginx/Tomcat/Apache日志）? (y/n): ")
	reader := bufio.NewReader(os.Stdin)
	deepScan, _ := reader.ReadString('\n')
	deepScan = strings.TrimSpace(deepScan)
	if strings.ToLower(deepScan) == "y" {
		fmt.Println("正在进行深度扫描，请耐心等待...")
		webServers := findWebServerLogs()
		systems = append(systems, webServers...)
	}

	if len(systems) == 0 {
		msg := "未识别到常见的OA/ERP系统或Web服务器。"
		fmt.Println(msg)
		writeCode(msg)
		return
	}

	var allSuspiciousLogs []string

	for _, sys := range systems {
		fmt.Printf("发现系统: %s (路径: %s)\n", sys.Name, sys.Path)
		writeLog(fmt.Sprintf("系统: %s (路径: %s)", sys.Name, sys.Path))

		logFiles := findLogFiles(sys)
		fmt.Printf("找到 %d 个日志文件\n", len(logFiles))

		for _, logFile := range logFiles {
			fmt.Printf("正在分析日志: %s ...\n", logFile)
			suspicious := analyzeLogFile(logFile, sys.Name)
			if len(suspicious) > 0 {
				fmt.Printf("  -> 发现 %d 条可疑记录\n", len(suspicious))
				allSuspiciousLogs = append(allSuspiciousLogs, suspicious...)
			}
		}
	}

	if len(allSuspiciousLogs) > 0 {
		writeCode(fmt.Sprintf("共发现 %d 条可疑日志，准备进行AI分析...", len(allSuspiciousLogs)))
		fmt.Printf("共发现 %d 条可疑日志，正在进行AI分析...\n", len(allSuspiciousLogs))

		// 分批分析
		batchSize := 5
		for i := 0; i < len(allSuspiciousLogs); i += batchSize {
			end := i + batchSize
			if end > len(allSuspiciousLogs) {
				end = len(allSuspiciousLogs)
			}

			batch := allSuspiciousLogs[i:end]
			content := strings.Join(batch, "\n")

			prompt := "请分析以下Web日志，判断是否存在针对OA/ERP系统的攻击。\n" +
				"对于每一行日志，请输出：\n" +
				"1. 攻击类型 (如SQL注入, XSS, RCE, Log4j, 反序列化等)\n" +
				"2. 是否攻击成功 (根据状态码200/500等及响应大小判断)\n" +
				"3. 风险等级 (高/中/低)\n" +
				"4. 原始日志摘要\n" +
				"请用中文回答，格式清晰。"

			result := callDeepSeekAPI(prompt, content)

			output := fmt.Sprintf("--- OA/ERP深度分析结果 (批次 %d/%d) ---\n%s\n", (i/batchSize)+1, (len(allSuspiciousLogs)+batchSize-1)/batchSize, result)
			writeCode(output)
			fmt.Println(output)

			time.Sleep(1 * time.Second)
		}
	} else {
		fmt.Println("未发现符合常见攻击特征的日志。")
		writeCode("未发现符合常见攻击特征的日志。")
	}
}

// 调用AI API（用于OA深度分析）
func callDeepSeekAPI(systemPrompt, userContent string) string {
	requestBody := map[string]interface{}{
		"model": "deepseek-chat",
		"messages": []map[string]string{
			{"role": "system", "content": systemPrompt},
			{"role": "user", "content": userContent},
		},
		"stream":      false,
		"temperature": 0.1,
	}

	jsonBody, err := json.Marshal(requestBody)
	if err != nil {
		return "API错误: " + err.Error()
	}

	req, err := http.NewRequest("POST", serverURL+"/analyze_section", bytes.NewBuffer(jsonBody))
	if err != nil {
		return "API错误: " + err.Error()
	}

	req.Header.Set("Content-Type", "application/json")

	client := &http.Client{Timeout: 120 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return "API错误: " + err.Error()
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return "API错误: " + err.Error()
	}

	var response struct {
		Success        bool   `json:"success"`
		AnalysisResult string `json:"analysis_result"`
		Error          string `json:"error"`
	}

	err = json.Unmarshal(body, &response)
	if err != nil {
		return "API错误: " + err.Error()
	}

	if response.Success {
		return response.AnalysisResult
	}

	return "API错误: " + response.Error
}

type SystemInfo struct {
	Name string
	Path string
	Type string
}

func identifySystems() []SystemInfo {
	var systems []SystemInfo

	// 检查IIS
	if _, err := os.Stat(`C:\inetpub\wwwroot`); err == nil {
		systems = append(systems, SystemInfo{Name: "IIS Web Server", Path: `C:\inetpub`, Type: "IIS"})
	}

	// 检查常见OA目录
	commonApps := map[string]string{
		`C:\MYOA`:    "通达OA",
		`C:\Seeyon`:  "致远OA",
		`C:\WEAVER`:  "泛微OA",
		`C:\yonyou`:  "用友",
		`C:\Landray`: "蓝凌OA",
		`D:\MYOA`:    "通达OA",
		`D:\Seeyon`:  "致远OA",
		`D:\WEAVER`:  "泛微OA",
	}

	for path, name := range commonApps {
		if _, err := os.Stat(path); err == nil {
			systems = append(systems, SystemInfo{Name: name, Path: path, Type: "OA"})
		}
	}

	return systems
}

// findWebServerLogs 深度扫描所有盘符查找Web服务器日志
func findWebServerLogs() []SystemInfo {
	var systems []SystemInfo
	foundPaths := make(map[string]bool)

	drives := getAvailableDrives()
	fmt.Printf("检测到盘符: %v\n", drives)

	webServerPatterns := []struct {
		Name        string
		Type        string
		DirPatterns []string
	}{
		{Name: "Nginx", Type: "Nginx", DirPatterns: []string{"nginx", "nginx-"}},
		{Name: "Tomcat", Type: "Tomcat", DirPatterns: []string{"tomcat", "tomcat-", "apache-tomcat"}},
		{Name: "Apache", Type: "Apache", DirPatterns: []string{"apache", "apache-", "httpd", "xampp", "wamp"}},
	}

	for _, drive := range drives {
		fmt.Printf("正在扫描盘符 %s ...\n", drive)

		for _, server := range webServerPatterns {
			for _, dirPattern := range server.DirPatterns {
				paths := searchDirectories(drive, dirPattern, 3)
				for _, path := range paths {
					if !foundPaths[path] {
						logPath := filepath.Join(path, "logs")
						if _, err := os.Stat(logPath); err == nil {
							systems = append(systems, SystemInfo{
								Name: server.Name,
								Path: path,
								Type: server.Type,
							})
							foundPaths[path] = true
							fmt.Printf("  发现 %s: %s\n", server.Name, path)
						}
					}
				}
			}
		}
	}

	return systems
}

func getAvailableDrives() []string {
	var drives []string
	for _, drive := range "ABCDEFGHIJKLMNOPQRSTUVWXYZ" {
		path := string(drive) + ":\\"
		if _, err := os.Stat(path); err == nil {
			drives = append(drives, string(drive)+":")
		}
	}
	return drives
}

func searchDirectories(drive string, pattern string, maxDepth int) []string {
	var results []string
	patternLower := strings.ToLower(pattern)

	commonDirs := []string{
		"\\Program Files",
		"\\Program Files (x86)",
		"\\opt",
		"\\server",
		"\\web",
		"\\www",
	}

	for _, baseDir := range commonDirs {
		searchPath := drive + baseDir
		if _, err := os.Stat(searchPath); os.IsNotExist(err) {
			continue
		}

		filepath.Walk(searchPath, func(path string, info os.FileInfo, err error) error {
			if err != nil || !info.IsDir() {
				return nil
			}

			depth := strings.Count(path, string(os.PathSeparator)) - strings.Count(searchPath, string(os.PathSeparator))
			if depth > maxDepth {
				return filepath.SkipDir
			}

			dirName := strings.ToLower(info.Name())
			if strings.Contains(dirName, patternLower) {
				results = append(results, path)
			}

			return nil
		})
	}

	return results
}

func findLogFiles(sys SystemInfo) []string {
	var logs []string
	sevenDaysAgo := time.Now().AddDate(0, 0, -7)

	logDirs := []string{
		filepath.Join(sys.Path, "logs"),
		filepath.Join(sys.Path, "log"),
	}

	for _, logDir := range logDirs {
		if _, err := os.Stat(logDir); err == nil {
			filepath.Walk(logDir, func(path string, info os.FileInfo, err error) error {
				if err == nil && !info.IsDir() {
					name := strings.ToLower(info.Name())
					if strings.Contains(name, "access") || strings.Contains(name, "error") || strings.HasSuffix(name, ".log") {
						if info.ModTime().After(sevenDaysAgo) {
							logs = append(logs, path)
						}
					}
				}
				return nil
			})
		}
	}

	return logs
}

func analyzeLogFile(path string, sysName string) []string {
	file, err := os.Open(path)
	if err != nil {
		return nil
	}
	defer file.Close()

	var suspicious []string
	scanner := bufio.NewScanner(file)

	lineCount := 0
	for scanner.Scan() {
		lineCount++
		if lineCount > 50000 {
			break
		}

		line := scanner.Text()
		if len(line) > 2000 {
			continue
		}

		lineLower := strings.ToLower(line)

		// 检查攻击特征（从Server获取的特征库）
		for category, patterns := range attackPatterns {
			for _, pattern := range patterns {
				if strings.Contains(lineLower, strings.ToLower(pattern.Pattern)) {
					suspicious = append(suspicious, fmt.Sprintf("[%s][%s][%s] %s", sysName, category, pattern.Description, line))
					break
				}
			}
		}
	}

	if len(suspicious) > 30 {
		return suspicious[len(suspicious)-30:]
	}
	return suspicious
}

// 离线安全检查功能
func performOfflineSecurityCheck() {
	fmt.Println("正在执行离线安全检查...")
	fmt.Println()

	findingsCount := 0

	// 1. 检查可疑进程
	fmt.Println("[1/8] 检查可疑进程...")
	suspiciousProcs := execCommand("powershell", "-Command", 
		"Get-Process | Where-Object {$_.ProcessName -match '(cmd|powershell|wscript|cscript|mshta|rundll32|regsvr32)'} | Select-Object Id, Name, Path | Format-Table -AutoSize")
	if !strings.Contains(suspiciousProcs, "没有运行") && len(strings.TrimSpace(suspiciousProcs)) > 50 {
		fmt.Println("  ⚠️  发现可疑进程:")
		fmt.Println(suspiciousProcs)
		findingsCount++
		writeLog("## ⚠️ 离线检查 - 可疑进程")
		writeCode(suspiciousProcs)
	} else {
		fmt.Println("  ✅ 未发现可疑进程")
	}

	// 2. 检查异常网络连接
	fmt.Println("[2/8] 检查异常网络连接...")
	suspiciousNet := execCommand("netstat", "-ano")
	// 过滤常见恶意端口
	netLines := strings.Split(suspiciousNet, "\n")
	var suspiciousConns []string
	maliciousPorts := []string{":4444", ":5555", ":6666", ":7777", ":8888", ":9999", ":1234", ":31337", ":12345", ":54321"}
	for _, line := range netLines {
		for _, port := range maliciousPorts {
			if strings.Contains(line, port) && strings.Contains(line, "ESTABLISHED") {
				suspiciousConns = append(suspiciousConns, line)
				break
			}
		}
	}
	if len(suspiciousConns) > 0 {
		fmt.Println("  ⚠️  发现异常网络连接:")
		for _, conn := range suspiciousConns {
			fmt.Printf("    - %s\n", conn)
		}
		findingsCount++
		writeLog("## ⚠️ 离线检查 - 异常网络连接")
		writeCode(strings.Join(suspiciousConns, "\n"))
	} else {
		fmt.Println("  ✅ 未发现异常网络连接")
	}

	// 3. 检查计划任务
	fmt.Println("[3/8] 检查计划任务...")
	schTasks := execCommand("schtasks", "/query", "/fo", "csv", "/v")
	if strings.Contains(schTasks, "powershell") || strings.Contains(schTasks, "cmd") || strings.Contains(schTasks, "wscript") {
		fmt.Println("  ⚠️  发现可疑计划任务")
		findingsCount++
		writeLog("## ⚠️ 离线检查 - 可疑计划任务")
		writeCode(schTasks)
	} else {
		fmt.Println("  ✅ 未发现可疑计划任务")
	}

	// 4. 检查启动项
	fmt.Println("[4/8] 检查启动项...")
	startupItems := execCommand("wmic", "startup", "list", "full")
	if len(strings.TrimSpace(startupItems)) > 100 {
		fmt.Println("  ⚠️  发现启动项:")
		fmt.Println(startupItems)
		findingsCount++
		writeLog("## ⚠️ 离线检查 - 启动项")
		writeCode(startupItems)
	} else {
		fmt.Println("  ✅ 未发现异常启动项")
	}

	// 5. 检查异常服务
	fmt.Println("[5/8] 检查异常服务...")
	services := execCommand("sc", "query", "state=", "all")
	if strings.Contains(services, "powershell") || strings.Contains(services, "cmd") {
		fmt.Println("  ⚠️  发现可疑服务")
		findingsCount++
		writeLog("## ⚠️ 离线检查 - 可疑服务")
		writeCode(services)
	} else {
		fmt.Println("  ✅ 未发现可疑服务")
	}

	// 6. 检查注册表持久化
	fmt.Println("[6/8] 检查注册表持久化...")
	regKeys := []string{
		"HKLM\\Software\\Microsoft\\Windows\\CurrentVersion\\Run",
		"HKLM\\Software\\Microsoft\\Windows\\CurrentVersion\\RunOnce",
		"HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run",
		"HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\RunOnce",
	}
	regFindings := ""
	for _, regKey := range regKeys {
		output := execCommand("reg", "query", regKey)
		if !strings.Contains(output, "错误") && !strings.Contains(output, "ERROR") {
			regFindings += fmt.Sprintf("[%s]\n%s\n", regKey, output)
		}
	}
	if len(regFindings) > 50 {
		fmt.Println("  ⚠️  发现注册表启动项:")
		fmt.Println(regFindings)
		findingsCount++
		writeLog("## ⚠️ 离线检查 - 注册表持久化")
		writeCode(regFindings)
	} else {
		fmt.Println("  ✅ 未发现异常注册表项")
	}

	// 7. 检查异常文件
	fmt.Println("[7/8] 检查临时目录异常文件...")
	tempDirs := []string{os.Getenv("TEMP"), os.Getenv("TMP"), "C:\\Windows\\Temp"}
	var suspiciousFiles []string
	for _, tempDir := range tempDirs {
		if tempDir == "" {
			continue
		}
		output := execCommand("cmd", "/c", fmt.Sprintf("dir /b /s %s 2>nul | findstr /i \"\\.exe \\.dll \\.bat \\.cmd \\.ps1 \\.vbs \\.js\"", tempDir))
		if len(strings.TrimSpace(output)) > 10 {
			suspiciousFiles = append(suspiciousFiles, output)
		}
	}
	if len(suspiciousFiles) > 0 {
		fmt.Println("  ⚠️  发现临时目录中的可疑文件:")
		fmt.Println(strings.Join(suspiciousFiles, "\n"))
		findingsCount++
		writeLog("## ⚠️ 离线检查 - 临时目录文件")
		writeCode(strings.Join(suspiciousFiles, "\n"))
	} else {
		fmt.Println("  ✅ 临时目录未发现可疑文件")
	}

	// 8. 检查防火墙配置
	fmt.Println("[8/8] 检查防火墙配置...")
	firewall := execCommand("netsh", "advfirewall", "show", "allprofiles", "state")
	if strings.Contains(firewall, "OFF") {
		fmt.Println("  ⚠️  防火墙未完全启用")
		findingsCount++
		writeLog("## ⚠️ 离线检查 - 防火墙配置")
		writeCode(firewall)
	} else {
		fmt.Println("  ✅ 防火墙配置正常")
	}

	// 输出总结
	fmt.Println()
	fmt.Println("═══════════════════════════════════════════════════════════════")
	fmt.Println("                    离线安全检查完成                          ")
	fmt.Println("═══════════════════════════════════════════════════════════════")
	if findingsCount > 0 {
		fmt.Printf("[警告] 发现 %d 项安全问题，请人工复核\n", findingsCount)
		fmt.Println("[提示] 详细信息已记录在日志文件中")
	} else {
		fmt.Println("[正常] 未发现明显安全问题")
	}
	fmt.Println("═══════════════════════════════════════════════════════════════")
}
