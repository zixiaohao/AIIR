package main

// 7. 进程检查（续）
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