import json
from langgraph.types import Command
from utils.states import SystemState
from utils.tools import tools_by_name
from langchain.messages import ToolMessage,HumanMessage, AIMessage, SystemMessage
from utils.templates import *
from utils.llms import model_with_tools, model_intent_recognition, model_analysis, model_chat, result_chat
from utils.sub_nodes import build_subgraph
from langgraph.config import get_stream_writer


def initial_node(state:SystemState):
    return {
        "fix_result":[],
        "further_check":[],
        "has_issue": False,
        "is_related": False
    }

def intent_recognition_node(state: SystemState):
    """意图识别，判断问题是否和运维相关"""
    messages = state["messages"]
    # print(messages)
    response = model_intent_recognition.invoke({"query": messages[-1]["content"]})
    intent = response.dict()
    writer = get_stream_writer()
    writer({"意图识别节点":intent})
    return {"is_related": intent["is_related"]}


def chat_node(state: SystemState):
    """正常对话节点"""
    response = model_chat.invoke({"messages": state["messages"]})
    return {"messages":[response]}

def system_status_get_node(state: SystemState):
    """获取系统运行参数节点"""
    messages = state["messages"]

    response = model_with_tools.invoke([SystemMessage(content=system_status_prompt.format()), HumanMessage(content=messages[-1]['content'])])

    tool_list = []
    for tool in response.tool_calls:
        tool_list.append(tool["name"])
    writer = get_stream_writer()
    writer({"调用以下工具获取系统参数：": '，'.join(tool_list)})
    return {"messages":[response], "further_check_count":0}


def check_system_status_node(state: SystemState):
    """检查系统运行状态节点"""
    # 1. 从State中提取所有系统指标数据（只提取有值的字段，避免空值报错）
    system_status = {}
    further_check_status = state["further_check"]
    # writer = get_stream_writer()
    # writer({"进一步检查结果：": json.dumps(further_check_status)})
    state_fields = ["cpu_usage", "mem_usage", "disk_usage", "disk_io", "network_io", "system_load", "top_processes"]
    for field in state_fields:
        if field in state and state[field] is not None:
            system_status[field] = state[field]


    response = model_analysis.invoke({
            "system_status_json":json.dumps(system_status),
            "further_check_status_json":json.dumps(further_check_status)
        }
    )

    # 4. 解析大模型输出，更新到State
    try:
        # 解析JSON结果
        analysis_result = response.dict()
        print("----------------分析结果----------------------")
        print(analysis_result)
        # 构建State增量更新
        state_update = {
            "messages": [response],
            "has_issue": analysis_result["has_issue"],
            "issue_type": analysis_result["issue_type"],
            "issue_detail": analysis_result["issue_detail"],
            "root_cause": analysis_result["root_cause"],
            "commands_type": analysis_result["commands_type"],
            "fix_commands": analysis_result["fix_commands"]
        }
        # print("系统状态节点：", state_update)
        return state_update
    except json.JSONDecodeError:
        # 异常兜底：如果JSON解析失败，返回原始消息，标记为未知问题
        return {
            "messages": [response],
            "has_issue": True,
            "issue_type": "unknown",
            "issue_detail": "系统状态解析失败，大模型输出格式异常",
            "root_cause": None,
            "commands_type":None,
            "fix_commands": []
        }


def check_problem_node(state: SystemState):
    """判断系统问题节点"""
    commands_list = state.get("fix_commands")
    messages = state["messages"]

    if commands_list:
        current_count = state.get("further_check_count", 0)
        response = model_with_tools.invoke([SystemMessage(content=command_executor_prompt.format()),HumanMessage(content=json.dumps(commands_list))])
        return {"further_check_count":current_count + 1, "messages":[response]}

    else:
        return {}


