# 回测子图 (Backtest Subgraph)

## 概述

回测子图负责对交易信号执行回测，计算策略的日度收益，并使用quantstats生成PNL分析报告。

## 子图结构

```
START → reflection → backtest → reflection → pnl_plot → END
                 ↓                    ↑
                 └──────────────────→ END
```

### 节点说明

1. **reflection (反思节点)**
   - 检查GLOBAL_DATA_STATE中signal和backtest_results的状态
   - 决定是否需要执行回测
   - 检查回测结果质量，决定是否需要重跑
   - 符合质量标准后进入pnl_plot节点

2. **backtest (回测节点)**
   - 使用vectorbt框架执行回测
   - 从GLOBAL_DATA_STATE读取signal和ohlcv数据
   - 计算策略的日度收益
   - 将结果存入GLOBAL_DATA_STATE.backtest_results['daily_returns']
   - 执行完成后返回reflection节点进行检查

3. **pnl_plot (PNL绘制节点)**
   - 使用quantstats库生成HTML报告
   - 从GLOBAL_DATA_STATE读取daily_returns
   - 保存到config['task_dir']/strategy_report.html

## State定义

```python
class BacktestSubgraphState(TypedDict):
    messages: Annotated[list, add_messages]
    current_task: str  # 'reflection'/'backtest'/'pnl_plot'
    signal_ready: bool
    backtest_completed: bool
    returns_ready: bool
    pnl_plot_ready: bool
    backtest_params: dict  # {init_cash, fees, slippage}
    execution_history: list[str]
    error_messages: list[str]
    max_retries: int
    retry_count: int
```

## 使用示例

### 1. 独立使用回测子图

```python
from src.subgraphs.backtest import create_backtest_subgraph, BacktestSubgraphState
from src.state import GLOBAL_DATA_STATE

# 假设signal已存在于GLOBAL_DATA_STATE中
graph = create_backtest_subgraph()

initial_state: BacktestSubgraphState = {
    "messages": [
        {"role": "user", "content": "请对现有信号执行回测"}
    ],
    "current_task": "",
    "signal_ready": True,
    "backtest_completed": False,
    "returns_ready": False,
    "pnl_plot_ready": False,
    "backtest_params": {
        "init_cash": 100000,
        "fees": 0.001,
        "slippage": 0.0
    },
    "execution_history": [],
    "error_messages": [],
    "max_retries": 3,
    "retry_count": 0,
}

result = graph.invoke(initial_state)
```

### 2. 串联signal和backtest子图

```python
from main_with_subgraphs import create_main_graph

main_graph = create_main_graph()

initial_state = {
    "messages": [
        {"role": "user", "content": "获取数据，生成信号，并执行回测"}
    ],
    "signal_completed": False,
    "backtest_completed": False,
}

final_state = main_graph.invoke(initial_state)
```

## 回测流程

1. **reflection节点**检查signal是否就绪
   - 如果signal不存在 → 结束
   - 如果signal存在 → 分配backtest任务

2. **backtest节点**执行回测
   - 使用vectorbt.Portfolio.from_signals()
   - 计算日度收益
   - 存入GLOBAL_DATA_STATE.backtest_results['daily_returns']
   - 返回reflection节点

3. **reflection节点**检查回测结果
   - 检查daily_returns是否存在
   - 验证收益数据质量（非全0、非NaN、有效点数充足）
   - 如果不合格且未超过重试次数 → 重新执行backtest
   - 如果合格 → 进入pnl_plot

4. **pnl_plot节点**生成报告
   - 使用quantstats生成HTML报告
   - 保存到config['task_dir']
   - 结束

## 回测参数

通过`backtest_params`配置：

```python
backtest_params = {
    "init_cash": 100000,   # 初始资金
    "fees": 0.001,         # 手续费率 (0.1%)
    "slippage": 0.0        # 滑点
}
```

## GLOBAL_DATA_STATE扩展

回测子图扩展了GLOBAL_DATA_STATE，新增`backtest_results`字段：

```python
GLOBAL_DATA_STATE.backtest_results = {
    'daily_returns': DataFrame  # 日度收益率
}
```

## 错误处理

- 回测失败时，backtest节点会记录错误信息
- reflection节点检查错误，决定是否重试
- 超过max_retries次数后停止
- 所有错误记录在state.error_messages中

## 依赖

- **vectorbt**: 回测框架
- **quantstats**: PNL报告生成

确保已安装：
```bash
uv add vectorbt quantstats
```

## 测试

参考测试文件：
- `notebook/test_backtest_subgraph.py`: 回测子图单独测试
- `main_with_subgraphs.py`: 完整流程测试

运行测试：
```bash
uv run notebook/test_backtest_subgraph.py
uv run main_with_subgraphs.py
```
