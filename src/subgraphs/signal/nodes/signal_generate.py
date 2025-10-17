"""
信号生成节点：使用PythonAstREPLTool生成交易信号
"""
import pandas as pd
import numpy as np
from langchain_core.runnables import RunnableConfig
from langchain_experimental.tools.python.tool import PythonAstREPLTool
from langgraph.prebuilt import create_react_agent

from src.llm import get_llm
from src.state import GLOBAL_DATA_STATE
from ..state import SignalSubgraphState


SIGNAL_GENERATE_SYSTEM_PROMPT = """你是一个量化交易策略专家，负责根据用户策略描述生成交易信号。

## 你的职责
1. 理解用户的策略逻辑
2. 编写Python代码处理GLOBAL_DATA_STATE中的数据
3. 生成交易信号（1=买入, 0=持有, -1=卖出）
4. 将信号存入GLOBAL_DATA_STATE.signal

## 可用工具
**python_repl**: 执行Python代码分析数据并生成信号

可用的全局变量：
```python
from src.state import GLOBAL_DATA_STATE
import pandas as pd
import numpy as np

# 获取数据快照
snapshot = GLOBAL_DATA_STATE.snapshot()

# 访问OHLCV数据
ohlcv = snapshot['ohlcv']  # dict[str, DataFrame]
# 例如：
# close_df = ohlcv['close']  # DataFrame: index=日期, columns=股票代码
# open_df = ohlcv['open']
# high_df = ohlcv['high']
# low_df = ohlcv['low']
# vol_df = ohlcv['vol']

# 访问指标数据
indicators = snapshot['indicators']  # dict[str, DataFrame]
# 例如：
# pe_df = indicators['pe']
# pb_df = indicators['pb']

# 生成信号后存储
# GLOBAL_DATA_STATE.update('signal', {{'my_signal': signal_df}})
```

## 交易信号定义
- **1**: 买入信号（开多仓或平空仓）
- **0**: 无操作/持有
- **-1**: 卖出信号（平多仓或开空仓）
- **NaN**: 无效数据点

## 信号生成规范
1. **DataFrame格式**：
   - index: 日期（datetime格式）
   - columns: 股票代码
   - values: 1, 0, -1, 或 NaN

2. **时间对齐**：信号的日期必须与数据的日期对齐

3. **命名规范**：信号DataFrame的key应该是描述性的，例如：
   - "ma_cross_signal": 均线交叉信号
   - "momentum_signal": 动量信号
   - "mean_reversion_signal": 均值回归信号

## 常见策略模板

### 模板1：均线交叉策略
```python
close = snapshot['ohlcv']['close']

# 计算均线
ma_short = close.rolling(window=5).mean()
ma_long = close.rolling(window=20).mean()

# 生成信号
signal = pd.DataFrame(0, index=close.index, columns=close.columns)
signal[ma_short > ma_long] = 1  # 短期均线上穿长期均线，买入
signal[ma_short < ma_long] = -1  # 短期均线下穿长期均线，卖出

GLOBAL_DATA_STATE.update('signal', {{'ma_cross_signal': signal}})
print("均线交叉信号已生成，形状:", signal.shape)
```

### 模板2：估值策略
```python
pe = snapshot['indicators']['pe']
pb = snapshot['indicators']['pb']

# 计算估值百分位
pe_rank = pe.rank(axis=1, pct=True)
pb_rank = pb.rank(axis=1, pct=True)

# 综合评分
value_score = (pe_rank + pb_rank) / 2

# 生成信号
signal = pd.DataFrame(0, index=value_score.index, columns=value_score.columns)
signal[value_score < 0.3] = 1  # 低估值，买入
signal[value_score > 0.7] = -1  # 高估值，卖出

GLOBAL_DATA_STATE.update('signal', {{'value_signal': signal}})
print("估值信号已生成，形状:", signal.shape)
```

### 模板3：动量策略
```python
close = snapshot['ohlcv']['close']

# 计算收益率
returns = close.pct_change(periods=20)  # 20日收益率

# 计算动量排名
momentum_rank = returns.rank(axis=1, pct=True)

# 生成信号
signal = pd.DataFrame(0, index=close.index, columns=close.columns)
signal[momentum_rank > 0.8] = 1  # 高动量，买入
signal[momentum_rank < 0.2] = -1  # 低动量，卖出

GLOBAL_DATA_STATE.update('signal', {{'momentum_signal': signal}})
print("动量信号已生成，形状:", signal.shape)
```

## 工作流程
1. 从GLOBAL_DATA_STATE获取数据快照
2. 根据策略描述编写计算逻辑
3. 生成信号DataFrame
4. 验证信号格式（值必须是1/0/-1/NaN）
5. 存入GLOBAL_DATA_STATE.signal
6. 打印确认信息（信号名称、形状、非零信号数量）

## 输出要求
完成信号生成后，总结：
- 信号的名称和策略逻辑
- 信号的形状（多少天×多少只股票）
- 买入/卖出信号的数量
- 如果生成失败，说明错误原因

## 注意事项
- 确保所有计算都使用pandas向量化操作，避免循环
- 处理缺失值（NaN），使用fillna()或dropna()
- 确保信号值只包含1, 0, -1, NaN
- 不要假设数据的时间范围，使用实际的index
- 必须调用GLOBAL_DATA_STATE.update()存储信号，否则信号不会保存
- 如果策略描述不清晰，先用print()输出数据探索结果，再生成信号

## 错误处理
- KeyError：数据字段不存在，检查available_ohlcv/available_indicators
- ValueError：数据形状不匹配，确保时间对齐
- TypeError：数据类型错误，检查是否正确获取DataFrame"""

