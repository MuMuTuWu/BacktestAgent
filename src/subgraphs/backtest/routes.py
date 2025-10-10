"""
回测子图的路由函数
"""
from langgraph.graph import END
from .state import BacktestSubgraphState


def route_from_reflection(state: BacktestSubgraphState) -> str:
    """从反思节点出发的路由决策"""
    
    # 检查是否超过最大重试次数
    if state.get('retry_count', 0) >= state.get('max_retries', 3):
        # 超过重试次数，如果回测已完成就绘图，否则结束
        if state.get('backtest_completed') and state.get('returns_ready'):
            return 'pnl_plot'
        return END
    
    # 根据current_task决策
    current_task = state.get('current_task', 'end')
    
    if current_task == 'backtest':
        return 'backtest'
    
    if current_task == 'pnl_plot':
        # 确保回测已完成
        if state.get('backtest_completed') and state.get('returns_ready'):
            return 'pnl_plot'
        # 如果回测未完成，先回测
        return 'backtest'
    
    if current_task == 'end':
        return END
    
    # 默认：检查状态决定
    if not state.get('signal_ready'):
        return END  # 信号未就绪，无法回测
    
    if not state.get('backtest_completed'):
        return 'backtest'  # 回测未完成，执行回测
    
    if state.get('backtest_completed') and not state.get('pnl_plot_ready'):
        return 'pnl_plot'  # 回测完成，绘制PNL
    
    return END  # 所有任务完成


def route_after_backtest(state: BacktestSubgraphState) -> str:
    """回测节点后的路由：总是返回reflection进行检查"""
    # 修改：回测后总是回到reflection节点进行检查
    return 'reflection'


def route_after_pnl_plot(state: BacktestSubgraphState) -> str:
    """PNL绘制节点后的路由"""
    # PNL绘制后结束
    return END
