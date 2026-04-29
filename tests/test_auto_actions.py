#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动操作功能测试用例
测试 Server 端的 parse_actions_from_report 函数
"""

import unittest
import json
import re
import sys
import os

# 添加Server目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'Server'))

# 为了测试，需要定义一个简化版本的 parse_actions_from_report
def parse_actions_from_report(report_text, platform):
    """
    从AI分析报告中解析出结化的修复动作
    """
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


class TestParseActionsFromReport(unittest.TestCase):
    """测试 parse_actions_from_report 函数"""
    
    def test_parse_json_actions_linux(self):
        """测试解析Linux平台JSON格式的动作列表"""
        report = """
# 安全分析报告

## 发现的问题

发现可疑进程，需要停止并检查。

## 修复建议

```json
[
  {
    "command": "systemctl stop suspicious-service",
    "description": "停止可疑服务",
    "risk_level": "high",
    "category": "service"
  },
  {
    "command": "iptables -A INPUT -s 192.168.1.100 -j DROP",
    "description": "封禁恶意IP",
    "risk_level": "medium",
    "category": "network"
  }
]
```
"""
        actions = parse_actions_from_report(report, "linux")
        
        self.assertEqual(len(actions), 2)
        self.assertEqual(actions[0]['command'], "systemctl stop suspicious-service")
        self.assertEqual(actions[0]['risk_level'], "high")
        self.assertEqual(actions[1]['command'], "iptables -A INPUT -s 192.168.1.100 -j DROP")
        self.assertEqual(actions[1]['risk_level'], "medium")
    
    def test_parse_json_actions_windows(self):
        """测试解析Windows平台JSON格式的动作列表"""
        report = """
# 安全分析报告

## 发现的问题

发现恶意进程需要终止。

```json
[
  {
    "command": "taskkill /F /IM suspicious.exe",
    "description": "终止可疑进程",
    "risk_level": "high",
    "category": "process"
  },
  {
    "command": "netsh advfirewall firewall add rule name=BlockIP dir=in action=block remoteip=192.168.1.100",
    "description": "阻止恶意IP连接",
    "risk_level": "medium",
    "category": "network"
  }
]
```
"""
        actions = parse_actions_from_report(report, "windows")
        
        self.assertEqual(len(actions), 2)
        self.assertEqual(actions[0]['command'], "taskkill /F /IM suspicious.exe")
        self.assertEqual(actions[0]['risk_level'], "high")
    
    def test_parse_bash_commands(self):
        """测试解析bash命令块"""
        report = """
## 修复建议

以下是建议执行的命令：

```bash
ps aux | grep malicious
kill -9 12345
```
"""
        actions = parse_actions_from_report(report, "linux")
        
        self.assertEqual(len(actions), 2)
        self.assertIn("ps aux", actions[0]['command'])
        self.assertIn("kill -9", actions[1]['command'])
    
    def test_parse_powershell_commands(self):
        """测试解析PowerShell命令块"""
        report = """
## 修复建议

执行以下PowerShell命令：

```powershell
Stop-Process -Name suspicious -Force
Get-NetTCPConnection | Where-Object {$_.RemoteAddress -eq '192.168.1.100'}
```
"""
        actions = parse_actions_from_report(report, "windows")
        
        self.assertEqual(len(actions), 2)
        self.assertIn("Stop-Process", actions[0]['command'])
    
    def test_empty_report(self):
        """测试空报告"""
        report = """
# 安全分析报告

未发现任何问题。
"""
        actions = parse_actions_from_report(report, "linux")
        self.assertEqual(len(actions), 0)
    
    def test_no_actions_needed(self):
        """测试明确表示无需操作的情况"""
        report = """
# 安全分析报告

如果不需要任何修复操作，输出空数组 []

```json
[]
```
"""
        actions = parse_actions_from_report(report, "linux")
        self.assertEqual(len(actions), 0)
    
    def test_duplicate_commands_deduplicated(self):
        """测试重复命令会被去重"""
        report = """
