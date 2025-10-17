"""
信号生成子图的State定义
"""
from operator import add
from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages


class SignalSubgraphState(TypedDict):
    """信号生成子图的专用State"""
    
    # 继承主图的消息流
    messages: Annotated[list, add_messages]
    
    # 任务追踪
    next_action: str  # 下一步行动：'data_fetch', 'signal_generate', 'validate', 'end'

    # 下一步行动的详细描述
    next_action_desc: str  # 自然语言描述，包含具体的任务参数或策略逻辑
    
    # 数据状态标记
    data_ready: bool  # OHLCV数据是否已准备
    indicators_ready: bool  # 指标数据是否已准备
    signal_ready: bool  # 交易信号是否已生成
    
    # 执行历史和错误追踪
    execution_history: Annotated[list[str], add]  # 记录已执行的步骤，使用add策略追加
    error_messages: Annotated[list[str], add]  # 记录错误信息，使用add策略追加
    
    # 最大重试次数
    max_retries: int
    retry_count: int
