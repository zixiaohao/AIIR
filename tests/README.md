# 自动操作功能测试套件

## 测试文件

- `test_auto_actions.py` - Python测试用例，测试Server端 `parse_actions_from_report` 函数

## 运行测试

### Python测试（Server端解析逻辑）

```bash
# 在项目根目录运行
python tests/test_auto_actions.py

# 或使用unittest
python -m unittest tests.test_auto_actions -v
```

### 测试覆盖范围

| 测试用例 | 说明 |
|---------|------|
| `test_parse_json_actions_linux` | 测试解析Linux平台JSON格式的动作列表 |
| `test_parse_json_actions_windows` | 测试解析Windows平台JSON格式的动作列表 |
| `test_parse_bash_commands` | 测试解析bash命令块 |
| `test_parse_powershell_commands` | 测试解析PowerShell命令块 |
| `test_empty_report` | 测试空报告（无动作） |
| `test_no_actions_needed` | 测试明确返回空数组的情况 |
| `test_duplicate_commands_deduplicated` | 测试重复命令会被去重 |
| `test_ignore_comments_in_bash` | 测试忽略bash注释 |
| `test_nested_json_in_report` | 测试嵌套JSON格式（应忽略） |
| `test_multiple_json_blocks` | 测试多个JSON代码块 |
| `test_actions_have_required_fields` | 测试动作结构完整性 |
| `test_default_values_for_missing_fields` | 测试缺失字段使用默认值 |

## 预期结果

```
Ran 12 tests in 0.001s
OK

============================================================
测试总结
============================================================
运行测试数: 12
成功: 12
失败: 0
错误: 0
```

## 手动测试

### Linux执行器手动测试

```bash
# 创建测试用的JSON响应文件
cat > /tmp/test_response.json << 'EOF'
{
  "success": true,
  "analysis_report": "# 安全分析报告\\n\\n发现可疑进程",
  "actions": [
    {"command": "ps aux", "description": "查看进程", "risk_level": "low", "category": "process"},
    {"command": "whoami", "description": "查看当前用户", "risk_level": "low", "category": "user"}
  ]
}
EOF

# 运行执行器（使用测试文件）
cd linuxclient_gaint
chmod +x action_executor.sh
./action_executor.sh /tmp/test_response.json

# 或使用管道输入
cat /tmp/test_response.json | ./action_executor.sh -
```

### Windows执行器手动测试

```powershell
# 编译执行器
cd windowsclient_gaint
go build -o action_executor_gaint.exe action_executor_gaint.go

# 创建测试用的JSON响应文件
@'
{
  "success": true,
  "analysis_report": "# 安全分析报告",
  "actions": [
    {"command": "whoami", "description": "查看当前用户", "risk_level": "low", "category": "user"}
  ]
}
'@ | Out-File -FilePath test_response.json -Encoding UTF8

# 运行执行器
.\action_executor_gaint.exe -f test_response.json
```

## 测试Mock数据

项目包含测试用的Mock响应数据，位于 `tests/mock_data/` 目录：

- `linux_actions.json` - Linux平台测试数据
- `windows_actions.json` - Windows平台测试数据

这些文件模拟Server返回的完整响应，可用于手动测试执行器功能。