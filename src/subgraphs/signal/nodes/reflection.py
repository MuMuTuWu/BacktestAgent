"""
反思节点：分析用户意图并制定执行计划
"""
import pandas as pd
from langchain_core.runnables import RunnableConfig
from langchain_experimental.tools.python.tool import PythonAstREPLTool
from langgraph.prebuilt import create_react_agent

from src.llm import get_llm
from src.state import GLOBAL_DATA_STATE
from src.utils import extract_json_from_response
from ..state import SignalSubgraphState


REFLECTION_SYSTEM_PROMPT = """你是一个策略分析专家，负责理解用户意图并制定执行计划。

## 你的职责
1. 分析用户的交易策略需求
2. 检查当前数据状态，判断是否需要获取数据
3. 评估历史执行情况，决定下一步行动（next_action）
4. 为下一步行动提供清晰的自然语言描述（next_action_desc）

## next_action决策规则

### data_fetch（数据获取）
选择这个action当：
- 用户明确要求获取数据
- 用户要求生成信号但OHLCV数据未就绪（data_ready=False）
- 用户要求生成信号但需要的指标数据未就绪（indicators_ready=False）

### signal_generate（信号生成）
选择这个action当：
- 用户明确要求生成交易信号
- 所需的OHLCV数据和指标数据已经就绪（data_ready=True, indicators_ready=True）
- 用户提供了明确的策略描述

### validate（数据验证）
选择这个action当：
- 数据获取完成，需要验证数据质量
- 信号生成完成，需要验证信号质量
- 用户仅要求数据获取且数据已就绪

### end（结束流程）
选择这个action当：
- 所有任务已完成
- 出现无法自动修复的错误（重试次数超过max_retries）
- 用户意图不明确且无法推断

## next_action_desc的编写指南

next_action_desc是给下游节点的**自然语言指令**，具体化了next_action的执行细节。

### 当next_action="data_fetch"时
next_action_desc应该包含以下信息（以自然语言表达）：
- **股票代码**：明确指定要获取哪只或哪些股票的数据（格式：000001.SZ 或 600000.SH）
- **时间范围**：明确指定开始日期和结束日期（格式：YYYYMMDD，例如20240101）
- **数据类型**：是否需要OHLCV数据（一般总是需要）、是否需要指标数据
- **指标类型**：如果需要指标，列出具体需要的指标（pe, pb, turnover_rate等）

示例：
- "获取000001.SZ从20240101到20240630的日线OHLCV数据，同时获取pe和pb估值指标"
- "获取沪深300指数成分股（HS300）2024年全年的行情数据和周转率、成交量指标"
- "获取600000.SH从20230101到20231231的OHLCV数据"

### 当next_action="signal_generate"时
next_action_desc应该是**完整的策略描述**，包括：
- **策略逻辑**：简明扼要地描述如何生成信号
- **数据需求**：用到哪些数据字段
- **信号定义**：买入/卖出/持有的具体条件

示例：
- "基于5日和20日均线交叉生成信号：当5日均线上穿20日均线时买入（信号值=1），下穿时卖出（信号值=-1），其他时间持有（信号值=0）"
- "基于PE百分位的估值策略：当前PE处于历史低位（百分位<30%）时买入，高位（百分位>70%）时卖出"
- "动量反转策略：基于近20日收益率，选择动量最低的20%股票作为买入信号，最高的20%作为卖出信号"

### 当next_action="validate"时
next_action_desc应该说明验证的目标对象和重点

示例：
- "验证数据完整性：检查OHLCV数据是否有缺失，指标数据的行数是否与行情数据对齐"
- "验证信号质量：检查信号值是否只包含-1、0、1，信号覆盖的时间范围是否完整"

## 输出格式要求

必须以JSON格式输出决策，包含以下字段：
- "analysis"：你对当前情况的简洁分析（1-2句话）
- "next_action"：下一步行动（data_fetch/signal_generate/validate/end）
- "next_action_desc"：具体的自然语言描述（字符串，1-3句话）

JSON示例：
```json
{
  "analysis": "用户要求生成交易信号，但OHLCV数据未就绪。",
  "next_action": "data_fetch",
  "next_action_desc": "获取000001.SZ从20240101到20240630的日线OHLCV数据，同时获取pe和pb指标"
}
```

## 重要注意事项
- **next_action_desc必须是纯字符串**，不要包含JSON或嵌套结构
- next_action_desc中的**日期格式必须是YYYYMMDD**，股票代码必须包含交易所后缀（.SZ或.SH）
- 日期和代码会被下游节点直接使用，请确保格式准确
"""

