from utils.states import SystemState
from typing_extensions import Literal


def intent_check_condition(state: SystemState):
    """意图识别"""
    intent = state["is_related"]
    if intent:
        return "system_status_get"
    else:
        return "chat_node"


def status_check_condition(state: SystemState):
    """检查系统状态是否异常"""
    has_issue = state["has_issue"]
    if has_issue:
        return "check_problem"
    else:
        return "summary_node"


def further_check_condition(state: SystemState):
    """判断是否需要进一步检查"""
    command_type = state["commands_type"]
    further_count = state["further_check_count"]
    if further_count >=6:
        return "summary_node"
    if command_type == "check":
        return "tool_node"
    elif command_type == "fix":
        return "fix_problem"
    else:
        return "summary_node"


# def fix_check_condition(state: SystemState):
#     """检查是否修复成功"""
#     pass



def call_tools(state: SystemState) -> Literal["tool_node", "END"]:
    """是否需要进行工具调用"""
    messages = state["messages"]
    last_messages = messages[-1]
    if last_messages.tool_calls:
        return "tool_node"
    return "END"
