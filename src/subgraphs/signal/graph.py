"""
信号生成子图的构建函数。

该模块仅负责搭建信号子图的节点与路由，不直接编译或运行。
"""
from langgraph.graph import StateGraph, END

from .state import SignalSubgraphState
from .nodes import (
    reflection_node,
    data_fetch_node,
    signal_generate_node,
    validation_node,
)
from .routes import (
    route_from_reflection,
    route_after_data_fetch,
    route_after_signal_gen,
    route_after_validation,
)


def build_signal_graph() -> StateGraph[SignalSubgraphState]:
    """返回未编译的信号子图 StateGraph。"""
    graph = StateGraph(SignalSubgraphState)

    graph.add_node("reflection", reflection_node)
    graph.add_node("data_fetch", data_fetch_node)
    graph.add_node("signal_generate", signal_generate_node)
    graph.add_node("validate", validation_node)

    graph.set_entry_point("reflection")

    graph.add_conditional_edges(
        "reflection",
        route_from_reflection,
        {
            "data_fetch": "data_fetch",
            "signal_generate": "signal_generate",
            "validate": "validate",
            END: END,
        },
    )

    graph.add_conditional_edges(
        "data_fetch",
        route_after_data_fetch,
        {
            "reflection": "reflection",
            "validate": "validate",
            END: END,
        },
    )

    graph.add_conditional_edges(
        "signal_generate",
        route_after_signal_gen,
        {
            "reflection": "reflection",
            "validate": "validate",
        },
    )

    graph.add_conditional_edges(
        "validate",
        route_after_validation,
        {
            "reflection": "reflection",
            END: END,
        },
    )

    return graph
