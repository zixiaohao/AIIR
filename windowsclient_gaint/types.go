package main

// Action 修复动作定义（主程序和执行器共享）
type Action struct {
	Command     string `json:"command"`
	Description string `json:"description"`
	RiskLevel   string `json:"risk_level"`
	Category    string `json:"category"`
}
