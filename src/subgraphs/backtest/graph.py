"""
回测子图的构建函数
"""
from pathlib import Path
from typing import Optional

from langgraph.graph import StateGraph, END
from langchain_core.runnables.config import RunnableConfig

from src.utils import TaskLoggerCallbackHandler
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


def create_backtest_subgraph():
    """创建回测子图"""
    
    # 创建StateGraph
    graph = StateGraph(BacktestSubgraphState)
    
    # 添加节点
    graph.add_node("reflection", reflection_node)
    graph.add_node("backtest", backtest_node)
    graph.add_node("pnl_plot", pnl_plot_node)
    
    # 设置入口
    graph.set_entry_point("reflection")
    
    # 添加条件边：从反思节点出发
    graph.add_conditional_edges(
        "reflection",
        route_from_reflection,
        {
            "backtest": "backtest",
            "pnl_plot": "pnl_plot",
            END: END
        }
    )
    
    # 回测后返回反思节点进行检查
    graph.add_edge("backtest", "reflection")
    
    # PNL绘制后结束
    graph.add_edge("pnl_plot", END)
    
    # 编译子图
    return graph.compile()


def run_backtest_subgraph_stream(
    compiled_graph, 
    initial_state: BacktestSubgraphState,
    task_dir: Path,
    verbose: bool = False
):
    """
    使用流式方式运行回测子图，并记录日志
    
    Args:
        compiled_graph: 已编译的子图实例
        initial_state: 初始状态
        task_dir: 任务目录，日志文件将存储在此目录
        verbose: 是否同时打印到终端（可选）
    
    Returns:
        最终状态
    """
    # 创建日志记录器
    logger = TaskLoggerCallbackHandler(task_dir)
    
    # 配置callbacks
    config = RunnableConfig(callbacks=[logger])
    
    final_state = None
    
    if verbose:
        print("开始执行回测子图...")
    
    try:
        # 流式执行并记录
        for chunk in compiled_graph.stream(initial_state, config=config, stream_mode="updates"):
            for node_name, node_output in chunk.items():
                # 设置当前节点上下文
                logger.set_current_node(node_name)
                # 记录节点输出
                logger.log_node_output(node_name, node_output)
                
                if verbose:
                    print(f"  节点 [{node_name}] 执行完成")
                
                final_state = node_output
        
        # 写入执行摘要
        logger.write_summary(final_state)
        
        if verbose:
            print(f"执行完成，日志已保存到: {task_dir}")
    
    except Exception as e:
        if verbose:
            print(f"执行出错: {e}")
        raise
    
    return final_state
