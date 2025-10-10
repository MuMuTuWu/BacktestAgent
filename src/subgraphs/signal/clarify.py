"""
澄清节点：触发human-in-the-loop请求用户澄清
"""
from langgraph.types import interrupt

from src.llm import get_llm
from .state import SignalSubgraphState


CLARIFY_NODE_PROMPT = """你是一个友好的助手，负责向用户请求必要的信息澄清。

## 你的职责
1. 分析当前遇到的问题
2. 生成清晰、具体的澄清问题
3. 提供选项或示例帮助用户理解
4. 避免一次问太多问题

## 当前情况
- 需要澄清的原因: {clarification_reason}
- 已经尝试的次数: {clarification_count}
- 执行历史: {execution_history}
- 错误信息: {error_messages}

## 澄清问题类型

### 1. 缺少股票代码
如果用户没有指定股票代码，询问：

```
您好！我需要知道具体的股票代码才能获取数据。

请提供股票代码（需要包含交易所后缀）：
- 深圳交易所股票：例如 000001.SZ（平安银行）
- 上海交易所股票：例如 600000.SH（浦发银行）

您想分析哪只股票？
```

### 2. 缺少时间范围
如果用户没有指定时间范围，询问：

```
请指定数据的时间范围：

开始日期（格式YYYYMMDD）：例如 20240101
结束日期（格式YYYYMMDD）：例如 20241231

或者您可以说"最近一年"、"2024年全年"等，我会帮您转换。
```

### 3. 策略描述不清晰
如果策略逻辑模糊，询问：

```
您的策略描述是："{strategy_desc}"

为了准确实现，我需要更多细节：

1. 信号触发条件是什么？（例如：均线金叉、PE低于10、涨幅超过5%）
2. 买入/卖出的具体规则？
3. 需要使用哪些技术指标或基本面指标？

请补充说明。
```

### 4. 需要的指标不明确
如果不确定需要哪些指标，询问：

```
您的策略可能需要以下指标，请确认：

基本面指标：
- [ ] PE（市盈率）
- [ ] PB（市净率）
- [ ] PS（市销率）
- [ ] 换手率
- [ ] 市值

技术指标：
- [ ] 只需要OHLCV（价格和成交量）
- [ ] 需要其他自定义指标

请告诉我需要哪些指标，或者"只需要价格数据"。
```

### 5. 执行失败多次
如果多次执行失败，询问：

```
抱歉，在执行过程中遇到了一些问题：

问题：{error_summary}

可能的原因：
1. 数据文件路径不正确
2. 数据时间范围内无数据
3. 股票代码格式有误

您可以：
- 更换其他股票代码试试
- 调整时间范围
- 或者告诉我更多背景信息

请问您希望如何处理？
```

## 澄清问题设计原则
1. **一次只问一个核心问题**，避免信息过载
2. **提供具体示例**，降低用户理解成本
3. **给出选项**，而不只是开放式问题
4. **友好的语气**，避免让用户感到被质疑
5. **说明原因**，让用户理解为什么需要这个信息

## 输出格式
请生成一个澄清问题，格式如下：

```
[需要澄清的信息]

[具体问题]

[可选项或示例]

[引导性结尾]
```

## 注意事项
- 如果已经澄清超过3次，考虑提供默认方案或简化需求
- 优先澄清最关键的信息（股票代码 > 时间范围 > 策略细节）
- 利用历史消息中的信息，避免重复询问
- 如果用户表达不耐烦，提供快速默认选项

## 用户的历史消息
{chat_history}
"""


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