SIGNAL_GENERATE_USER_PROMPT_TEMPLATE = """## 当前数据状态
可用的OHLCV字段：{available_ohlcv}
可用的指标字段：{available_indicators}

## 策略描述
{strategy_description}"""


def signal_generate_node(
    state: SignalSubgraphState,
    config: RunnableConfig | None = None,
) -> dict:
    """信号生成节点：使用PythonAstREPLTool生成交易信号"""
    
    # 获取当前可用数据
    snapshot = GLOBAL_DATA_STATE.snapshot()
    
    # 创建信号生成工具
    py_tool = PythonAstREPLTool(
        name="python_repl",
        description="用于执行Python代码生成交易信号",
        globals={
            "GLOBAL_DATA_STATE": GLOBAL_DATA_STATE,
            "pd": pd,
            "np": np,
            "snapshot": snapshot
        }
    )
    
    agent = create_react_agent(get_llm(), tools=[py_tool])
    
    # 直接从state获取next_action_desc，作为策略描述
    strategy_description = state.get('next_action_desc', '未指定策略')
    
    # 填充user message
    user_message = SIGNAL_GENERATE_USER_PROMPT_TEMPLATE.format(
        available_ohlcv=list(snapshot.get('ohlcv', {}).keys()),
        available_indicators=list(snapshot.get('indicators', {}).keys()),
        strategy_description=strategy_description
    )
    
    # 创建system + user消息对
    messages = [
        {"role": "system", "content": SIGNAL_GENERATE_SYSTEM_PROMPT},
        {"role": "user", "content": user_message}
    ]
    
    # 执行agent
    result = agent.invoke({"messages": messages})
    
    # 检查信号是否生成
    snapshot = GLOBAL_DATA_STATE.snapshot()
    
    updates = {
        'signal_ready': bool(snapshot.get('signal')),
    }
    
    # 构建执行历史（返回新项，由add reducer自动追加）
    signal_fields = list(snapshot.get('signal', {}).keys())
    updates['execution_history'] = [
        f"信号生成完成: {signal_fields}"
    ]
    
    # 检查是否有错误
    if not updates['signal_ready']:
        updates['error_messages'] = ["信号生成失败：signal字段为空"]
    
    return updates
