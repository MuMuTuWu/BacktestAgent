"""
回测子图的State定义
"""
from operator import add
from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages


class BacktestSubgraphState(TypedDict):
    """回测生成子图的专用State"""
    
    # 继承主图的消息流
    messages: Annotated[list, add_messages]
    
    # 任务追踪
    current_task: str  # 当前执行的任务类型：'reflection', 'backtest', 'pnl_plot'
    
    # 数据状态标记
    signal_ready: bool  # 交易信号是否就绪
    backtest_completed: bool  # 回测是否完成
    returns_ready: bool  # 日度收益是否准备好
    pnl_plot_ready: bool  # PNL图是否已绘制
    
    # 回测参数
    backtest_params: dict  # 包含：{init_cash: float, fees: float, slippage: float}
    
    # 执行历史和错误追踪
    execution_history: Annotated[list[str], add]  # 记录已执行的步骤，使用add策略追加
    error_messages: Annotated[list[str], add]  # 记录错误信息，使用add策略追加
    
    # 最大重试次数
    max_retries: int
    retry_count: int
