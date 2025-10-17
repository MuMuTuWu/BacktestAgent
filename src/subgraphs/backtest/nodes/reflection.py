"""
反思节点：检查回测状态并制定执行计划
"""
import pandas as pd
from langchain_core.runnables import RunnableConfig
from langchain_experimental.tools.python.tool import PythonAstREPLTool
from langgraph.prebuilt import create_react_agent

from src.llm import get_llm
from src.state import GLOBAL_DATA_STATE
from src.utils import extract_json_from_response
from ..state import BacktestSubgraphState


REFLECTION_NODE_PROMPT = """你是一个回测分析专家，负责检查回测状态并制定执行计划。

## 你的职责
1. 检查GLOBAL_DATA_STATE中signal和backtest_results的状态
2. 如果回测未完成，分配任务给backtest节点
3. 如果回测已完成，检查回测结果质量，决定是否重跑
4. 如果回测结果合格，进入pnl_plot绘制PNL图

## 当前状态信息
- 数据就绪状态：
  * 信号就绪: {signal_ready}
  * 回测完成: {backtest_completed}
  * 收益就绪: {returns_ready}
  * PNL图就绪: {pnl_plot_ready}

- 执行历史：
{execution_history}

- 错误信息：
{error_messages}

- 重试次数：{retry_count}/{max_retries}

## 可用工具
- python_repl: 用于快速验证GlobalDataState中的数据状态
  使用示例：
  ```python
  # 检查数据是否存在
  from src.state import GLOBAL_DATA_STATE
  snapshot = GLOBAL_DATA_STATE.snapshot()
  print("信号字段:", list(snapshot['signal'].keys()))
  print("回测结果字段:", list(snapshot['backtest_results'].keys()))
  
  # 检查数据形状
  if 'daily_returns' in snapshot['backtest_results']:
      returns = snapshot['backtest_results']['daily_returns']
      print("收益数据形状:", returns.shape)
      print("收益统计:", returns.describe())
  ```

## 用户请求
{user_message}

## 任务类型定义
- **backtest**: 信号就绪但回测未完成，或回测结果不合格需要重跑
- **pnl_plot**: 回测已完成且结果合格，可以绘制PNL图
- **end**: 所有任务完成

## 回测结果质量检查标准
1. daily_returns字段必须存在
2. 收益率序列不能全为0或NaN
3. 收益率的数据点数量应该合理（至少10个有效点）
4. 如果回测失败，检查error_messages中的错误原因

## 输出要求
请分析当前情况，然后以JSON格式输出你的决策：

```json
{{
  "analysis": "你对当前情况的分析（1-2句话）",
  "next_action": "backtest/pnl_plot/end",
  "backtest_params": {{
    "init_cash": 100000,
    "fees": 0.001,
    "slippage": 0.0
  }},
  "need_rerun": true/false
}}
```

## 注意事项
- 优先使用python_repl工具验证数据状态，避免臆断
- 如果回测结果存在但质量不合格，设置need_rerun为true
- 如果连续失败超过max_retries次，应该停止并输出错误信息
- 回测参数可以根据错误信息适当调整
"""


def reflection_node(
    state: BacktestSubgraphState,
    config: RunnableConfig | None = None,
) -> dict:
    """反思节点：检查回测状态并制定执行计划"""
    
    # 创建数据验证工具
    py_tool = PythonAstREPLTool(
        name="python_repl",
        description="用于验证GlobalDataState中的数据状态",
        globals={"GLOBAL_DATA_STATE": GLOBAL_DATA_STATE, "pd": pd}
    )
    
    # 使用ReAct agent进行反思
    agent = create_react_agent(get_llm(), tools=[py_tool])
    
    # 获取用户消息
    user_message = ""
    if state.get('messages'):
        last_msg = state['messages'][-1]
        user_message = last_msg.content if hasattr(last_msg, 'content') else str(last_msg)
    
    # 填充prompt
    execution_history = '\n'.join(state.get('execution_history', [])) if state.get('execution_history') else '暂无执行历史'
    error_messages = '\n'.join(state.get('error_messages', [])) if state.get('error_messages') else '暂无错误'
    
    prompt = REFLECTION_NODE_PROMPT.format(
        signal_ready=state.get('signal_ready', False),
        backtest_completed=state.get('backtest_completed', False),
        returns_ready=state.get('returns_ready', False),
        pnl_plot_ready=state.get('pnl_plot_ready', False),
        execution_history=execution_history,
        error_messages=error_messages,
        retry_count=state.get('retry_count', 0),
        max_retries=state.get('max_retries', 3),
        user_message=user_message
    )
    
    # 执行agent
    result = agent.invoke({"messages": [{"role": "user", "content": prompt}]})
    
    # 提取最后一条消息
    final_message = result['messages'][-1]
    response_content = final_message.content if hasattr(final_message, 'content') else str(final_message)
    
    # 尝试解析JSON响应
    parse_result = extract_json_from_response(response_content)
    messages = [{"role": "user", "content": prompt}]
    
    if not parse_result["success"]:
        # JSON解析失败，生成新prompt让LLM重试
        error_info = parse_result["error"]
        
        # 创建重试prompt
        retry_prompt = f"""前一次JSON解析失败，请重新生成。

错误类型：{error_info['type']}
错误信息：{error_info['message']}

你的原始响应是（部分）：
{error_info['raw_response']}

请重新分析回测状态，并以JSON格式输出你的决策。必须包含以下字段：
- "analysis": 你对当前情况的分析（1-2句话）
- "next_action": backtest/pnl_plot/end
- "backtest_params": 回测参数（如有）
- "need_rerun": 是否需要重跑"""
        
        # 重新调用agent
        retry_result = agent.invoke({"messages": messages + [
            {"role": "assistant", "content": response_content},
            {"role": "user", "content": retry_prompt}
        ]})
        
        # 提取重试后的响应
        retry_message = retry_result['messages'][-1]
        retry_response_content = retry_message.content if hasattr(retry_message, 'content') else str(retry_message)
        
        # 重新解析
        parse_result = extract_json_from_response(retry_response_content)
    
    if parse_result["success"]:
        decision = parse_result["data"]
        
        # 更新state
        updates = {
            'current_task': decision.get('next_action', 'end'),
            'backtest_params': decision.get('backtest_params', {}),
            # 追加执行历史（返回新项，由add reducer自动追加）
            'execution_history': [f"反思: {decision.get('analysis', '完成分析')}"]
        }
        
        # 如果需要重跑，增加retry_count
        if decision.get('need_rerun', False):
            updates['retry_count'] = state.get('retry_count', 0) + 1
        
        return updates
    else:
        # 重试后仍然失败
        error_info = parse_result["error"]
        error_msg = f"反思节点JSON解析失败（重试后）: [{error_info['type']}] {error_info['message']}"
        
        return {
            'error_messages': [error_msg],  # 返回新项，由add reducer自动追加
            'current_task': 'end'
        }
