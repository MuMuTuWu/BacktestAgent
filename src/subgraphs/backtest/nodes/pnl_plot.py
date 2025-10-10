"""
PNL绘制节点：使用quantstats生成HTML报告
"""
from pathlib import Path
from config import config
from src.state import GLOBAL_DATA_STATE
from ..state import BacktestSubgraphState


def pnl_plot_node(state: BacktestSubgraphState) -> dict:
    """PNL绘制节点：使用quantstats生成HTML报告"""
    
    # 获取回测结果
    snapshot = GLOBAL_DATA_STATE.snapshot()
    backtest_results = snapshot.get('backtest_results', {})
    
    updates = {}
    
    # 检查是否有日度收益数据
    if 'daily_returns' not in backtest_results:
        error_msg = "PNL绘制失败：backtest_results中没有daily_returns字段"
        
        updates['error_messages'] = state.get('error_messages', []).copy()
        updates['error_messages'].append(error_msg)
        updates['pnl_plot_ready'] = False
        
        if 'execution_history' not in state:
            updates['execution_history'] = []
        else:
            updates['execution_history'] = state['execution_history'].copy()
        updates['execution_history'].append(error_msg)
        
        return updates
    
    returns = backtest_results['daily_returns']
    
    # 确保输出目录存在
    task_dir = Path(config['task_dir'])
    task_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        import quantstats as qs
        
        # 如果returns是DataFrame且有多列，取第一列或求平均
        if hasattr(returns, 'columns') and len(returns.columns) > 1:
            returns_series = returns.mean(axis=1)
        else:
            returns_series = returns.squeeze() if hasattr(returns, 'squeeze') else returns
        
        # 生成HTML报告
        output_path = task_dir / 'strategy_report.html'
        qs.reports.html(returns_series, output=str(output_path))
        
        updates['pnl_plot_ready'] = True
        
        # 追加执行历史
        if 'execution_history' not in state:
            updates['execution_history'] = []
        else:
            updates['execution_history'] = state['execution_history'].copy()
        updates['execution_history'].append(f"PNL图已生成: {output_path}")
        
    except Exception as e:
        error_msg = f"PNL绘制失败: {str(e)}"
        
        updates['error_messages'] = state.get('error_messages', []).copy()
        updates['error_messages'].append(error_msg)
        updates['pnl_plot_ready'] = False
        
        if 'execution_history' not in state:
            updates['execution_history'] = []
        else:
            updates['execution_history'] = state['execution_history'].copy()
        updates['execution_history'].append(error_msg)
    
    return updates
