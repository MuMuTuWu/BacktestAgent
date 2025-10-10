"""
主图：串联signal子图和backtest子图
"""
import dotenv
dotenv.load_dotenv()

from typing import Annotated
from typing_extensions import TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

from config import config
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
    print("\n>>> 进入信号生成子图 <<<\n")
    
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
    
    # 使用流式方式执行并记录日志
    from src.subgraphs.signal import run_signal_subgraph_stream
    final_signal_state = run_signal_subgraph_stream(
        compiled_graph=signal_graph,
        initial_state=signal_state,
        task_dir=config['task_dir'],
        verbose=True
    )
    
    # 检查signal是否生成成功
    snapshot = GLOBAL_DATA_STATE.snapshot()
    signal_completed = bool(snapshot.get('signal'))
    
    print(f"\n>>> 信号生成子图完成：signal_ready={signal_completed} <<<\n")
    
    return {
        "signal_completed": signal_completed,
        "messages": final_signal_state.get('messages', state['messages'])
    }


def run_backtest_subgraph_node(state: MainGraphState) -> dict:
    """执行backtest子图的节点"""
    print("\n>>> 进入回测子图 <<<\n")
    
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
    
    # 使用流式方式执行并记录日志
    from src.subgraphs.backtest import run_backtest_subgraph_stream
    final_backtest_state = run_backtest_subgraph_stream(
        compiled_graph=backtest_graph,
        initial_state=backtest_state,
        task_dir=config['task_dir'],
        verbose=True
    )
    
    backtest_completed = final_backtest_state.get('pnl_plot_ready', False)
    
    print(f"\n>>> 回测子图完成：pnl_plot_ready={backtest_completed} <<<\n")
    
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
    print("\n" + "="*80)
    print("🎯 开始执行完整流程：信号生成 → 回测 → PNL绘制")
    print("="*80 + "\n")
    print(f"日志目录: {config['task_dir']}\n")
    
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
    
    print("\n" + "="*80)
    print("✅ 完整流程执行完成")
    print("="*80 + "\n")
    
    # 打印最终结果
    print(f"信号生成: {'✅ 成功' if final_state.get('signal_completed') else '❌ 失败'}")
    print(f"回测完成: {'✅ 成功' if final_state.get('backtest_completed') else '❌ 失败'}")
    
    # 检查GLOBAL_DATA_STATE
    snapshot = GLOBAL_DATA_STATE.snapshot()
    print(f"\nGLOBAL_DATA_STATE:")
    print(f"  - OHLCV字段: {list(snapshot.get('ohlcv', {}).keys())}")
    print(f"  - 信号字段: {list(snapshot.get('signal', {}).keys())}")
    print(f"  - 回测结果字段: {list(snapshot.get('backtest_results', {}).keys())}")
    print(f"\n日志文件已保存到: {config['task_dir']}")


if __name__ == "__main__":
    main()
