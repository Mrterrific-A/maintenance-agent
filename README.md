# Linux系统运维智能助手 - 功能说明文档

---

## 一、项目概述

### 1.1 项目定位

本项目是基于 **LangGraph** 框架构建的 **Linux 系统运维智能助手**，利用大语言模型（LLM）实现自动化的系统监控、故障诊断和问题修复。

### 1.2 核心功能

| 功能模块 | 描述 |
|---------|------|
| **意图识别** | 判断用户问题是否与 Linux 系统运维相关 |
| **系统监控** | 自动获取 CPU、内存、磁盘、网络等系统指标 |
| **健康分析** | 使用大语言模型分析系统健康状态 |
| **问题诊断** | 识别系统问题类型并定位根因 |
| **自动修复** | 生成并执行修复命令（含敏感操作人工确认） |

### 1.3 架构设计

```
┌─────────────────────────────────────────────────────────────────┐
│                     Linux 系统运维智能助手                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │ 意图识别节点  │───→│ 系统状态获取  │───→│   工具调用   │      │
│  │ intent_      │    │ system_      │    │ tool_node    │      │
│  │ recognition  │    │ status_get   │    │              │      │
│  └──────────────┘    └──────────────┘    └───────┬──────┘      │
│         │                                        │              │
│         ▼                                        ▼              │
│       END                                    ┌──────────────┐   │
│                                              │ 状态检查节点 │   │
│                                              │ check_system │   │
│                                              │ _status      │   │
│                                              └───────┬──────┘   │
│                                                      │          │
│                                               ┌──────┴──────┐   │
│                                               │             │   │
│                                               ▼             ▼   │
│                                    ┌──────────────┐  ┌────────┐ │
│                                    │ 问题诊断节点  │  │  END   │ │
│                                    │ check_problem │  └────────┘ │
│                                    └───────┬──────┘             │
│                                            │                   │
│                                   ┌────────┴────────┐           │
│                                   │                 │           │
│                                   ▼                 ▼           │
│                          ┌──────────────┐  ┌──────────────┐     │
│                          │ 继续检查节点  │  │  修复节点    │     │
│                          │ check_problem │  │ fix_problem  │     │
│                          └───────┬──────┘  └───────┬──────┘     │
│                                  │                 │           │
│                                  └────────┬────────┘           │
│                                           │                    │
│                                           ▼                    │
│                                        ┌────────┐              │
│                                        │  END   │              │
│                                        └────────┘              │
└─────────────────────────────────────────────────────────────────┘
```

---

## 二、工作流程详解

### 2.1 意图识别阶段

**节点**：`intent_recognition_node`

**功能**：判断用户输入是否与 Linux 系统运维相关

**输入**：用户消息列表

**输出**：`is_related: bool`

**判断逻辑**：
- 相关：CPU、内存、磁盘、网络、进程、系统服务、日志等
- 不相关：Windows/macOS问题、文件编辑、日常闲聊等

### 2.2 系统状态获取阶段

**节点**：`system_status_get_node`

**功能**：根据用户问题，调用相应的监控工具获取系统指标

**工具列表**：

| 工具函数 | 功能 | 状态字段 |
|---------|------|---------|
| `get_cpu_usage` | 获取CPU使用率 | `cpu_usage` |
| `get_memory_usage` | 获取内存使用情况 | `mem_usage` |
| `get_disk_usage` | 获取磁盘空间 | `disk_usage` |
| `get_disk_io` | 获取磁盘IO统计 | `disk_io` |
| `get_network_io` | 获取网络IO统计 | `network_io` |
| `get_system_load` | 获取系统负载 | `system_load` |

### 2.3 系统健康分析阶段

**节点**：`check_system_status_node`

**功能**：调用大模型分析系统健康状态

**分析内容**：
- 健康级别：健康 / 警告 / 异常 / 严重
- 问题类型：CPU / 内存 / 磁盘 / 网络 / IO / unknown
- 问题详情：异常指标、触发阈值、影响范围
- 根因分析：定位具体进程、行为或配置问题
- 修复建议：生成可执行的 Linux 命令

### 2.4 问题诊断阶段

**节点**：`check_problem_node`

**功能**：执行诊断命令并将结果交给大模型继续分析

**流程**：
1. 获取待执行命令列表
2. 执行 shell 命令
3. 收集执行结果
4. 调用大模型分析结果
5. 生成下一步操作建议

### 2.5 问题修复阶段

**节点**：`fix_problem_node`

**功能**：执行修复命令（含敏感操作人工确认）

**安全机制**：
- **敏感操作检测**：识别危险命令（rm、del、format、dd等）
- **人工确认**：敏感操作需要用户确认后才能执行
- **命令白名单**：支持配置安全命令列表

---

## 三、状态管理

### 3.1 系统状态结构

```python
class SystemState(TypedDict):
    # 消息
    messages: List[AnyMessage]
    
    # 意图识别
    is_related: bool
    
    # 检查次数
    further_check_count: int
    
    # 系统指标
    cpu_usage: CpuState
    mem_usage: MemoryState
    disk_usage: DiskUsageState
    disk_io: DiskIOState
    network_io: NetworkIOState
    system_load: SystemLoadState
    top_processes: List[dict]
    
    # 问题分析
    has_issue: bool
    issue_type: Optional[str]
    issue_detail: Optional[str]
    root_cause: Optional[str]
    commands_type: Optional[str]
    fix_commands: Optional[List[str]]
    
    # 执行结果
    fix_result: Optional[List[CommandFix]]
```

### 3.2 命令状态结构（子图）

