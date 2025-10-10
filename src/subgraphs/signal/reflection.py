"""
反思节点：分析用户意图并制定执行计划
"""
import json
import pandas as pd
from langchain_experimental.tools.python.tool import PythonAstREPLTool
from langgraph.prebuilt import create_react_agent

from src.llm import get_llm
from src.state import GLOBAL_DATA_STATE
from .state import SignalSubgraphState


REFLECTION_NODE_PROMPT = """你是一个策略分析专家，负责理解用户意图并制定执行计划。

## 你的职责
1. 分析用户的交易策略需求，识别任务类型
2. 检查当前数据状态，判断是否需要获取数据
3. 评估历史执行情况，决定下一步行动
4. 识别需要澄清的模糊信息

## 当前状态信息
- 数据就绪状态：
  * OHLCV数据: {data_ready}
  * 指标数据: {indicators_ready}
  * 交易信号: {signal_ready}

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
  print("OHLCV字段:", list(snapshot['ohlcv'].keys()))
  print("指标字段:", list(snapshot['indicators'].keys()))
  print("信号字段:", list(snapshot['signal'].keys()))
  
  # 检查数据形状
  if 'close' in snapshot['ohlcv']:
      print("收盘价数据形状:", snapshot['ohlcv']['close'].shape)
  ```

## 用户请求
{user_message}

## 任务类型定义
- **data_fetch**: 用户明确要求获取数据，或策略执行需要但数据缺失
- **signal_gen**: 用户要求生成交易信号，需要基于现有数据进行计算
- **mixed**: 需要先获取数据再生成信号的复合任务
- **unclear**: 用户意图不明确，需要澄清

## 判断是否需要澄清的场景
1. 用户未指定股票代码或代码模糊
2. 用户未指定时间范围（开始/结束日期）
3. 策略描述过于抽象，缺少具体计算逻辑
4. 需要的指标字段不明确
5. 多次执行失败且无法自动修复

## 输出要求
请分析当前情况，然后以JSON格式输出你的决策：

```json
{{
  "analysis": "你对当前情况的分析（1-2句话）",
  "task_type": "data_fetch/signal_gen/mixed/unclear",
  "next_action": "data_fetch/signal_generate/clarify/validate/end",
  "user_intent": {{
    "type": "任务类型",
    "params": {{
      "ts_code": "股票代码（如有）",
      "start_date": "开始日期（如有）",
      "end_date": "结束日期（如有）",
      "strategy_desc": "策略描述（如有）",
      "required_indicators": ["指标列表"]
    }},
    "needs_clarification": true/false
  }},
  "clarification_question": "如果需要澄清，这里写具体问题；否则为null",
  "reasoning": "你的推理过程"
}}
```

## 注意事项
- 如果数据已经就绪且用户要求生成信号，直接进入signal_generate
- 如果出现同样的错误超过2次，应该请求澄清而不是继续重试
- 优先使用python_repl工具验证数据状态，避免臆断
- 任务参数尽可能从用户消息和历史记录中提取
"""


def reflection_node(state: SignalSubgraphState) -> dict:
    """反思节点：分析用户意图并制定执行计划"""
    
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
        data_ready=state.get('data_ready', False),
        indicators_ready=state.get('indicators_ready', False),
        signal_ready=state.get('signal_ready', False),
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
    try:
        # 查找JSON代码块
        if "```json" in response_content:
            json_start = response_content.find("```json") + 7
            json_end = response_content.find("```", json_start)
            json_str = response_content[json_start:json_end].strip()
        elif "{" in response_content and "}" in response_content:
            json_start = response_content.find("{")
            json_end = response_content.rfind("}") + 1
            json_str = response_content[json_start:json_end]
        else:
            raise ValueError("未找到JSON格式的响应")
        
        decision = json.loads(json_str)
        
        # 更新state
        updates = {
            'user_intent': decision.get('user_intent', {}),
            'current_task': decision.get('next_action', 'end'),
        }
        
        # 检查是否需要澄清
        if decision.get('clarification_question') and decision['clarification_question'] != 'null':
            updates['clarification_needed'] = decision['clarification_question']
        
        # 追加执行历史
        if 'execution_history' not in state:
            updates['execution_history'] = []
        else:
            updates['execution_history'] = state['execution_history'].copy()
        updates['execution_history'].append(f"反思: {decision.get('analysis', '完成分析')}")
        
        return updates
        
    except (json.JSONDecodeError, ValueError) as e:
        # 解析失败，返回错误
        error_msg = f"反思节点JSON解析失败: {str(e)}"
        
        return {
            'error_messages': state.get('error_messages', []).copy() + [error_msg],
            'clarification_needed': "抱歉，我在分析您的请求时遇到了问题，请您重新描述一下需求？",
            'current_task': 'clarify'
        }
