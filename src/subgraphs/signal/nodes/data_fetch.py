"""
数据获取节点：使用ReAct模式获取数据
"""
from langchain_core.runnables import RunnableConfig
from langgraph.prebuilt import create_react_agent

from src.llm import get_light_llm
from src.state import GLOBAL_DATA_STATE
from src.tools.daily_bar import tushare_daily_bar_tool
from src.tools.daily_ind import tushare_daily_basic_tool
from ..state import SignalSubgraphState


DATA_FETCH_SYSTEM_PROMPT = """你是一个数据获取专家，负责从Tushare获取股票数据并存入全局状态。

## 你的职责
1. 根据下面的任务描述调用正确的数据获取工具
2. 确保数据成功存入GLOBAL_DATA_STATE
3. 处理数据获取错误并提供反馈
4. 验证数据的完整性

## 可用工具
1. **tushare_daily_bar**: 获取OHLCV日线行情数据
   - 参数：
     * ts_code: 股票代码，例如 "000001.SZ"
     * start_date: 开始日期，格式"YYYYMMDD"，例如 "20240101"
     * end_date: 结束日期，格式"YYYYMMDD"，例如 "20241231"
   - 输出字段：open, high, low, close, vol
   - 数据存储位置：GLOBAL_DATA_STATE.ohlcv

2. **tushare_daily_basic**: 获取每日指标数据
   - 参数：
     * ts_code: 股票代码
     * start_date: 开始日期
     * end_date: 结束日期
     * fields: 指定字段（可选），例如 "ts_code,trade_date,pe,pb,ps"
   - 可用指标：pe, pe_ttm, pb, ps, ps_ttm, turnover_rate, volume_ratio 等
   - 数据存储位置：GLOBAL_DATA_STATE.indicators

## 执行策略
1. **优先获取OHLCV数据**：几乎所有策略都需要价格数据
2. **按需获取指标数据**：根据任务描述判断需要哪些指标
3. **验证数据质量**：
   - 检查返回的消息是否包含"成功"
   - 确认字段数量和预期一致
   - 如果有错误信息，记录并报告

## 常见指标用途参考
- pe, pe_ttm, pb: 估值策略
- turnover_rate, volume_ratio: 量能策略
- ps, ps_ttm: 成长性策略
- total_mv, circ_mv: 市值策略

## 工作流程
1. 从任务描述中提取股票代码、时间范围和所需指标
2. 先调用 tushare_daily_bar 获取基础行情数据
3. 如果需要指标，再调用 tushare_daily_basic
4. 每次调用后检查返回消息，确认成功
5. 如果失败，分析错误原因（参数错误/数据不存在/文件问题）

## 输出要求
完成数据获取后，用自然语言总结：
- 成功获取了哪些数据
- 数据的时间范围和股票代码
- 如果有错误，说明错误原因和可能的解决方案

## 错误处理指南
- "数据文件不存在"：文件路径问题，提示检查data目录
- "未找到符合条件的数据"：参数可能不正确，建议调整时间范围或股票代码
- "pivot失败"：可能有重复数据，但不影响其他字段，继续执行

## 注意事项
- 日期格式必须是"YYYYMMDD"，例如 "20240901"
- 股票代码必须包含交易所后缀，例如 "000001.SZ" 或 "600000.SH"
- 工具调用失败不要重复尝试同样的参数，应该报告问题"""

DATA_FETCH_USER_PROMPT_TEMPLATE = """## 上下文信息
{last_message_content}

## 当前任务描述
{next_action_desc}"""


def data_fetch_node(
    state: SignalSubgraphState,
    config: RunnableConfig | None = None,
) -> dict:
    """数据获取节点：使用ReAct模式获取数据"""
    
    # 创建数据获取agent
    tools = [tushare_daily_bar_tool, tushare_daily_basic_tool]
    agent = create_react_agent(get_light_llm(), tools=tools)
    
    # 直接从state获取next_action_desc（已是自然语言字符串）
    next_action_desc = state.get('next_action_desc', '未指定任务')

    # 获取最后一个message的content
    messages = state.get('messages', [])
    last_message_content = messages[-1].content if messages else '无上下文信息'

    # 填充user message
    user_message = DATA_FETCH_USER_PROMPT_TEMPLATE.format(
        next_action_desc=next_action_desc,
        last_message_content=last_message_content
    )
    
    # 创建system + user消息对
    messages = [
        {"role": "system", "content": DATA_FETCH_SYSTEM_PROMPT},
        {"role": "user", "content": user_message}
    ]
    
    # 执行agent
    result = agent.invoke({"messages": messages})
    
    # 检查GLOBAL_DATA_STATE并更新state
    snapshot = GLOBAL_DATA_STATE.snapshot()
    
    updates = {
        'data_ready': bool(snapshot.get('ohlcv')),
        'indicators_ready': bool(snapshot.get('indicators')),
    }
    
    # 构建执行历史和错误信息（返回新项，由add reducer自动追加）
    ohlcv_fields = list(snapshot.get('ohlcv', {}).keys())
    indicator_fields = list(snapshot.get('indicators', {}).keys())
    updates['execution_history'] = [
        f"数据获取完成: OHLCV={ohlcv_fields}, Indicators={indicator_fields}"
    ]
    
    # 检查是否有错误（通过检查数据是否为空来判断）
    if not updates['data_ready']:
        updates['error_messages'] = ["数据获取失败：OHLCV数据为空"]
    
    return updates
