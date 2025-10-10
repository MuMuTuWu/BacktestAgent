"""
回测子图的构建函数
"""
from langgraph.graph import StateGraph, END
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich import box

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
    verbose: bool = True,
    stream_mode: str = "updates"
):
    """
    使用流式方式运行回测子图
    
    Args:
        compiled_graph: 已编译的子图实例
        initial_state: 初始状态
        verbose: 是否打印详细信息
        stream_mode: 流式输出模式
            - "values": 每步后输出完整状态
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
        console.print("🚀 开始流式执行回测子图", style="bold cyan", justify="center")
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
    if any(k in node_output for k in ['signal_ready', 'backtest_completed', 'returns_ready', 'pnl_plot_ready']):
        content.append("📊 数据状态: ", style="bold cyan")
        
        status_parts = []
        if 'signal_ready' in node_output:
            status_parts.append(f"信号={'✓' if node_output['signal_ready'] else '✗'}")
        if 'backtest_completed' in node_output:
            status_parts.append(f"回测={'✓' if node_output['backtest_completed'] else '✗'}")
        if 'returns_ready' in node_output:
            status_parts.append(f"收益={'✓' if node_output['returns_ready'] else '✗'}")
        if 'pnl_plot_ready' in node_output:
            status_parts.append(f"PNL图={'✓' if node_output['pnl_plot_ready'] else '✗'}")
        
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
        'current_task', 'signal_ready', 'backtest_completed', 'returns_ready', 
        'pnl_plot_ready', 'retry_count', 'max_retries'
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
    signal_ready = final_state.get('signal_ready', False)
    backtest_completed = final_state.get('backtest_completed', False)
    returns_ready = final_state.get('returns_ready', False)
    pnl_plot_ready = final_state.get('pnl_plot_ready', False)
    
    table.add_row("信号就绪", f"{'✅ 就绪' if signal_ready else '❌ 未就绪'}")
    table.add_row("回测完成", f"{'✅ 完成' if backtest_completed else '❌ 未完成'}")
    table.add_row("收益计算", f"{'✅ 完成' if returns_ready else '❌ 未完成'}")
    table.add_row("PNL图生成", f"{'✅ 完成' if pnl_plot_ready else '❌ 未完成'}")
    
    # 执行统计
    history_count = len(final_state.get('execution_history', []))
    error_count = len(final_state.get('error_messages', []))
    retry_count = final_state.get('retry_count', 0)
    
    table.add_row("执行步骤数", str(history_count))
    table.add_row("错误次数", str(error_count))
    table.add_row("重试次数", str(retry_count))
    
    console.print(table)
