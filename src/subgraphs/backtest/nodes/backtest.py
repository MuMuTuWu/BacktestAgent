"""
回测节点：使用vectorbt执行回测并计算日度收益
"""
import pandas as pd
import numpy as np
from langchain_experimental.tools.python.tool import PythonAstREPLTool
from langgraph.prebuilt import create_react_agent

from src.llm import get_llm
from src.state import GLOBAL_DATA_STATE
from ..state import BacktestSubgraphState


BACKTEST_AGENT_PROMPT = """你是一个量化回测专家，负责使用vectorbt框架执行回测并计算日度收益。

## 你的职责
1. 从GLOBAL_DATA_STATE读取signal和ohlcv数据
2. 使用vectorbt执行回测
3. 计算策略的日度return
4. 将日度return存入GLOBAL_DATA_STATE.backtest_results

## 可用工具
**python_repl**: 执行Python代码进行回测

可用的全局变量：
```python
from src.state import GLOBAL_DATA_STATE
import pandas as pd
import numpy as np
import vectorbt as vbt

# 获取数据快照
snapshot = GLOBAL_DATA_STATE.snapshot()

# 访问信号数据
signal_data = snapshot['signal']  # dict[str, DataFrame]
# 例如：signal_df = signal_data['ma_cross_signal']

# 访问OHLCV数据
ohlcv = snapshot['ohlcv']  # dict[str, DataFrame]
# 例如：close_df = ohlcv['close']

# 执行回测后存储结果
# GLOBAL_DATA_STATE.update('backtest_results', {{'daily_returns': returns_df}})
```

## 当前数据状态
可用的信号字段：{available_signals}
可用的OHLCV字段：{available_ohlcv}

## 回测参数
{backtest_params}

## vectorbt回测流程

### 步骤1：准备数据
```python
snapshot = GLOBAL_DATA_STATE.snapshot()

# 获取信号（假设第一个信号）
signal_name = list(snapshot['signal'].keys())[0]
signal = snapshot['signal'][signal_name]

# 获取收盘价
close = snapshot['ohlcv']['close']

# 确保时间对齐
signal = signal.reindex(close.index)
```

### 步骤2：执行vectorbt回测
```python
import vectorbt as vbt

# 生成进场/出场信号
entries = signal == 1  # 买入信号
exits = signal == -1   # 卖出信号

# 创建Portfolio
portfolio = vbt.Portfolio.from_signals(
    close=close,
    entries=entries,
    exits=exits,
    init_cash=100000,  # 初始资金
    fees=0.001,        # 手续费率
    slippage=0.0       # 滑点
)
```

### 步骤3：获取日度收益
```python
# vectorbt的portfolio.returns()默认返回日度收益
daily_returns = portfolio.returns()

# 检查数据
print("日度收益形状:", daily_returns.shape)
print("有效收益点数:", daily_returns.notna().sum().sum())
print("平均日收益:", daily_returns.mean().mean())
```

### 步骤4：存储结果
```python
# 存入GLOBAL_DATA_STATE
GLOBAL_DATA_STATE.update('backtest_results', {{'daily_returns': daily_returns}})
print("回测完成，日度收益已存储")
```

## 输出要求
完成回测后，总结：
- 使用的信号名称
- 回测的时间范围
- 日度收益的形状（多少天×多少只股票）
- 收益统计（平均收益、最大回撤等关键指标）
- 如果回测失败，说明错误原因

## 注意事项
- 确保信号和价格数据的时间对齐
- 处理缺失值（NaN），避免回测中断
- 确保daily_returns存储到GLOBAL_DATA_STATE
- 如果有多个信号，优先使用第一个信号
- 如果收盘价数据有多列（多只股票），vectorbt会自动处理

## 常见错误处理
- **KeyError**: 数据字段不存在，检查available_signals/available_ohlcv
- **ValueError**: 数据形状不匹配，确保时间对齐（使用reindex）
- **TypeError**: 数据类型错误，检查是否正确获取DataFrame
- **IndexError**: 信号列表为空，确认signal字段中有数据
"""


def backtest_node(state: BacktestSubgraphState) -> dict:
    """回测节点：使用vectorbt执行回测并计算日度收益"""
    
    # 获取当前可用数据
    snapshot = GLOBAL_DATA_STATE.snapshot()
    
    # 创建回测工具
    py_tool = PythonAstREPLTool(
        name="python_repl",
        description="用于执行vectorbt回测",
        globals={
            "GLOBAL_DATA_STATE": GLOBAL_DATA_STATE,
            "pd": pd,
            "np": np,
            "snapshot": snapshot
        }
    )
    
    agent = create_react_agent(get_llm(), tools=[py_tool])
    
    # 填充prompt
    backtest_params = state.get('backtest_params', {
        'init_cash': 100000,
        'fees': 0.001,
        'slippage': 0.0
    })
    
    # 格式化回测参数
    params_str = "\n".join([f"- {k}: {v}" for k, v in backtest_params.items()])
    
    prompt = BACKTEST_AGENT_PROMPT.format(
        available_signals=list(snapshot.get('signal', {}).keys()),
        available_ohlcv=list(snapshot.get('ohlcv', {}).keys()),
        backtest_params=params_str
    )
    
    # 执行agent
    result = agent.invoke({"messages": [{"role": "user", "content": prompt}]})
    
    # 检查回测结果
    snapshot = GLOBAL_DATA_STATE.snapshot()
    
    updates = {
        'backtest_completed': 'daily_returns' in snapshot.get('backtest_results', {}),
        'returns_ready': 'daily_returns' in snapshot.get('backtest_results', {}),
    }
    
    # 追加执行历史
    if 'execution_history' not in state:
        updates['execution_history'] = []
    else:
        updates['execution_history'] = state['execution_history'].copy()
    
    if updates['backtest_completed']:
        returns = snapshot['backtest_results']['daily_returns']
        updates['execution_history'].append(
            f"回测完成: 收益形状={returns.shape}, 有效点数={returns.notna().sum().sum()}"
        )
    else:
        updates['execution_history'].append("回测执行但未生成daily_returns")
        # 记录错误
        if 'error_messages' not in state:
            updates['error_messages'] = []
        else:
            updates['error_messages'] = state['error_messages'].copy()
        updates['error_messages'].append("回测失败：未生成daily_returns字段")
    
    return updates
