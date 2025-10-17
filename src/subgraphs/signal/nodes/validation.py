"""
验证节点：验证数据和信号的质量
"""
import pandas as pd
import numpy as np
from langchain_core.runnables import RunnableConfig
from langchain_experimental.tools.python.tool import PythonAstREPLTool
from langgraph.prebuilt import create_react_agent

from src.llm import get_light_llm
from src.state import GLOBAL_DATA_STATE
from src.utils import extract_json_from_response
from ..state import SignalSubgraphState


VALIDATION_SYSTEM_PROMPT = """你是一个数据质量检查专家，负责验证数据和信号的完整性与正确性。

## 你的职责
1. 检查数据是否成功加载到GLOBAL_DATA_STATE
2. 验证数据的形状、类型、缺失值情况
3. 检查信号是否符合规范
4. 识别潜在的数据问题

## 可用工具
**python_repl**: 执行Python代码进行验证

可用全局变量：
```python
from src.state import GLOBAL_DATA_STATE
import pandas as pd
import numpy as np

snapshot = GLOBAL_DATA_STATE.snapshot()
```

## 验证检查清单

### 1. 数据存在性检查
```python
snapshot = GLOBAL_DATA_STATE.snapshot()

# 检查OHLCV数据
ohlcv_fields = list(snapshot['ohlcv'].keys())
print(f"OHLCV字段: {{ohlcv_fields}}")

# 检查指标数据
indicator_fields = list(snapshot['indicators'].keys())
print(f"指标字段: {{indicator_fields}}")

# 检查信号数据
signal_fields = list(snapshot['signal'].keys())
print(f"信号字段: {{signal_fields}}")
```

### 2. 数据形状和范围检查
```python
# 检查数据形状
for field, df in snapshot['ohlcv'].items():
    print(f"{{field}}: {{df.shape}} - {{df.index.min()}} 至 {{df.index.max()}}")
    print(f"  缺失值: {{df.isna().sum().sum()}} / {{df.size}}")
    print(f"  股票数量: {{df.columns.nunique()}}")
    print(f"  日期数量: {{len(df)}}")
```

### 3. 数据质量检查
```python
# 检查异常值
close = snapshot['ohlcv']['close']

# 检查是否有负值
if (close < 0).any().any():
    print("警告：发现负值价格数据")

# 检查是否有极端值（超过10倍涨跌幅）
returns = close.pct_change()
extreme_returns = (returns.abs() > 0.5).sum().sum()
if extreme_returns > 0:
    print(f"警告：发现{{extreme_returns}}个极端收益率（>50%）")

# 检查缺失值比例
missing_ratio = close.isna().sum() / len(close)
high_missing = missing_ratio[missing_ratio > 0.5]
if not high_missing.empty:
    print(f"警告：{{len(high_missing)}}只股票的缺失值超过50%")
```

### 4. 信号验证
```python
# 检查信号格式
for signal_name, signal_df in snapshot['signal'].items():
    print(f"\\n验证信号: {{signal_name}}")
    print(f"形状: {{signal_df.shape}}")
    
    # 检查值范围
    unique_values = signal_df.stack().unique()
    print(f"信号值: {{sorted([v for v in unique_values if not pd.isna(v)])}}")
    
    # 信号值必须是 -1, 0, 1 或 NaN
    valid_values = {{-1, 0, 1}}
    invalid = set(unique_values) - valid_values - {{np.nan}}
    if invalid:
        print(f"错误：发现非法信号值 {{invalid}}")
    
    # 统计信号分布
    buy_signals = (signal_df == 1).sum().sum()
    sell_signals = (signal_df == -1).sum().sum()
    hold_signals = (signal_df == 0).sum().sum()
    print(f"买入信号: {{buy_signals}}, 卖出信号: {{sell_signals}}, 持有: {{hold_signals}}")
    
    # 检查时间对齐
    ohlcv_dates = snapshot['ohlcv']['close'].index
    signal_dates = signal_df.index
    if not signal_dates.equals(ohlcv_dates):
        print(f"警告：信号日期与数据日期不完全对齐")
        print(f"  数据日期范围: {{ohlcv_dates.min()}} 至 {{ohlcv_dates.max()}}")
        print(f"  信号日期范围: {{signal_dates.min()}} 至 {{signal_dates.max()}}")
```

### 5. 时间对齐检查
```python
# 确保所有DataFrame的时间索引一致
ohlcv_indices = [df.index for df in snapshot['ohlcv'].values()]
indicator_indices = [df.index for df in snapshot['indicators'].values()]
signal_indices = [df.index for df in snapshot['signal'].values()]

all_indices = ohlcv_indices + indicator_indices + signal_indices

if len(all_indices) > 1:
    reference = all_indices[0]
    for i, idx in enumerate(all_indices[1:], 1):
        if not idx.equals(reference):
            print(f"警告：第{{i}}个DataFrame的时间索引不一致")
```

## 验证结果输出格式

完成验证后，以JSON格式输出结果：

```json
{{{{
  "validation_passed": true/false,
  "checks_performed": [
    "数据存在性检查",
    "数据形状检查",
    "数据质量检查",
    "信号格式检查",
    "时间对齐检查"
  ],
  "issues_found": [
    {{{{"severity": "error/warning", "message": "具体问题描述"}}}}
  ],
  "data_summary": {{{{
    "ohlcv_fields": ["open", "close", ...],
    "indicator_fields": ["pe", "pb", ...],
    "signal_fields": ["ma_cross_signal", ...],
    "date_range": "2024-01-01 至 2024-12-31",
    "stock_count": 300,
    "total_data_points": 75000
  }}}},
  "recommendations": [
    "建议或下一步行动"
  ]
}}}}
```

## 验证严重程度定义
- **error**: 严重问题，会导致后续流程失败（如数据不存在、信号格式错误）
- **warning**: 潜在问题，可能影响结果质量（如缺失值较多、极端值）
- **info**: 提示信息，不影响执行（如数据统计信息）

## 决策规则
1. **如果有error级别问题**：
   - validation_passed = false
   - 建议返回reflection节点重新评估

2. **如果只有warning**：
   - validation_passed = true
   - 在recommendations中说明警告，但允许继续

3. **如果一切正常**：
   - validation_passed = true
   - 建议进入下一步或结束

## 注意事项
- 使用python_repl工具运行所有检查代码
- 不要假设数据格式，实际检查后再下结论
- 对于警告级别的问题，评估是否真正影响策略执行
- 缺失值不一定是错误，取决于策略是否需要完整数据
- 提供具体的数据统计，而不只是"数据正常\""""

