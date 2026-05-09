from utils.nodes import *
from utils.edges import *
from utils.states import SystemState
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import InMemorySaver

graph = StateGraph(SystemState)
graph.add_node("initial_node", initial_node)
graph.add_node("intent_recognition", intent_recognition_node)
graph.add_node("system_status_get", system_status_get_node)
graph.add_node("check_system_status", check_system_status_node)
graph.add_node("check_problem", check_problem_node)
graph.add_node("fix_problem", fix_problem_node)
graph.add_node("tool_node", tool_node)
graph.add_node("chat_node", chat_node)
graph.add_node("summary_node", check_fix_result_summary_node)
graph.add_node("reset_node", reset_state_node)

graph.set_entry_point("initial_node")
graph.add_edge("initial_node", "intent_recognition")
graph.add_conditional_edges(
    "intent_recognition",
    intent_check_condition,
    {
        "system_status_get":"system_status_get",
        "chat_node":"chat_node"
    }
)
graph.add_conditional_edges(
    "system_status_get",
    call_tools,
    {
        "tool_node":"tool_node",
        "summary_node":"summary_node"
    }
)
graph.add_edge("tool_node","check_system_status")
graph.add_conditional_edges(
    "check_system_status",
    status_check_condition,
    {
        "check_problem":"check_problem",
        "summary_node":"summary_node"
    }
)
graph.add_conditional_edges(
    "check_problem",
    further_check_condition,
    {
        "summary_node":"summary_node",
        "tool_node":"tool_node",
        "fix_problem":"fix_problem"
    }
)
graph.add_edge("fix_problem", "summary_node")
graph.add_edge("chat_node",END)
graph.add_edge("summary_node","reset_node")
graph.add_edge("reset_node", END)

checkpointer = InMemorySaver()
agent = graph.compile(checkpointer=checkpointer)
png_data = agent.get_graph(xray=True).draw_mermaid_png()
with open('demo.png', "wb") as f:
    f.write(png_data)

config = {
    "configurable": {
        "thread_id": "1"
    }
}

while True:
    user_input = input("\n user: ")
    if user_input == "exit":
        break

    for chunk in agent.stream(
        {"messages": [{"role": "user", "content": f"{user_input}"}]},
        config,
        stream_mode=["messages", "custom","messages"],
        # version="v2",
        version="v2",
    ):
        if chunk["type"] == "values":
            # ValuesStreamPart — full state snapshot after each step
            print(f"{chunk['data']}")
        elif chunk["type"] == "updates":
            # UpdatesStreamPart — only the changed keys from each node
            for node_name, state in chunk["data"].items():
                print(f"Node `{node_name}` updated: {state}")
        elif chunk["type"] == "messages":
            # MessagesStreamPart — (message_chunk, metadata) from LLM calls
            msg, metadata = chunk["data"]
            print(msg.content, end="", flush=True)
        elif chunk["type"] == "custom":
            # CustomStreamPart — arbitrary data from get_stream_writer()
            print(chunk['data'])
        # if chunk["type"] == "messages":
        #     # MessagesStreamPart — (message_chunk, metadata) from LLM calls
        #     msg, metadata = chunk["data"]
        #     print(msg.content, end="", flush=True)