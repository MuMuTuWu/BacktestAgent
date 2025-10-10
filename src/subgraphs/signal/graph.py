"""
信号生成子图的构建函数
"""
from langgraph.graph import StateGraph, END

from .state import SignalSubgraphState
from .nodes import (
    reflection_node,
    data_fetch_node,
    signal_generate_node,
    clarify_node,
    validation_node,
)
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


def run_signal_subgraph_stream(compiled_graph, initial_state: SignalSubgraphState, verbose: bool = True):
    """
    使用流式方式运行信号生成子图
    
    Args:
        compiled_graph: 已编译的子图实例
        initial_state: 初始状态
        verbose: 是否打印详细信息
    
    Returns:
        最终状态
    """
    final_state = None
    
    print("\n" + "="*50)
    print("开始流式执行信号生成子图")
    print("="*50)
    
    for step_output in compiled_graph.stream(initial_state):
        # stream 返回的是 {node_name: node_output} 格式
        for node_name, node_output in step_output.items():
            if verbose:
                print(f"\n[节点: {node_name}]")
                
                # 打印当前任务
                if 'current_task' in node_output:
                    print(f"  当前任务: {node_output.get('current_task')}")
                
                # 打印数据状态
                if 'data_ready' in node_output or 'indicators_ready' in node_output or 'signal_ready' in node_output:
                    print(f"  数据状态: OHLCV={node_output.get('data_ready', False)}, "
                          f"指标={node_output.get('indicators_ready', False)}, "
                          f"信号={node_output.get('signal_ready', False)}")
                
                # 打印执行历史（只显示最新的一条）
                if 'execution_history' in node_output and node_output['execution_history']:
                    latest_history = node_output['execution_history'][-1]
                    print(f"  执行: {latest_history}")
                
                # 打印错误信息
                if 'error_messages' in node_output and node_output['error_messages']:
                    print(f"  ⚠️  错误: {node_output['error_messages'][-1]}")
                
                # 打印澄清需求
                if 'clarification_needed' in node_output and node_output['clarification_needed']:
                    print(f"  ❓ 需要澄清: {node_output['clarification_needed']}")
            
            # 保存最终状态
            final_state = node_output
    
    print("\n" + "="*50)
    print("子图执行完成")
    print("="*50)
    
    return final_state
