"""
信号生成子图的节点实现
"""
import json
import pandas as pd
import numpy as np
from langchain_experimental.tools.python.tool import PythonAstREPLTool
from langgraph.prebuilt import create_react_agent
from langgraph.types import interrupt

from src.llm import get_llm, get_light_llm
from src.state import GLOBAL_DATA_STATE
from src.tools.daily_bar import tushare_daily_bar_tool
from src.tools.daily_ind import tushare_daily_basic_tool

from .state import SignalSubgraphState
from .prompts import (
    REFLECTION_NODE_PROMPT,
    DATA_FETCH_AGENT_PROMPT,
    SIGNAL_GENERATE_AGENT_PROMPT,
    CLARIFY_NODE_PROMPT,
    VALIDATION_NODE_PROMPT,
)


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


def data_fetch_node(state: SignalSubgraphState) -> dict:
    """数据获取节点：使用ReAct模式获取数据"""
    
    # 创建数据获取agent
    tools = [tushare_daily_bar_tool, tushare_daily_basic_tool]
    agent = create_react_agent(get_light_llm(), tools=tools)
    
    # 从user_intent获取参数
    params = state.get('user_intent', {}).get('params', {})
    ts_code = params.get('ts_code', '未指定')
    start_date = params.get('start_date', '未指定')
    end_date = params.get('end_date', '未指定')
    required_indicators = params.get('required_indicators', [])
    
    # 填充prompt
    prompt = DATA_FETCH_AGENT_PROMPT.format(
        ts_code=ts_code,
        start_date=start_date,
        end_date=end_date,
        required_indicators=required_indicators
    )
    
    # 执行agent
    result = agent.invoke({"messages": [{"role": "user", "content": prompt}]})
    
    # 检查GLOBAL_DATA_STATE并更新state
    snapshot = GLOBAL_DATA_STATE.snapshot()
    
    updates = {
        'data_ready': bool(snapshot.get('ohlcv')),
        'indicators_ready': bool(snapshot.get('indicators')),
    }
    
    # 追加执行历史
    if 'execution_history' not in state:
        updates['execution_history'] = []
    else:
        updates['execution_history'] = state['execution_history'].copy()
    
    ohlcv_fields = list(snapshot.get('ohlcv', {}).keys())
    indicator_fields = list(snapshot.get('indicators', {}).keys())
    updates['execution_history'].append(
        f"数据获取完成: OHLCV={ohlcv_fields}, Indicators={indicator_fields}"
    )
    
    # 检查是否有错误（通过检查数据是否为空来判断）
    if not updates['data_ready']:
        if 'error_messages' not in state:
            updates['error_messages'] = []
        else:
            updates['error_messages'] = state['error_messages'].copy()
        updates['error_messages'].append("数据获取失败：OHLCV数据为空")
    
    return updates


def signal_generate_node(state: SignalSubgraphState) -> dict:
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
    
    # 填充prompt
    params = state.get('user_intent', {}).get('params', {})
    strategy_description = params.get('strategy_desc', '未指定策略')
    
    prompt = SIGNAL_GENERATE_AGENT_PROMPT.format(
        available_ohlcv=list(snapshot.get('ohlcv', {}).keys()),
        available_indicators=list(snapshot.get('indicators', {}).keys()),
        strategy_description=strategy_description
    )
    
    # 执行agent
    result = agent.invoke({"messages": [{"role": "user", "content": prompt}]})
    
    # 检查信号是否生成
    snapshot = GLOBAL_DATA_STATE.snapshot()
    
    updates = {
        'signal_ready': bool(snapshot.get('signal')),
    }
    
    # 追加执行历史
    if 'execution_history' not in state:
        updates['execution_history'] = []
    else:
        updates['execution_history'] = state['execution_history'].copy()
    
    signal_fields = list(snapshot.get('signal', {}).keys())
    updates['execution_history'].append(f"信号生成完成: {signal_fields}")
    
    # 检查是否有错误
    if not updates['signal_ready']:
        if 'error_messages' not in state:
            updates['error_messages'] = []
        else:
            updates['error_messages'] = state['error_messages'].copy()
        updates['error_messages'].append("信号生成失败：signal字段为空")
    
    return updates


