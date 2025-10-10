"""
信号生成子图的State定义
"""
from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages


class SignalSubgraphState(TypedDict):
    """信号生成子图的专用State"""
    
    # 继承主图的消息流
    messages: Annotated[list, add_messages]
    
    # 任务追踪
    current_task: str  # 当前执行的任务类型：'data_fetch', 'signal_gen', 'validate', 'clarify'
    
    # 数据状态标记
    data_ready: bool  # OHLCV数据是否已准备
    indicators_ready: bool  # 指标数据是否已准备
    signal_ready: bool  # 交易信号是否已生成
    
    # 意图识别结果
    user_intent: dict  # 包含：{type: str, params: dict, needs_clarification: bool}
    
    # 澄清相关
    clarification_needed: str | None  # 需要澄清的问题
    clarification_count: int  # 澄清次数计数
    
    # 执行历史和错误追踪
    execution_history: list[str]  # 记录已执行的步骤
    error_messages: list[str]  # 记录错误信息
    
    # 最大重试次数
    max_retries: int
    retry_count: int