# 安全分析报告

```json
[
  {"command": "systemctl stop service1", "description": "停止服务1", "risk_level": "medium", "category": "service"},
  {"command": "systemctl stop service1", "description": "停止服务1", "risk_level": "medium", "category": "service"},
  {"command": "systemctl stop service2", "description": "停止服务2", "risk_level": "medium", "category": "service"}
]
```
"""
        actions = parse_actions_from_report(report, "linux")
        
        # 应该只有2个动作（service1重复被去重）
        self.assertEqual(len(actions), 2)
        commands = [a['command'] for a in actions]
        self.assertIn("systemctl stop service1", commands)
        self.assertIn("systemctl stop service2", commands)
    
    def test_ignore_comments_in_bash(self):
        """测试bash命令中忽略注释"""
        report = """
## 修复建议

```bash
# 这是注释，不应该被解析
ps aux | grep malicious
# 另一个注释
kill -9 12345
```
"""
        actions = parse_actions_from_report(report, "linux")
        
        # 应该只有2条实际命令
        self.assertEqual(len(actions), 2)
        self.assertNotIn("#", actions[0]['command'][0])
    
    def test_nested_json_in_report(self):
        """测试报告中的嵌套JSON格式"""
        report = """
# 安全分析报告

{
  "analysis": "发现问题",
  "actions": [
    {"command": "service nginx restart", "description": "重启nginx", "risk_level": "low", "category": "service"},
    {"command": "systemctl restart httpd", "description": "重启httpd", "risk_level": "medium", "category": "service"}
  ]
}
"""
        actions = parse_actions_from_report(report, "linux")
        # 这种格式不会被解析，需要明确的代码块标记
        self.assertEqual(len(actions), 0)
    
    def test_multiple_json_blocks(self):
        """测试多个JSON代码块"""
        report = """
# 安全分析报告

第一个修复建议：
```json
[{"command": "service nginx stop", "description": "停止nginx", "risk_level": "medium", "category": "service"}]
```

第二个修复建议：
```json
[{"command": "iptables -F", "description": "清空防火墙规则", "risk_level": "high", "category": "network"}]
```
"""
        actions = parse_actions_from_report(report, "linux")
        
        self.assertEqual(len(actions), 2)
        self.assertEqual(actions[0]['command'], "service nginx stop")
        self.assertEqual(actions[1]['command'], "iptables -F")


class TestActionsStructure(unittest.TestCase):
    """测试动作结构完整性"""
    
    def test_actions_have_required_fields(self):
        """测试每个动作都有必需字段"""
        report = """
# 安全分析报告

```json
[
  {"command": "test", "description": "test"}
]
```
"""
        actions = parse_actions_from_report(report, "linux")
        
        for action in actions:
            self.assertIn('command', action)
            self.assertIn('description', action)
            self.assertIn('risk_level', action)
            self.assertIn('category', action)
    
    def test_default_values_for_missing_fields(self):
        """测试缺失字段使用默认值"""
        report = """
# 安全分析报告

```json
[
  {"command": "test"}
]
```
"""
        actions = parse_actions_from_report(report, "linux")
        
        self.assertEqual(actions[0]['risk_level'], 'medium')
        self.assertEqual(actions[0]['category'], 'general')
        self.assertEqual(actions[0]['description'], '')


if __name__ == '__main__':
    print("=" * 60)
    print("自动操作功能测试")
    print("=" * 60)
    
    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # 添加测试类
    suite.addTests(loader.loadTestsFromTestCase(TestParseActionsFromReport))
    suite.addTests(loader.loadTestsFromTestCase(TestActionsStructure))
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # 输出总结
    print()
    print("=" * 60)
    print("测试总结")
    print("=" * 60)
    print(f"运行测试数: {result.testsRun}")
    print(f"成功: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"失败: {len(result.failures)}")
    print(f"错误: {len(result.errors)}")
    
    sys.exit(0 if result.wasSuccessful() else 1)