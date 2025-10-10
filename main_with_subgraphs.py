"""
主图：串联signal子图和backtest子图
"""
import dotenv
dotenv.load_dotenv()

from typing import Annotated
from typing_extensions import TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from rich.console import Console

from src.state import GLOBAL_DATA_STATE
from src.subgraphs.signal import create_signal_subgraph, SignalSubgraphState
from src.subgraphs.backtest import create_backtest_subgraph, BacktestSubgraphState


class MainGraphState(TypedDict):
    """主图状态"""
    messages: Annotated[list, add_messages]
    signal_completed: bool
    backtest_completed: bool


def run_signal_subgraph_node(state: MainGraphState) -> dict:
    """执行signal子图的节点"""
    console = Console()
    console.print("\n[bold blue]>>> 进入信号生成子图 <<<[/bold blue]\n")
    
    # 创建signal子图
    signal_graph = create_signal_subgraph()
    
    # 初始化signal子图状态
    signal_state: SignalSubgraphState = {
        "messages": state['messages'],
        "current_task": "",
        "data_ready": False,
        "indicators_ready": False,
        "signal_ready": False,
        "user_intent": {},
        "clarification_needed": None,
        "clarification_count": 0,
        "execution_history": [],
        "error_messages": [],
        "max_retries": 3,
        "retry_count": 0,
    }
    
    # 执行signal子图
    final_signal_state = signal_graph.invoke(signal_state)
    
    # 检查signal是否生成成功
    snapshot = GLOBAL_DATA_STATE.snapshot()
    signal_completed = bool(snapshot.get('signal'))
    
    console.print(f"\n[bold blue]>>> 信号生成子图完成：signal_ready={signal_completed} <<<[/bold blue]\n")
    
    return {
        "signal_completed": signal_completed,
        "messages": final_signal_state.get('messages', state['messages'])
    }


def run_backtest_subgraph_node(state: MainGraphState) -> dict:
    """执行backtest子图的节点"""
    console = Console()
    console.print("\n[bold magenta]>>> 进入回测子图 <<<[/bold magenta]\n")
    
    # 创建backtest子图
    backtest_graph = create_backtest_subgraph()
    
    # 检查signal是否就绪
    snapshot = GLOBAL_DATA_STATE.snapshot()
    signal_ready = bool(snapshot.get('signal'))
    
    # 初始化backtest子图状态
    backtest_state: BacktestSubgraphState = {
        "messages": state['messages'],
        "current_task": "",
        "signal_ready": signal_ready,
        "backtest_completed": False,
        "returns_ready": False,
        "pnl_plot_ready": False,
        "backtest_params": {
            "init_cash": 100000,
            "fees": 0.001,
            "slippage": 0.0
        },
        "execution_history": [],
        "error_messages": [],
        "max_retries": 3,
        "retry_count": 0,
    }
    
    # 执行backtest子图
    final_backtest_state = backtest_graph.invoke(backtest_state)
    
    backtest_completed = final_backtest_state.get('pnl_plot_ready', False)
    
    console.print(f"\n[bold magenta]>>> 回测子图完成：pnl_plot_ready={backtest_completed} <<<[/bold magenta]\n")
    
    return {
        "backtest_completed": backtest_completed,
        "messages": final_backtest_state.get('messages', state['messages'])
    }


def route_after_signal(state: MainGraphState) -> str:
    """signal子图后的路由"""
    if state.get('signal_completed', False):
        return 'backtest'
    return END


def create_main_graph():
    """创建主图"""
    graph = StateGraph(MainGraphState)
    
    # 添加子图节点
    graph.add_node("signal", run_signal_subgraph_node)
    graph.add_node("backtest", run_backtest_subgraph_node)
    
    # 设置入口
    graph.set_entry_point("signal")
    
    # 添加条件边
    graph.add_conditional_edges(
        "signal",
        route_after_signal,
        {
            "backtest": "backtest",
            END: END
        }
    )
    
    # backtest后结束
    graph.add_edge("backtest", END)
    
    return graph.compile()


def main():
    """主函数：测试完整流程"""
    console = Console()
    
    console.print("\n" + "="*80, style="bold green")
    console.print("🎯 开始执行完整流程：信号生成 → 回测 → PNL绘制", style="bold green", justify="center")
    console.print("="*80 + "\n", style="bold green")
    
    # 创建主图
    main_graph = create_main_graph()
    
    # 初始化主图状态
    initial_state: MainGraphState = {
        "messages": [
            {"role": "user", "content": "请获取000001.SZ从20240901到20240930的数据，然后生成5日和20日均线交叉策略信号，并执行回测"}
        ],
        "signal_completed": False,
        "backtest_completed": False,
    }
    
    # 执行主图
    final_state = main_graph.invoke(initial_state)
    
    console.print("\n" + "="*80, style="bold green")
    console.print("✅ 完整流程执行完成", style="bold green", justify="center")
    console.print("="*80 + "\n", style="bold green")
    
    # 打印最终结果
    console.print(f"信号生成: {'✅ 成功' if final_state.get('signal_completed') else '❌ 失败'}")
    console.print(f"回测完成: {'✅ 成功' if final_state.get('backtest_completed') else '❌ 失败'}")
    
    # 检查GLOBAL_DATA_STATE
    snapshot = GLOBAL_DATA_STATE.snapshot()
    console.print(f"\nGLOBAL_DATA_STATE:")
    console.print(f"  - OHLCV字段: {list(snapshot.get('ohlcv', {}).keys())}")
    console.print(f"  - 信号字段: {list(snapshot.get('signal', {}).keys())}")
    console.print(f"  - 回测结果字段: {list(snapshot.get('backtest_results', {}).keys())}")


if __name__ == "__main__":
    main()
