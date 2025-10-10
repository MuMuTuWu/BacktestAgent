"""
信号生成子图的构建函数
"""
from langgraph.graph import StateGraph, END

from .state import SignalSubgraphState
from .reflection import reflection_node
from .data_fetch import data_fetch_node
from .signal_generate import signal_generate_node
from .clarify import clarify_node
from .validation import validation_node
from .routes import (
    route_from_reflection,
    route_after_data_fetch,
    route_after_signal_gen,
    route_after_validation,
    route_after_clarify,
)


def create_signal_subgraph():
    """创建信号生成子图"""
    
    # 创建StateGraph
    graph = StateGraph(SignalSubgraphState)
    
    # 添加节点
    graph.add_node("reflection", reflection_node)
    graph.add_node("data_fetch", data_fetch_node)
    graph.add_node("signal_generate", signal_generate_node)
    graph.add_node("clarify", clarify_node)
    graph.add_node("validate", validation_node)
    
    # 设置入口
    graph.set_entry_point("reflection")
    
    # 添加条件边：从反思节点出发
    graph.add_conditional_edges(
        "reflection",
        route_from_reflection,
        {
            "data_fetch": "data_fetch",
            "signal_generate": "signal_generate",
            "clarify": "clarify",
            "validate": "validate",
            END: END
        }
    )
    
    # 数据获取后的路由
    graph.add_conditional_edges(
        "data_fetch",
        route_after_data_fetch,
        {
            "reflection": "reflection",
            "validate": "validate",
            "clarify": "clarify"
        }
    )
    
    # 信号生成后的路由
    graph.add_conditional_edges(
        "signal_generate",
        route_after_signal_gen,
        {
            "reflection": "reflection",
            "validate": "validate"
        }
    )
    
    # 验证后的路由
    graph.add_conditional_edges(
        "validate",
        route_after_validation,
        {
            "reflection": "reflection",
            "clarify": "clarify",
            END: END
        }
    )
    
    # 澄清后的路由
    graph.add_edge("clarify", "reflection")
    
    # 编译子图
    return graph.compile()
