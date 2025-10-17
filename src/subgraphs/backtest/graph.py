"""
回测子图的构建函数。

该模块仅负责定义回测子图的节点与路由，不直接编译或执行。
"""
from langgraph.graph import StateGraph, END

from .state import BacktestSubgraphState
from .nodes import (
    reflection_node,
    backtest_node,
    pnl_plot_node,
)
from .routes import (
    route_from_reflection,
    route_after_backtest,
    route_after_pnl_plot,
)


def build_backtest_graph() -> StateGraph[BacktestSubgraphState]:
    """返回未编译的回测子图 StateGraph。"""
    graph = StateGraph(BacktestSubgraphState)

    graph.add_node("reflection", reflection_node)
    graph.add_node("backtest", backtest_node)
    graph.add_node("pnl_plot", pnl_plot_node)

    graph.set_entry_point("reflection")

    graph.add_conditional_edges(
        "reflection",
        route_from_reflection,
        {
            "backtest": "backtest",
            "pnl_plot": "pnl_plot",
            END: END,
        },
    )

    graph.add_edge("backtest", "reflection")
    graph.add_edge("pnl_plot", END)
    return graph