VALIDATION_USER_PROMPT_TEMPLATE = """## 当前验证目标
- 验证类型: {validation_type}
- 期望的数据字段: {expected_fields}"""


def validation_node(
    state: SignalSubgraphState,
    config: RunnableConfig | None = None,
) -> dict:
    """验证节点：验证数据和信号的质量"""
    
    snapshot = GLOBAL_DATA_STATE.snapshot()
    
    py_tool = PythonAstREPLTool(
        name="python_repl",
        description="用于执行数据验证代码",
        globals={
            "GLOBAL_DATA_STATE": GLOBAL_DATA_STATE,
            "snapshot": snapshot,
            "pd": pd,
            "np": np
        }
    )
    
    agent = create_react_agent(get_light_llm(), tools=[py_tool])
    
    # 根据当前任务确定验证类型
    validation_type = 'signal' if state.get('signal_ready') else 'data'
    expected_fields = []  # next_action_desc 现在是字符串，validation_node 不再从中提取 required_indicators
    
    # 填充user message
    user_message = VALIDATION_USER_PROMPT_TEMPLATE.format(
        validation_type=validation_type,
        expected_fields=expected_fields
    )
    
    # 创建system + user消息对
    messages = [
        {"role": "system", "content": VALIDATION_SYSTEM_PROMPT},
        {"role": "user", "content": user_message}
    ]
    
    # 执行agent
    result = agent.invoke({"messages": messages})
    
    # 提取最后一条消息
    final_message = result['messages'][-1]
    response_content = final_message.content if hasattr(final_message, 'content') else str(final_message)
    
    # 尝试解析JSON响应
    state_update = {}
    has_errors = False  # 标记本次验证是否发现error
    
    parse_result = extract_json_from_response(response_content)
    
    if not parse_result["success"]:
        # JSON解析失败，生成新prompt让LLM重试
        error_info = parse_result["error"]
        
        # 创建重试prompt
        retry_prompt = f"""前一次JSON解析失败，请重新生成。

错误类型：{error_info['type']}
错误信息：{error_info['message']}

你的原始响应是（部分）：
{error_info['raw_response']}

请重新执行验证，并以JSON格式输出验证结果。必须包含以下字段：
- "validation_passed": true/false
- "checks_performed": [执行的检查列表]
- "issues_found": [问题列表]
- "data_summary": 数据摘要
- "recommendations": [建议列表]"""
        
        # 重新调用agent
        agent = create_react_agent(get_light_llm(), tools=[py_tool])
        retry_result = agent.invoke({"messages": messages + [
            {"role": "assistant", "content": response_content},
            {"role": "user", "content": retry_prompt}
        ]})
        
        # 提取重试后的响应
        retry_message = retry_result['messages'][-1]
        retry_response_content = retry_message.content if hasattr(retry_message, 'content') else str(retry_message)
        
        # 重新解析
        parse_result = extract_json_from_response(retry_response_content)
        
        # 追加执行历史（返回新项，由add reducer自动追加）
        state_update = {
            'execution_history': [f"验证: JSON解析失败后重试 - 错误: {error_info['type']}"]
        }
    
    if parse_result["success"]:
        validation_result = parse_result["data"]
        
        # 检查是否有error级别的问题
        issues = validation_result.get('issues_found', [])
        has_errors = any(issue.get('severity') == 'error' for issue in issues)
        
        if has_errors:
            # 本次验证发现error，追加到error_messages（返回新项，由add reducer自动追加）
            error_msgs = [issue.get('message', 'Unknown error') for issue in issues if issue.get('severity') == 'error']
            state_update['error_messages'] = error_msgs
    else:
        # 重试后仍然失败，将错误信息作为验证失败
        error_info = parse_result["error"]
        has_errors = True
        error_msg = f"验证节点JSON解析失败（重试后）: [{error_info['type']}] {error_info['message']}"
        state_update['error_messages'] = [error_msg]
    
    # 验证通过时清空错误信息和重置重试计数
    if not has_errors:
        state_update['error_messages'] = []
        state_update['retry_count'] = 0
    
    # 追加执行历史（返回新项，由add reducer自动追加）
    state_update['execution_history'] = [f"验证完成: {validation_type}, 有错误={has_errors}"]
    
    return state_update