def fix_problem_node(state: SystemState):
    """修复节点,人工确认"""
    sub_app = build_subgraph()
    commands_list = state.get("fix_commands")
    writer = get_stream_writer()
    writer({"进入修复节点\n"})
    writer({"修复指令集为:": commands_list})

    config = {"configurable":{"thread_id": "1"}}
    messages = state["messages"]
    fix_result=[]

    if commands_list:
        for cmd in commands_list:
            init_state = {
                "command": cmd,
                "is_sensitive": False,
                "confirmed": None,
                "success": False,
                "output": ""
            }

            try:
                final_state = None

                # 执行子图，处理中断
                for chunk in sub_app.stream(init_state, config=config, stream_mode="values",subgraphs=True):
                    # print(f"[子图] {chunk}")

                    # 1. 兼容不同的 stream 返回格式，提取真正的 state dict
                    # 如果 chunk 是元组 (packed, state)，取第二个元素
                    if isinstance(chunk, tuple) and len(chunk) >= 2:
                        current_state = chunk[1]
                    else:
                        current_state = chunk

                    final_state = current_state

                    # 2. 检测中断 (检查字典 Key，而不是对象属性)
                    # 检查常见的中断键：'__interrupt__' 或者直接看有没有 'interrupts'
                    interrupt_data = current_state.get('__interrupt__')

                    # 如果找到了中断数据
                    if interrupt_data :

                        # 提取中断消息 (兼容不同的数据结构)
                        if isinstance(interrupt_data, (list, tuple)) and interrupt_data:
                            interrupt_obj = interrupt_data[0]
                            # 尝试获取 message，或者直接 str() 它
                            interrupt_msg = getattr(interrupt_obj, 'message', str(interrupt_obj))
                        else:
                            interrupt_msg = "确认执行该敏感操作？"

                        # 3. 现在才弹出输入框
                        user_input = input(f"\n{interrupt_msg} (yes/no): ").strip().lower()
                        user_confirmed = (user_input == "yes")

                        # print(f"\n[系统] 正在{'继续执行' if user_confirmed else '取消'}...")

                        # 4. 恢复执行
                        # 注意：这里通常不需要再传 Command，直接 update_state 或 resume
                        # 但如果你的图设计是接收 resume=True/False，按你的逻辑来
                        for continuation_chunk in sub_app.stream(
                                Command(resume=user_confirmed),  # 或者 Command(resume=user_confirmed)
                                config=config,
                                stream_mode="values"
                        ):
                            # print(f"[子图恢复] {continuation_chunk}")
                            if isinstance(continuation_chunk, tuple) and len(continuation_chunk) >= 2:
                                final_state = continuation_chunk[1]
                            else:
                                final_state = continuation_chunk

                        break  # 处理完中断，跳出主循环  # 中断处理完成，跳出外层循环

                # 收集结果
                if final_state:
                    fix_result.append({
                        "command": final_state.get("command", cmd),
                        "success": final_state.get("success", False),
                        "output": final_state.get("output", "")
                    })

            except Exception as e:
                fix_result.append({
                    "command": cmd,
                    "success": False,
                    "output": f"执行失败: {str(e)}"
                })

    return {"fix_result":fix_result}


def reset_state_node(state: SystemState):
    """重置状态节点"""
    return {
        "has_issue": False,
        "issue_type": None,
        "issue_detail": None,
        "root_cause": None,
        "commands_type": None,
        "fix_commands": [],
        "fix_result": [],
        "further_check":[],

    }

# def fix_check(state: SystemState):
#     """检查修复结果"""
#     pass



def check_fix_result_summary_node(state: SystemState):
    """总结处理结果节点"""
    state_update = {
        "has_issue": state["has_issue"],
        "issue_type": state["issue_type"],
        "issue_detail": state["issue_detail"],
        "root_cause": state["root_cause"],
        "commands_type": state["commands_type"],
        "fix_commands": state["fix_commands"],
        "further_check": state["further_check"],
        "further_check_count": state["further_check_count"],
        "fix_result":state["fix_result"] if state.get("fix_result") else []
    }
    response = result_chat.invoke({"system_status": json.dumps(state_update)})
    return {"messages": [response]}







TOOL_TO_STATE_FIELD = {
    "get_memory_usage":"mem_usage",
    "get_disk_usage":"disk_usage",
    "get_disk_io":"disk_io",
    "get_network_io":"network_io",
    "get_system_load":"system_load",
    "get_cpu_usage":"cpu_usage",
    "run_command":"further_check"
}



def tool_node(state: SystemState):
    """调用工具节点"""
    result = []
    state_updates= {}
    last_message = state["messages"][-1]
    writer = get_stream_writer()
    # 判断最后一条是否是AI回复消息
    if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
        return {"messages": result}
    for tool_call in last_message.tool_calls:
        # 判断工具是否存在
        # print(tool_call["name"])
        if tool_call["name"] not in tools_by_name:
            error_msg = f"Error: Tool '{tool_call['name']}' not found."
            writer(f"Error: Tool '{tool_call['name']}' not found.")
            result.append(ToolMessage(content=error_msg, tool_call_id=tool_call["id"]))
            continue
        tool = tools_by_name[tool_call["name"]]

        # 判断是否存在参数错误
        try:
            tool_res = tool.invoke(tool_call["args"])

            if tool_call["name"] in TOOL_TO_STATE_FIELD:
                state_field = TOOL_TO_STATE_FIELD[tool_call["name"]]
                state_updates[state_field] = tool_res

            # 确保 content 是字符串类型（兼容不同工具返回值）
            result.append(ToolMessage(content=str(tool_res), tool_call_id=tool_call["id"]))
        except Exception as e:
            print(e)
            error_msg=f"Error executing tool '{tool_call['name']}': {str(e)}"
            writer(f"Error executing tool '{tool_call['name']}': {str(e)}")
            result.append(ToolMessage(content=error_msg, tool_call_id=tool_call["id"]))

    return_dict = {"messages": result}
    return_dict.update(state_updates)
    return return_dict