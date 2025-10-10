"""
信号生成子图流式调用示例

展示如何使用 run_signal_subgraph_stream 函数实时查看子图执行过程
"""
import sys
from pathlib import Path

# 添加项目根目录到sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.subgraphs.signal import create_signal_subgraph, run_signal_subgraph_stream, SignalSubgraphState
from src.state import GLOBAL_DATA_STATE


def example_stream_execution():
    """演示流式执行的完整示例"""
    
    # 清空之前的数据
    GLOBAL_DATA_STATE.override(ohlcv={}, indicators={}, signal={})
    
    # 创建并编译子图
    graph = create_signal_subgraph()
    
    # 初始化状态
    initial_state: SignalSubgraphState = {
        "messages": [
            {"role": "user", "content": "请获取000001.SZ从20240901到20240930的数据，然后生成5日和20日均线交叉策略信号"}
        ],
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
    
    print("="*70)
    print("示例: 使用流式方式执行信号生成子图")
    print("="*70)
    print("\n用户请求:", initial_state["messages"][0]["content"])
    
    # 使用流式执行
    final_state = run_signal_subgraph_stream(
        compiled_graph=graph,
        initial_state=initial_state,
        verbose=True  # 打印详细信息
    )
    
    # 检查最终结果
    print("\n" + "="*70)
    print("执行结果汇总")
    print("="*70)
    
    print(f"\n数据状态:")
    print(f"  - OHLCV数据: {'✓ 就绪' if final_state.get('data_ready') else '✗ 未就绪'}")
    print(f"  - 指标数据: {'✓ 就绪' if final_state.get('indicators_ready') else '✗ 未就绪'}")
    print(f"  - 交易信号: {'✓ 就绪' if final_state.get('signal_ready') else '✗ 未就绪'}")
    
    # 显示GLOBAL_DATA_STATE中的数据
    snapshot = GLOBAL_DATA_STATE.snapshot()
    
    print(f"\nGLOBAL_DATA_STATE 数据:")
    print(f"  - OHLCV字段: {list(snapshot.get('ohlcv', {}).keys())}")
    print(f"  - 指标字段: {list(snapshot.get('indicators', {}).keys())}")
    print(f"  - 信号字段: {list(snapshot.get('signal', {}).keys())}")
    
    # 显示信号详情
    if snapshot.get('signal'):
        print(f"\n信号详情:")
        for signal_name, signal_df in snapshot['signal'].items():
            print(f"  [{signal_name}]")
            print(f"    - 形状: {signal_df.shape}")
            print(f"    - 买入信号: {(signal_df == 1).sum().sum()} 个")
            print(f"    - 卖出信号: {(signal_df == -1).sum().sum()} 个")
            print(f"    - 持有信号: {(signal_df == 0).sum().sum()} 个")
    
    # 显示执行历史
    print(f"\n执行历史 (共{len(final_state.get('execution_history', []))}步):")
    for i, step in enumerate(final_state.get('execution_history', []), 1):
        print(f"  {i}. {step}")


def example_silent_execution():
    """演示静默执行（不打印详细信息）"""
    
    # 清空之前的数据
    GLOBAL_DATA_STATE.override(ohlcv={}, indicators={}, signal={})
    
    # 创建并编译子图
    graph = create_signal_subgraph()
    
    # 初始化状态
    initial_state: SignalSubgraphState = {
        "messages": [
            {"role": "user", "content": "请获取000001.SZ从20240901到20240930的数据"}
        ],
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
    
    print("\n" + "="*70)
    print("示例: 静默模式执行（verbose=False）")
    print("="*70)
    
    # 静默执行
    final_state = run_signal_subgraph_stream(
        compiled_graph=graph,
        initial_state=initial_state,
        verbose=False  # 不打印详细信息
    )
    
    print(f"\n执行完成！数据就绪: {final_state.get('data_ready')}")


if __name__ == "__main__":
    # 运行示例
    try:
        # 示例1: 详细模式
        example_stream_execution()
        
        # 示例2: 静默模式
        # example_silent_execution()
        
    except Exception as e:
        print(f"\n执行失败: {e}")
        import traceback
        traceback.print_exc()