```python
class CommandState(TypedDict):
    command: str          # 命令内容
    is_sensitive: bool    # 是否敏感操作
    confirmed: bool       # 是否已确认
    success: bool         # 是否执行成功
    output: str           # 执行结果输出
```

---

## 四、条件边控制

### 4.1 意图识别条件

```python
def intent_check_condition(state):
    if state["is_related"]:
        return "system_status_get"  # 相关，继续处理
    else:
        return "END"                # 不相关，结束
```

### 4.2 工具调用条件

```python
def call_tools(state):
    last_message = state["messages"][-1]
    if last_message.tool_calls:
        return "tool_node"  # 有工具调用
    else:
        return "END"        # 无工具调用
```

### 4.3 状态检查条件

```python
def status_check_condition(state):
    if state["has_issue"]:
        return "check_problem"  # 有问题，继续诊断
    else:
        return "END"            # 无问题，结束
```

### 4.4 进一步检查条件

```python
def further_check_condition(state):
    if state["further_check_count"] >= 3:
        return "END"                        # 超过检查次数上限
    if state["commands_type"] == "check":
        return "check_problem"              # 需要进一步检查
    elif state["commands_type"] == "fix":
        return "fix_problem"                # 执行修复
    else:
        return "END"                        # 未知类型，结束
```

---

## 五、敏感操作安全机制

### 5.1 敏感命令检测

```python
# 危险命令列表
dangerous_commands = ["rm", "del", "format", "dd", "mkfs", "fdisk"]

# 危险参数
dangerous_flags = ["-rf", "--no-preserve-root"]

# 危险路径
dangerous_paths = ["/", "/etc", "/usr", "/bin", "/sbin", "/home"]
```

### 5.2 确认流程

```
用户请求修复
       │
       ▼
检测敏感操作
       │
       ├─ 否 → 自动执行
       │
       └─ 是 → 触发中断
                 │
                 ▼
           用户确认界面
                 │
           ┌────┴────┐
           │         │
           ▼         ▼
        确认执行    拒绝执行
           │         │
           ▼         ▼
      执行命令    返回失败
```

---

## 六、配置说明

### 6.1 环境变量配置

```env
# .env 文件
API_KEY=your-api-key-here       # OpenAI API Key
BASE_URL=https://api.openai.com/v1  # API 基础地址
MODEL=gpt-4o-mini               # 使用的模型
```

### 6.2 告警阈值配置

| 指标 | 警告阈值 | 异常阈值 |
|------|---------|---------|
| CPU使用率 | 70% | 85% |
| 内存使用率 | 75% | 90% |
| 磁盘使用率 | 80% | 90% |
| 交换分区 | 50% | 60% |
| CPU iowait | 20% | 30% |

---

## 七、使用示例

### 7.1 启动方式

```python
from maintenance.agent import agent

# 初始化状态
init_state = {
    "messages": [HumanMessage(content="检查系统状态")],
    "is_related": False,
    "further_check_count": 0
}

# 执行工作流
result = agent.invoke(init_state)

# 查看结果
print(result["has_issue"])
print(result["issue_detail"])
print(result["fix_commands"])
```

### 7.2 典型场景

#### 场景1：检查CPU使用率

```
用户输入："检查一下CPU使用率"
        │
        ▼
意图识别 → is_related=True
        │
        ▼
系统状态获取 → 调用 get_cpu_usage
        │
        ▼
工具调用 → 获取 CPU 数据
        │
        ▼
健康分析 → has_issue=False（正常）
        │
        ▼
END
```

#### 场景2：修复磁盘空间不足

```
用户输入："磁盘空间不足，帮忙清理"
        │
        ▼
意图识别 → is_related=True
        │
        ▼
系统状态获取 → 调用 get_disk_usage
        │
        ▼
工具调用 → 获取磁盘数据
        │
        ▼
健康分析 → has_issue=True, issue_type="disk"
        │
        ▼
问题诊断 → 生成清理命令
        │
        ▼
问题修复 → 执行清理命令（需确认）
        │
        ▼
END
```

---

## 八、代码结构

```
maintenance/
├── agent.py              # 主入口，图定义
├── .env                  # 环境配置
└── utils/
    ├── __init__.py
    ├── nodes.py          # 节点函数
    ├── edges.py          # 条件边函数
    ├── states.py         # 状态类型定义
    ├── tools.py          # 系统监控工具
    ├── llms.py           # LLM配置
    ├── templates.py      # 提示词模板
    ├── sub_nodes.py      # 子图节点（命令执行）
    └── utils.py          # 工具函数
```

---

## 九、扩展说明

### 9.1 添加新工具

```python
# 在 tools.py 中添加
@tool
def get_custom_metric(state: SystemState):
    """自定义指标获取"""
    # 实现逻辑
    return {"custom_metric": value}

# 在 nodes.py 中添加映射
TOOL_TO_STATE_FIELD = {
    # ... 现有映射 ...
    "get_custom_metric": "custom_metric"
}
```

### 9.2 自定义提示词

```python
# 在 templates.py 中添加
custom_prompt = PromptTemplate.from_template("""
你的自定义提示词模板
{variable}
""")
```

---

## 十、注意事项

1. **API Key 配置**：需要有效的 OpenAI API Key
2. **网络环境**：确保可以访问 OpenAI API
3. **敏感操作**：危险命令需要人工确认
4. **权限限制**：部分系统命令需要 root 权限
5. **执行超时**：命令执行有超时限制（默认60秒）

---

**文档版本**：v1.0  
**生成时间**：2026年5月9日  
**适用范围**：Linux 系统运维智能助手