REFLECTION_USER_PROMPT_TEMPLATE = """## 可用工具
- python_repl: 用于快速验证GLOBAL_DATA_STATE中的数据状态
  使用示例：
  ```python
  from src.state import GLOBAL_DATA_STATE
  snapshot = GLOBAL_DATA_STATE.snapshot()
  print("OHLCV字段:", list(snapshot['ohlcv'].keys()))
  print("指标字段:", list(snapshot['indicators'].keys()))
  print("信号字段:", list(snapshot['signal'].keys()))
  
  # 检查数据形状
  if 'close' in snapshot['ohlcv']:
      print("收盘价数据形状:", snapshot['ohlcv']['close'].shape)
  ```

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

## 用户请求
{user_message}

## 执行指南
- 优先使用python_repl工具验证数据状态，避免臆断
- 如果数据未就绪但用户要求生成信号，next_action应该是data_fetch而不是signal_generate
- 如果出现同样的错误超过2次，next_action应设置为end并在analysis中说明原因
- 任务参数尽可能从用户消息和历史记录中提取

请分析当前情况，并以JSON格式输出你的决策。"""


def reflection_node(
    state: SignalSubgraphState,
    config: RunnableConfig | None = None,
) -> dict:
    """反思节点：使用ReAct模式分析用户意图并制定执行计划"""
    
    # 创建python_repl工具用于验证数据状态
    py_tool = PythonAstREPLTool(
        name="python_repl",
        description="用于验证GLOBAL_DATA_STATE中的数据状态",
        globals={"GLOBAL_DATA_STATE": GLOBAL_DATA_STATE, "pd": pd}
    )
    
    agent = create_react_agent(get_llm(), tools=[py_tool])
    
    # 格式化执行历史和错误信息
    execution_history = "\n".join(state.get('execution_history', [])) if state.get('execution_history') else '暂无历史'
    error_messages = "\n".join(state.get('error_messages', [])) if state.get('error_messages') else '暂无错误'
    
    # 格式化user message
    user_message = REFLECTION_USER_PROMPT_TEMPLATE.format(
        data_ready=state.get('data_ready', False),
        indicators_ready=state.get('indicators_ready', False),
        signal_ready=state.get('signal_ready', False),
        execution_history=execution_history,
        error_messages=error_messages,
        retry_count=state.get('retry_count', 0),
        max_retries=state.get('max_retries', 3),
        user_message=state.get('user_message', '')
    )
    
    # 创建system + user消息对
    messages = [
        {"role": "system", "content": REFLECTION_SYSTEM_PROMPT},
        {"role": "user", "content": user_message}
    ]
    
    # 执行agent
    result = agent.invoke({"messages": messages})
    
    # 提取最后一条消息
    final_message = result['messages'][-1]
    response_content = final_message.content if hasattr(final_message, 'content') else str(final_message)
    
    # 尝试解析JSON响应
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

请重新分析当前情况，并以JSON格式输出你的决策。必须包含以下字段：
- "analysis"：你对当前情况的简洁分析（1-2句话）
- "next_action"：下一步行动（data_fetch/signal_generate/validate/end）
- "next_action_desc"：具体的自然语言描述（字符串，1-3句话）"""
        
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
        
        # 追加执行历史（返回新项，由add reducer自动追加）
        updates = {
            'execution_history': [f"反思: JSON解析失败后重试 - 错误: {error_info['type']}"]
        }
    else:
        updates = {}
    
    if parse_result["success"]:
        decision = parse_result["data"]
        
        # 增加重试计数
        retry_count = state.get('retry_count', 0)
        
        # 更新state
        updates.update({
            'next_action_desc': decision.get('next_action_desc', ''),
            'next_action': decision.get('next_action', 'end'),
            'retry_count': retry_count + 1,
            # 追加执行历史（返回新项，由add reducer自动追加）
            'execution_history': [f"反思: {decision.get('analysis', '完成分析')}"]
        })
        
        return updates
    else:
        # 重试后仍然失败
        error_info = parse_result["error"]
        error_msg = f"反思节点JSON解析失败（重试后）: [{error_info['type']}] {error_info['message']}"
        
        return {
            'error_messages': [error_msg],  # 返回新项，由add reducer自动追加
            'next_action': 'end',
            'execution_history': [f"反思: JSON解析失败，已达重试次数上限"]  # 返回新项，由add reducer自动追加
        }
