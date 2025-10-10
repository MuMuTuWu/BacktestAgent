"""
信号生成子图的构建函数
"""
from langgraph.graph import StateGraph, END
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich import box

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


def run_signal_subgraph_stream(
    compiled_graph, 
    initial_state: SignalSubgraphState, 
    verbose: bool = True,
    stream_mode: str = "updates"
):
    """
    使用流式方式运行信号生成子图
    
    Args:
        compiled_graph: 已编译的子图实例
        initial_state: 初始状态
        verbose: 是否打印详细信息
        stream_mode: 流式输出模式
            - "values": 每步后输出完整状态（默认）
            - "updates": 每步仅输出状态变化（推荐，更清晰）
            - "debug": 输出详细调试信息（包含节点执行元数据）
    
    Returns:
        最终状态
    """
    console = Console()
    final_state = None
    step_count = 0
    
    if verbose:
        console.print()
        console.print("="*60, style="bold cyan")
        console.print("🚀 开始流式执行信号生成子图", style="bold cyan", justify="center")
        console.print("="*60, style="bold cyan")
        console.print()
    
    try:
        for chunk in compiled_graph.stream(initial_state, stream_mode=stream_mode):
            step_count += 1
            
            if stream_mode == "debug":
                # debug 模式: 显示详细的执行信息
                if verbose:
                    console.print(f"\n[bold yellow]📊 调试信息 (步骤 {step_count})[/bold yellow]")
                    console.print(chunk)
            elif stream_mode == "values":
                # values 模式: 显示完整状态
                if verbose:
                    console.print(f"\n[bold green]📦 完整状态 (步骤 {step_count})[/bold green]")
                    _print_state_pretty(console, chunk)
                final_state = chunk
            else:
                # updates 模式 (默认): 仅显示变化
                for node_name, node_output in chunk.items():
                    if verbose:
                        _print_node_update_pretty(console, node_name, node_output, step_count)
                    final_state = node_output
        
        if verbose:
            console.print()
            console.print("="*60, style="bold green")
            console.print("✅ 子图执行完成", style="bold green", justify="center")
            console.print("="*60, style="bold green")
            
            if final_state:
                _print_final_summary(console, final_state)
    
    except Exception as e:
        if verbose:
            console.print(f"\n[bold red]❌ 执行出错: {e}[/bold red]")
        raise
    
    return final_state


def _print_node_update_pretty(console: "Console", node_name: str, node_output: dict, step_count: int):
    """使用 rich 库美化打印节点更新信息"""
    
    # 创建节点标题
    title = f"🔹 节点: {node_name} (步骤 {step_count})"
    
    # 创建内容文本
    content = Text()
    
    # 当前任务
    if 'current_task' in node_output and node_output['current_task']:
        content.append("📋 当前任务: ", style="bold cyan")
        content.append(f"{node_output['current_task']}\n", style="white")
    
    # 数据状态
    if any(k in node_output for k in ['data_ready', 'indicators_ready', 'signal_ready']):
        content.append("📊 数据状态: ", style="bold cyan")
        
        status_parts = []
        if 'data_ready' in node_output:
            status_parts.append(f"OHLCV={'✓' if node_output['data_ready'] else '✗'}")
        if 'indicators_ready' in node_output:
            status_parts.append(f"指标={'✓' if node_output['indicators_ready'] else '✗'}")
        if 'signal_ready' in node_output:
            status_parts.append(f"信号={'✓' if node_output['signal_ready'] else '✗'}")
        
        content.append(", ".join(status_parts) + "\n", style="white")
    
    # 执行历史（只显示最新的）
    if 'execution_history' in node_output and node_output['execution_history']:
        latest_history = node_output['execution_history'][-1]
        content.append("⚡ 最新执行: ", style="bold cyan")
        content.append(f"{latest_history}\n", style="white")
    
    # 错误信息
    if 'error_messages' in node_output and node_output['error_messages']:
        content.append("⚠️  错误: ", style="bold red")
        content.append(f"{node_output['error_messages'][-1]}\n", style="red")
    
    # 澄清需求
    if 'clarification_needed' in node_output and node_output['clarification_needed']:
        content.append("❓ 需要澄清: ", style="bold yellow")
        content.append(f"{node_output['clarification_needed']}\n", style="yellow")
    
    # 如果有内容才打印
    if content.plain:
        panel = Panel(
            content,
            title=title,
            border_style="blue",
            box=box.ROUNDED,
            padding=(0, 1)
        )
        console.print(panel)


def _print_state_pretty(console: "Console", state: dict):
    """美化打印完整状态"""
    
    table = Table(show_header=True, header_style="bold magenta", box=box.SIMPLE)
    table.add_column("字段", style="cyan", no_wrap=True)
    table.add_column("值", style="white")
    
    # 选择性显示关键字段
    key_fields = [
        'current_task', 'data_ready', 'indicators_ready', 'signal_ready',
        'clarification_needed', 'retry_count', 'max_retries'
    ]
    
    for field in key_fields:
        if field in state:
            value = state[field]
            # 格式化布尔值
            if isinstance(value, bool):
                value = "✓" if value else "✗"
            table.add_row(field, str(value))
    
    console.print(table)


def _print_final_summary(console: "Console", final_state: dict):
    """打印最终执行摘要"""
    
    console.print()
    
    # 创建摘要表格
    table = Table(title="📈 执行摘要", show_header=False, box=box.DOUBLE_EDGE)
    table.add_column("项目", style="bold cyan", width=20)
    table.add_column("状态", style="white")
    
    # 数据状态
    data_ready = final_state.get('data_ready', False)
    indicators_ready = final_state.get('indicators_ready', False)
    signal_ready = final_state.get('signal_ready', False)
    
    table.add_row("OHLCV数据", f"{'✅ 就绪' if data_ready else '❌ 未就绪'}")
    table.add_row("指标数据", f"{'✅ 就绪' if indicators_ready else '❌ 未就绪'}")
    table.add_row("交易信号", f"{'✅ 就绪' if signal_ready else '❌ 未就绪'}")
    
    # 执行统计
    history_count = len(final_state.get('execution_history', []))
    error_count = len(final_state.get('error_messages', []))
    retry_count = final_state.get('retry_count', 0)
    
    table.add_row("执行步骤数", str(history_count))
    table.add_row("错误次数", str(error_count))
    table.add_row("重试次数", str(retry_count))
    
    console.print(table)
