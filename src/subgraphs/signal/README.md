# 信号生成子图 (Signal Subgraph)

## 概述

信号生成子图是一个完整的ReAct模式子图，用于从数据获取到交易信号生成的完整流程。

## 功能特性

- ✅ **数据获取**：自动调用Tushare工具获取OHLCV和指标数据
- ✅ **信号生成**：基于用户策略描述生成交易信号
- ✅ **反思路由**：智能识别用户意图并调度任务
- ✅ **用户澄清**：信息不足时触发human-in-the-loop
- ✅ **数据验证**：确保数据和信号的质量

## 快速开始

### 1. 导入子图

```python
from src.subgraphs.signal import create_signal_subgraph, SignalSubgraphState
```

### 2. 创建子图实例

```python
graph = create_signal_subgraph()
```

### 3. 初始化State

```python
initial_state: SignalSubgraphState = {
    "messages": [
        {"role": "user", "content": "请获取000001.SZ从20240901到20240930的数据"}
    ],
    "current_task": "",
    "data_ready": False,
    "indicators_ready": False,
    "signal_ready": False,
    "user_intent": {},
    "clarification_needed": None,
    "clarification_count": 0,
    "execution_history": [],
    "error_messages": [],
    "max_retries": 3,
    "retry_count": 0,
}
```

### 4. 执行子图

```python
result = graph.invoke(initial_state)

# 查看执行历史
print("执行历史:")
for history in result['execution_history']:
    print(f"  - {history}")

# 检查数据状态
print(f"数据就绪: {result['data_ready']}")
print(f"信号就绪: {result['signal_ready']}")
```

## 使用示例

### 示例1: 数据获取

```python
from src.subgraphs.signal import create_signal_subgraph, SignalSubgraphState
from src.state import GLOBAL_DATA_STATE

graph = create_signal_subgraph()

initial_state: SignalSubgraphState = {
    "messages": [
        {"role": "user", "content": "请获取股票000001.SZ从20240901到20240930的数据"}
    ],
    "current_task": "",
    "data_ready": False,
    "indicators_ready": False,
    "signal_ready": False,
    "user_intent": {},
    "clarification_needed": None,
    "clarification_count": 0,
    "execution_history": [],
    "error_messages": [],
    "max_retries": 3,
    "retry_count": 0,
}

result = graph.invoke(initial_state)

# 检查GLOBAL_DATA_STATE
snapshot = GLOBAL_DATA_STATE.snapshot()
print(f"OHLCV字段: {list(snapshot['ohlcv'].keys())}")
print(f"指标字段: {list(snapshot['indicators'].keys())}")
```

### 示例2: 信号生成

```python
from src.subgraphs.signal import create_signal_subgraph, SignalSubgraphState
from src.state import GLOBAL_DATA_STATE

graph = create_signal_subgraph()

initial_state: SignalSubgraphState = {
    "messages": [
        {"role": "user", "content": "请获取000001.SZ从20240901到20240930的数据，然后生成5日和20日均线交叉策略信号"}
    ],
    "current_task": "",
    "data_ready": False,
    "indicators_ready": False,
    "signal_ready": False,
    "user_intent": {},
    "clarification_needed": None,
    "clarification_count": 0,
    "execution_history": [],
    "error_messages": [],
    "max_retries": 3,
    "retry_count": 0,
}

result = graph.invoke(initial_state)

# 检查生成的信号
snapshot = GLOBAL_DATA_STATE.snapshot()
for signal_name, signal_df in snapshot['signal'].items():
    print(f"\n信号 '{signal_name}':")
    print(f"  形状: {signal_df.shape}")
    print(f"  买入信号数: {(signal_df == 1).sum().sum()}")
    print(f"  卖出信号数: {(signal_df == -1).sum().sum()}")
```

## 子图结构

```
START → Reflection → Data Fetch / Signal Generate / Clarify / Validate → END
             ↓              ↓              ↓              ↓
         (循环反馈)    (循环反馈)    (循环反馈)    (循环反馈)
```

### 节点说明

1. **Reflection Node (反思节点)**：
   - 分析用户意图
   - 决策下一步行动
   - 使用PythonAstREPLTool验证数据状态

2. **Data Fetch Node (数据获取节点)**：
   - 调用Tushare工具获取数据
   - 存储数据到GLOBAL_DATA_STATE

3. **Signal Generate Node (信号生成节点)**：
   - 根据策略描述生成信号
   - 使用PythonAstREPLTool执行计算

4. **Clarify Node (澄清节点)**：
   - 触发human-in-the-loop
   - 请求用户补充信息

5. **Validation Node (验证节点)**：
   - 检查数据和信号质量
   - 识别潜在问题

## State字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `messages` | `list` | 消息流 |
| `current_task` | `str` | 当前任务类型 |
| `data_ready` | `bool` | OHLCV数据是否就绪 |
| `indicators_ready` | `bool` | 指标数据是否就绪 |
| `signal_ready` | `bool` | 交易信号是否就绪 |
| `user_intent` | `dict` | 用户意图和参数 |
| `clarification_needed` | `str \| None` | 需要澄清的问题 |
| `clarification_count` | `int` | 澄清次数 |
| `execution_history` | `list[str]` | 执行历史 |
| `error_messages` | `list[str]` | 错误信息 |
| `max_retries` | `int` | 最大重试次数 |
| `retry_count` | `int` | 当前重试次数 |

## 测试

运行测试示例：

```bash
cd /Users/wuye/Desktop/gjzq_intern/project_code/0926/BacktestAgent
source .venv/bin/activate
uv run notebook/test_signal_subgraph.py
```

## 注意事项

1. **数据存储**：所有数据存储在`GLOBAL_DATA_STATE`中，子图State只存储元数据
2. **Human-in-the-Loop**：澄清节点使用`interrupt()`，需要在支持interrupt的环境中运行
3. **错误处理**：子图会自动重试，超过最大重试次数后请求用户澄清
4. **并发安全**：`GLOBAL_DATA_STATE`使用锁保证线程安全

## 文件结构

```
src/subgraphs/signal/
├── __init__.py          # 模块导出
├── state.py             # State定义
├── reflection.py        # 反思节点（包含节点实现和Prompt）
├── data_fetch.py        # 数据获取节点（包含节点实现和Prompt）
├── signal_generate.py   # 信号生成节点（包含节点实现和Prompt）
├── clarify.py           # 澄清节点（包含节点实现和Prompt）
├── validation.py        # 验证节点（包含节点实现和Prompt）
├── routes.py            # 路由函数
├── graph.py             # 子图构建
└── README.md            # 使用说明
```

## 相关文档

- [方案设计文档](../../../docs/signal_subgraph_design.md)
- [项目README](../../../README.md)
