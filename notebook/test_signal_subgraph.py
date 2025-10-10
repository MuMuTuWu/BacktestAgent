# %%
"""
信号生成子图测试示例
"""
import sys
from pathlib import Path

# 添加项目根目录到sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.subgraphs.signal import create_signal_subgraph, run_signal_subgraph_stream, SignalSubgraphState
from src.state import GLOBAL_DATA_STATE


def test_data_fetch():
    """测试数据获取功能（使用流式输出）"""
    print("=" * 50)
    print("测试1: 数据获取（流式）")
    print("=" * 50)
    
    # 创建子图
    graph = create_signal_subgraph()
    
    # 初始化state
    initial_state: SignalSubgraphState = {
        "messages": [
            {"role": "user", "content": "请获取股票000001.SZ从20240901到20240930的数据"}
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
    
    # 使用流式执行
    result = run_signal_subgraph_stream(graph, initial_state, verbose=True)
    
    # 检查最终结果
    print(f"\n最终状态:")
    print(f"  数据就绪: {result.get('data_ready')}")
    print(f"  指标就绪: {result.get('indicators_ready')}")
    
    # 检查GLOBAL_DATA_STATE
    snapshot = GLOBAL_DATA_STATE.snapshot()
    print(f"\nGLOBAL_DATA_STATE中的OHLCV字段: {list(snapshot.get('ohlcv', {}).keys())}")
    print(f"GLOBAL_DATA_STATE中的指标字段: {list(snapshot.get('indicators', {}).keys())}")
    
    if snapshot.get('ohlcv', {}).get('close') is not None:
        close_df = snapshot['ohlcv']['close']
        print(f"\n收盘价数据形状: {close_df.shape}")
        print(f"数据范围: {close_df.index.min()} 至 {close_df.index.max()}")


def test_signal_generation():
    """测试信号生成功能（使用流式输出）"""
    print("\n" + "=" * 50)
    print("测试2: 信号生成（流式）")
    print("=" * 50)
    
    # 先清空之前的数据
    GLOBAL_DATA_STATE.override(ohlcv={}, indicators={}, signal={})
    
    # 创建子图
    graph = create_signal_subgraph()
    
    # 初始化state（包含数据获取和信号生成）
    initial_state: SignalSubgraphState = {
        "messages": [
            {"role": "user", "content": "请获取000001.SZ从20240901到20240930的数据，然后生成一个简单的5日和20日均线交叉策略信号"}
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
    
    # 使用流式执行
    result = run_signal_subgraph_stream(graph, initial_state, verbose=True)
    
    # 检查最终结果
    print(f"\n最终状态:")
    print(f"  数据就绪: {result.get('data_ready')}")
    print(f"  信号就绪: {result.get('signal_ready')}")
    
    # 检查GLOBAL_DATA_STATE
    snapshot = GLOBAL_DATA_STATE.snapshot()
    print(f"\nGLOBAL_DATA_STATE中的信号字段: {list(snapshot.get('signal', {}).keys())}")
    
    if snapshot.get('signal'):
        for signal_name, signal_df in snapshot['signal'].items():
            print(f"\n信号 '{signal_name}':")
            print(f"  形状: {signal_df.shape}")
            print(f"  买入信号数: {(signal_df == 1).sum().sum()}")
            print(f"  卖出信号数: {(signal_df == -1).sum().sum()}")
            print(f"  持有信号数: {(signal_df == 0).sum().sum()}")


def test_clarification():
    """测试澄清功能（模拟场景）"""
    print("\n" + "=" * 50)
    print("测试3: 澄清场景（模拟）")
    print("=" * 50)
    
    # 创建子图
    graph = create_signal_subgraph()
    
    # 初始化state（故意提供不完整的信息）
    initial_state: SignalSubgraphState = {
        "messages": [
            {"role": "user", "content": "请帮我获取数据"}  # 缺少股票代码和时间范围
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
    
    print("\n初始用户请求: '请帮我获取数据' (信息不完整)")
    print("预期: 子图应该识别出需要澄清，并请求股票代码和时间范围")
    print("\n注意: 由于澄清节点会触发interrupt()，这里只打印预期行为")
    print("实际使用时需要在支持interrupt的环境中运行（如LangGraph Studio）")


if __name__ == "__main__":
    # 运行测试
    try:
        test_data_fetch()
        test_signal_generation()
        test_clarification()
        
        print("\n" + "=" * 50)
        print("所有测试完成！")
        print("=" * 50)
        
    except Exception as e:
        print(f"\n测试失败: {e}")
        import traceback
        traceback.print_exc()

# %%
