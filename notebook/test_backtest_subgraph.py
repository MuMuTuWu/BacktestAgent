# %%
"""
回测子图测试示例
"""
import sys
from pathlib import Path

# 添加项目根目录到sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.subgraphs.backtest import create_backtest_subgraph, run_backtest_subgraph_stream, BacktestSubgraphState
from src.state import GLOBAL_DATA_STATE
import pandas as pd
import numpy as np


def test_backtest_with_existing_signal():
    """测试回测功能（假设signal已存在）"""
    print("=" * 50)
    print("测试: 回测子图（假设signal已存在）")
    print("=" * 50)
    
    # 创建模拟数据
    dates = pd.date_range('2024-09-01', '2024-09-30', freq='D')
    stocks = ['000001.SZ']
    
    # 模拟收盘价数据
    close_data = pd.DataFrame(
        np.random.randn(len(dates), len(stocks)).cumsum(axis=0) + 100,
        index=dates,
        columns=stocks
    )
    
    # 模拟信号数据（简单的均线交叉）
    ma5 = close_data.rolling(5).mean()
    ma20 = close_data.rolling(20).mean()
    signal = pd.DataFrame(0, index=dates, columns=stocks)
    signal[ma5 > ma20] = 1
    signal[ma5 < ma20] = -1
    
    # 存入GLOBAL_DATA_STATE
    GLOBAL_DATA_STATE.override(
        ohlcv={'close': close_data},
        indicators={},
        signal={'ma_cross_signal': signal},
        backtest_results={}
    )
    
    print("\n已准备模拟数据:")
    print(f"  - 收盘价形状: {close_data.shape}")
    print(f"  - 信号形状: {signal.shape}")
    print(f"  - 买入信号数: {(signal == 1).sum().sum()}")
    print(f"  - 卖出信号数: {(signal == -1).sum().sum()}")
    
    # 创建回测子图
    graph = create_backtest_subgraph()
    
    # 初始化state
    initial_state: BacktestSubgraphState = {
        "messages": [
            {"role": "user", "content": "请对现有的信号执行回测，初始资金10万，手续费0.1%"}
        ],
        "current_task": "",
        "signal_ready": True,
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
    
    # 使用流式执行
    result = run_backtest_subgraph_stream(graph, initial_state, verbose=True)
    
    # 检查最终结果
    print(f"\n最终状态:")
    print(f"  回测完成: {result.get('backtest_completed')}")
    print(f"  收益就绪: {result.get('returns_ready')}")
    print(f"  PNL图就绪: {result.get('pnl_plot_ready')}")
    
    # 检查GLOBAL_DATA_STATE
    snapshot = GLOBAL_DATA_STATE.snapshot()
    print(f"\nGLOBAL_DATA_STATE中的回测结果字段: {list(snapshot.get('backtest_results', {}).keys())}")
    
    if 'daily_returns' in snapshot.get('backtest_results', {}):
        returns = snapshot['backtest_results']['daily_returns']
        print(f"\n日度收益统计:")
        print(f"  形状: {returns.shape}")
        print(f"  平均收益: {returns.mean().mean():.4f}")
        print(f"  标准差: {returns.std().mean():.4f}")
        print(f"  累计收益: {(1 + returns).prod().mean() - 1:.4f}")


def test_backtest_without_signal():
    """测试回测子图（signal不存在）"""
    print("\n" + "=" * 50)
    print("测试: 回测子图（signal不存在）")
    print("=" * 50)
    
    # 清空GLOBAL_DATA_STATE
    GLOBAL_DATA_STATE.override(
        ohlcv={},
        indicators={},
        signal={},
        backtest_results={}
    )
    
    # 创建回测子图
    graph = create_backtest_subgraph()
    
    # 初始化state
    initial_state: BacktestSubgraphState = {
        "messages": [
            {"role": "user", "content": "请执行回测"}
        ],
        "current_task": "",
        "signal_ready": False,
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
    
    print("\n初始状态: signal_ready=False")
    print("预期: 回测子图应该直接结束，因为没有信号数据")
    
    # 使用流式执行
    result = run_backtest_subgraph_stream(graph, initial_state, verbose=True)
    
    print(f"\n最终状态:")
    print(f"  回测完成: {result.get('backtest_completed')}")
    print(f"  错误信息: {result.get('error_messages', [])}")


if __name__ == "__main__":
    # 运行测试
    try:
        test_backtest_with_existing_signal()
        # test_backtest_without_signal()
        
        print("\n" + "=" * 50)
        print("所有测试完成！")
        print("=" * 50)
        
    except Exception as e:
        print(f"\n测试失败: {e}")
        import traceback
        traceback.print_exc()

# %%
