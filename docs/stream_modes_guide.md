# LangGraph Stream Modes 使用指南

## 概述

`run_signal_subgraph_stream` 函数现在支持 LangGraph 的多种流式输出模式，并使用 `rich` 库提供美化的终端输出。

## Stream Modes

### 1. `updates` 模式（推荐，默认）

**特点**：
- 仅显示每步的状态变化
- 输出简洁清晰
- 适合日常调试和监控

**使用示例**：
```python
from src.subgraphs.signal import create_signal_subgraph, run_signal_subgraph_stream, SignalSubgraphState

graph = create_signal_subgraph()
initial_state = {...}

# 使用 updates 模式（默认）
final_state = run_signal_subgraph_stream(
    compiled_graph=graph,
    initial_state=initial_state,
    verbose=True,
    stream_mode="updates"  # 可省略，默认值
)
```

**输出示例**：
```
============================================================
                    🚀 开始流式执行信号生成子图                    
============================================================

╭─────────────── 🔹 节点: reflection (步骤 1) ───────────────╮
│ 📋 当前任务: 分析用户意图                                  │
│ ⚡ 最新执行: 已识别数据获取需求                            │
╰────────────────────────────────────────────────────────────╯

╭──────────────── 🔹 节点: data_fetch (步骤 2) ─────────────╮
│ 📋 当前任务: 获取 OHLCV 数据                              │
│ 📊 数据状态: OHLCV=✓, 指标=✗, 信号=✗                      │
│ ⚡ 最新执行: 成功获取000001.SZ数据                         │
╰────────────────────────────────────────────────────────────╯

============================================================
                        ✅ 子图执行完成                        
============================================================

            📈 执行摘要             
╔══════════════════════╤═══════════╗
║ OHLCV数据            │ ✅ 就绪   ║
║ 指标数据             │ ❌ 未就绪 ║
║ 交易信号             │ ❌ 未就绪 ║
║ 执行步骤数           │ 3         ║
║ 错误次数             │ 0         ║
║ 重试次数             │ 0         ║
╚══════════════════════╧═══════════╝
```

### 2. `values` 模式

**特点**：
- 每步输出完整状态
- 信息量大，适合深度调试
- 可以看到所有状态字段的变化

**使用示例**：
```python
final_state = run_signal_subgraph_stream(
    compiled_graph=graph,
    initial_state=initial_state,
    verbose=True,
    stream_mode="values"  # 完整状态模式
)
```

**输出示例**：
```
============================================================
                    🚀 开始流式执行信号生成子图                    
============================================================

📦 完整状态 (步骤 1)
┌──────────────────────┬─────────────────────┐
│ 字段                 │ 值                  │
├──────────────────────┼─────────────────────┤
│ current_task         │ 分析用户意图        │
│ data_ready           │ ✗                   │
│ indicators_ready     │ ✗                   │
│ signal_ready         │ ✗                   │
│ retry_count          │ 0                   │
│ max_retries          │ 3                   │
└──────────────────────┴─────────────────────┘
```

### 3. `debug` 模式

**特点**：
- 输出最详细的调试信息
- 包含节点执行元数据
- 适合排查复杂问题

**使用示例**：
```python
final_state = run_signal_subgraph_stream(
    compiled_graph=graph,
    initial_state=initial_state,
    verbose=True,
    stream_mode="debug"  # 调试模式
)
```

**输出示例**：
```
============================================================
                    🚀 开始流式执行信号生成子图                    
============================================================

📊 调试信息 (步骤 1)
{
    'type': 'task',
    'timestamp': '2024-01-01T10:00:00',
    'task': {'id': 'xxx', 'name': 'reflection', 'path': ['reflection']},
    'payload': {...},
    'metadata': {...}
}
```

## 静默模式

如果不需要任何输出，可以设置 `verbose=False`：

```python
final_state = run_signal_subgraph_stream(
    compiled_graph=graph,
    initial_state=initial_state,
    verbose=False  # 不打印任何信息
)
```

## 美化输出特性

使用 `rich` 库提供的美化输出包括：

1. **面板（Panel）**：节点执行信息以带边框的面板形式展示
2. **表格（Table）**：执行摘要以表格形式清晰展示
3. **颜色和样式**：不同类型的信息使用不同颜色
   - 青色：标题和字段名
   - 白色：正常内容
   - 红色：错误信息
   - 黄色：警告和澄清需求
   - 绿色：成功信息
4. **图标**：使用 emoji 增强可读性
   - 🚀 开始执行
   - ✅ 成功完成
   - ❌ 执行失败
   - 🔹 节点标识
   - 📋 任务信息
   - 📊 数据状态
   - ⚡ 执行历史
   - ⚠️  错误警告
   - ❓ 需要澄清

## 性能考虑

- `updates` 模式性能最好，输出量适中
- `values` 模式输出量大，可能影响终端性能
- `debug` 模式输出量最大，仅在必要时使用
- `verbose=False` 关闭输出可获得最佳性能

## 完整示例

参见 `notebook/example_stream_usage.py` 获取完整的使用示例。
