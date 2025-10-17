"""
PNL绘制节点：使用quantstats生成HTML报告
"""
from pathlib import Path
from langchain_core.runnables import RunnableConfig

from src.config import configurable as app_config
from src.state import GLOBAL_DATA_STATE
from src.subgraphs.backtest.state import BacktestSubgraphState

def pnl_plot_node(
    state: BacktestSubgraphState,
    config: RunnableConfig | None = None,
) -> dict:
    """PNL绘制节点：使用quantstats生成HTML报告"""
    
    # 获取回测结果
    snapshot = GLOBAL_DATA_STATE.snapshot()
    backtest_results = snapshot.get('backtest_results', {})
    
    updates = {}
    
    # 检查是否有日度收益数据
    if 'daily_returns' not in backtest_results:
        error_msg = "PNL绘制失败：backtest_results中没有daily_returns字段"
        
        updates['error_messages'] = [error_msg]
        updates['pnl_plot_ready'] = False
        updates['execution_history'] = [error_msg]
        
        return updates
    
    returns = backtest_results['daily_returns']
    
    # 确保输出目录存在
    task_dir = Path(app_config['task_dir'])
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
        
        # 追加执行历史（返回新项，由add reducer自动追加）
        updates['execution_history'] = [f"PNL图已生成: {output_path}"]
        
    except Exception as e:
        error_msg = f"PNL绘制失败: {str(e)}"
        
        updates['error_messages'] = [error_msg]
        updates['pnl_plot_ready'] = False
        updates['execution_history'] = [error_msg]
    
    return updates