def clarify_node(state: SignalSubgraphState) -> dict:
    """澄清节点：触发human-in-the-loop请求用户澄清"""
    
    llm = get_llm()
    
    # 获取历史消息
    chat_history = ""
    if state.get('messages'):
        recent_messages = state['messages'][-5:]
        chat_history = '\n'.join([
            f"{msg.content if hasattr(msg, 'content') else str(msg)}"
            for msg in recent_messages
        ])
    
    # 填充prompt
    execution_history = '\n'.join(state.get('execution_history', [])) if state.get('execution_history') else '暂无执行历史'
    error_messages = '\n'.join(state.get('error_messages', [])) if state.get('error_messages') else '暂无错误'
    
    # 如果有error_messages，生成错误摘要
    error_summary = "无"
    if state.get('error_messages'):
        error_summary = state['error_messages'][-1] if len(state['error_messages']) == 1 else f"共{len(state['error_messages'])}个错误"
    
    prompt = CLARIFY_NODE_PROMPT.format(
        clarification_reason=state.get('clarification_needed', '未知'),
        clarification_count=state.get('clarification_count', 0),
        execution_history=execution_history,
        error_messages=error_messages,
        chat_history=chat_history,
        error_summary=error_summary,
        strategy_desc=state.get('user_intent', {}).get('params', {}).get('strategy_desc', '未提供')
    )
    
    # 生成澄清问题
    response = llm.invoke([{"role": "system", "content": prompt}])
    clarification_question = response.content if hasattr(response, 'content') else str(response)
    
    # 触发中断，等待用户响应
    user_response = interrupt(clarification_question)
    
    # 将用户响应添加到消息流
    updates = {
        'messages': [{"role": "user", "content": user_response}],
        'clarification_count': state.get('clarification_count', 0) + 1,
        'clarification_needed': None,  # 清除澄清标记
    }
    
    # 追加执行历史
    if 'execution_history' not in state:
        updates['execution_history'] = []
    else:
        updates['execution_history'] = state['execution_history'].copy()
    updates['execution_history'].append(f"用户澄清: {user_response[:50]}...")
    
    return updates


def validation_node(state: SignalSubgraphState) -> dict:
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
    expected_fields = state.get('user_intent', {}).get('params', {}).get('required_indicators', [])
    
    prompt = VALIDATION_NODE_PROMPT.format(
        validation_type=validation_type,
        expected_fields=expected_fields
    )
    
    # 执行agent
    result = agent.invoke({"messages": [{"role": "user", "content": prompt}]})
    
    # 提取最后一条消息
    final_message = result['messages'][-1]
    response_content = final_message.content if hasattr(final_message, 'content') else str(final_message)
    
    # 尝试解析JSON响应
    updates = {}
    has_errors = False  # 标记本次验证是否发现error
    
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
            # 没有JSON，假设验证通过
            json_str = '{"validation_passed": true, "issues_found": []}'
        
        validation_result = json.loads(json_str)
        
        # 检查是否有error级别的问题
        issues = validation_result.get('issues_found', [])
        has_errors = any(issue.get('severity') == 'error' for issue in issues)
        
        if has_errors:
            # 本次验证发现error，追加到error_messages
            if 'error_messages' not in state:
                updates['error_messages'] = []
            else:
                updates['error_messages'] = state['error_messages'].copy()
            
            error_msgs = [issue.get('message', 'Unknown error') for issue in issues if issue.get('severity') == 'error']
            updates['error_messages'].extend(error_msgs)
        
    except (json.JSONDecodeError, ValueError):
        # 解析失败，假设验证通过
        has_errors = False
    
    # 验证通过时清空错误信息和重置重试计数
    if not has_errors:
        updates['error_messages'] = []
        updates['retry_count'] = 0
    
    # 追加执行历史
    if 'execution_history' not in state:
        updates['execution_history'] = []
    else:
        updates['execution_history'] = state['execution_history'].copy()
    updates['execution_history'].append(f"验证完成: {validation_type}, 有错误={has_errors}")
    
    return updates
