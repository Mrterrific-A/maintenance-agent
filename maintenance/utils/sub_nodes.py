import subprocess
from typing import TypedDict, List, Optional, Annotated
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt, Command
from utils.states import CommandState
import re

# ========== 子图节点 ==========
def detect_sensitive(state: CommandState) -> CommandState:
    """标记敏感操作"""
    command = state["command"]
    # 危险命令列表
    dangerous_cmds = {"rm", "del", "format", "dd", "mkfs", "fdisk", "shred", "kill"}

    # 危险参数
    dangerous_flags = {"-rf", "--no-preserve-root", "-i", "--interactive=no"}

    # 危险路径模式
    dangerous_patterns = [
        r"/$",  # 根目录
        r"/etc(/|$)",  # etc 目录
        r"/usr(/|$)",  # usr 目录
        r"/bin(/|$)",  # bin 目录
        r"/sbin(/|$)",  # sbin 目录
        r"/home(/|$)",  # home 目录
        r"/root(/|$)",  # root 目录
        r"\*",  # 通配符
    ]

    cmd_lower = command.lower()
    has_dangerous_cmd = any(cmd in cmd_lower for cmd in dangerous_cmds)
    has_dangerous_flag = any(flag in cmd_lower for flag in dangerous_flags)
    has_dangerous_path = any(re.search(pattern, command) for pattern in dangerous_patterns)

    return {"is_sensitive": has_dangerous_cmd or has_dangerous_flag or has_dangerous_path}

def ask_confirmation(state: CommandState) -> CommandState:
    """
    敏感操作触发 Interrupt，等待外部恢复时提供确认值。
    恢复时通过 Command(resume=...) 传入 bool。
    """
    if not state["is_sensitive"]:
        # 非敏感操作，自动确认
        state["confirmed"] = True
        return state

    # 触发中断，并附带提示信息
    confirmed = interrupt(
        f"⚠️ 敏感操作: {state['command']}\n是否允许执行？(yes/no)"
    )
    # interrupt 返回的值就是外部 resume 传入的值
    state["confirmed"] = confirmed if isinstance(confirmed, bool) else (confirmed.lower() == "yes")
    return state

def execute_command(state: CommandState) -> CommandState:
    """执行指令（仅当 confirmed=True 时）"""
    if not state["confirmed"]:
        state["success"] = False
        state["output"] = "用户拒绝执行"
        return state

    try:
        result = subprocess.run(
            state["command"], shell=True, capture_output=True, text=True, timeout=10
        )
        state["success"] = (result.returncode == 0)
        state["output"] = result.stdout + result.stderr
    except Exception as e:
        state["success"] = False
        state["output"] = str(e)
    return state

def log_result(state: CommandState) -> CommandState:
    """记录结果（仅用于打印）"""
    # print(f"[子图] 指令: {state['command']}")
    # print(f"  敏感: {state['is_sensitive']} | 确认: {state['confirmed']} | 成功: {state['success']}")
    return state

# 编译子图（需要 checkpointer 支持 interrupt）
def build_subgraph():
    builder = StateGraph(CommandState)
    builder.add_node("detect", detect_sensitive)
    builder.add_node("ask", ask_confirmation)
    builder.add_node("execute", execute_command)
    builder.add_node("log", log_result)

    builder.set_entry_point("detect")
    builder.add_edge("detect", "ask")
    builder.add_edge("ask", "execute")
    builder.add_edge("execute", "log")
    builder.add_edge("log", END)

    # Interrupt 必须配合 checkpointer
    return builder.compile(checkpointer=MemorySaver())

# ========== 主图（使用子图） ==========
# class MainState(TypedDict):
#     commands: List[str]
#     results: List[dict]
#
# def dispatch_commands(state: MainState):
#     sub_app = build_subgraph()
#     config = {"configurable": {"thread_id": "cmd-executor"}}
#     results = []
#     for cmd in state["commands"]:
#         init = {
#             "command": cmd,
#             "is_sensitive": False,
#             "confirmed": None,
#             "success": False,
#             "output": ""
#         }
#         # 调用子图（可能被 interrupt）
#         final = sub_app.invoke(init, config=config)
#         results.append({
#             "command": final["command"],
#             "confirmed": final["confirmed"],
#             "success": final["success"]
#         })
#     state["results"] = results
#     return state

# 主图编译
# main_builder = StateGraph(MainState)
# main_builder.add_node("dispatch", dispatch_commands)
# main_builder.set_entry_point("dispatch")
# main_builder.add_edge("dispatch", END)
# main_app = main_builder.compile()

# ========== 恢复机制示例（人工确认交互） ==========
# def run_with_confirmation():
#     # 初始化状态（模拟主图获取指令列表）
#     init_state = {
#         "commands": [
#             "echo 'hello'",               # 安全指令
#             "rm -rf /tmp/test.txt",       # 敏感指令
#             "ls -la"
#         ],
#         "results": []
#     }
#
#     # 先执行一次，遇到 interrupt 会抛出异常或挂起
#     # 使用 stream 模式捕捉中断
#     config = {"configurable": {"thread_id": "main-demo"}}
#     try:
#         # 方式1：使用 invoke（遇到第一个 interrupt 会中断，无法自动恢复）
#         # 实际应使用 stream 并处理 interrupt 事件
#         for chunk in main_app.stream(init_state, config=config, stream_mode="values"):
#             print("主图输出:", chunk)
#     except Exception as e:
#         # 若直接 invoke 遇到 interrupt 会抛出 GraphInterrupt
#         print(f"触发中断: {e}")
#
#     # 实际上，常见做法是使用 while 循环，根据 checkpoint 的 next 节点来恢复
#     # 这里展示手动恢复敏感指令的确认
#     # 获取当前状态（假设已经中断在 ask 节点）
#     # 需要从 checkpoint 获取，简化示例不展开全部循环，
#     # 只展示如何通过 Command(resume=...) 恢复单个中断
#     pass

# # 更完整的恢复示例（单条指令子图直接运行）
# def demo_single_command():
#     sub = build_subgraph()
#     config = {"configurable": {"thread_id": "demo1"}}
#     init = {
#         "command": "rm -rf /tmp/test",
#         "is_sensitive": False,
#         "confirmed": None,
#         "success": False,
#         "output": ""
#     }
#     # 首次调用会触发 interrupt，返回特殊值
#     try:
#         result = sub.invoke(init, config=config)
#         print(result)
#     except Exception as e:
#         print("中断发生:", e)
#         # 恢复时传入确认值
#         result = sub.invoke(Command(resume=True), config=config)
#         print("恢复后结果:", result)

