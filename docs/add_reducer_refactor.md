# execution_history 和 error_messages Add Reducer 重构

## 目的

为 `execution_history` 和 `error_messages` 实现 LangGraph 的 add reducer 策略，使得这两个累积型字段在图的执行过程中能够**自动追加**而不是被替换。

## 问题分析

### 原始问题
在未使用 add reducer 时，所有状态字段都采用**覆盖策略**：
- 节点返回的新值会**完全替换**旧值
- `execution_history` 和 `error_messages` 作为累积类数据，会丢失之前的记录

### 问题示例
```python
# 初始状态
state = {"execution_history": ["Step 1: 反思完成"]}

# data_fetch_node 返回
{"execution_history": ["Step 2: 数据获取完成"]}

# ❌ 结果：丢失了 Step 1
state["execution_history"] = ["Step 2: 数据获取完成"]
```

## 解决方案

### 1. 状态定义更新

**信号子图** (`src/subgraphs/signal/state.py`):
```python
from operator import add

class SignalSubgraphState(TypedDict):
    execution_history: Annotated[list[str], add]  # 使用 add reducer
    error_messages: Annotated[list[str], add]     # 使用 add reducer
```

**回测子图** (`src/subgraphs/backtest/state.py`):
```python
from operator import add

class BacktestSubgraphState(TypedDict):
    execution_history: Annotated[list[str], add]  # 使用 add reducer
    error_messages: Annotated[list[str], add]     # 使用 add reducer
```

### 2. Reducer 工作原理

`from operator import add` 实现列表合并：
- 初始状态：`execution_history = []`
- 节点返回：`{"execution_history": ["新项"]}`
- 合并结果：`[] + ["新项"] = ["新项"]` ✓

当存在多个节点返回时：
```python
# 初始
execution_history = []

# 反思节点返回
{"execution_history": ["反思完成"]}
# → execution_history = [] + ["反思完成"] = ["反思完成"]

# 数据获取节点返回
{"execution_history": ["数据获取完成"]}
# → execution_history = ["反思完成"] + ["数据获取完成"] = ["反思完成", "数据获取完成"]
```

## 受影响的节点

### 信号子图节点

| 节点 | 文件 | 改动 |
|------|------|------|
| reflection | `src/subgraphs/signal/nodes/reflection.py` | 改为返回新列表项 |
| data_fetch | `src/subgraphs/signal/nodes/data_fetch.py` | 改为返回新列表项 |
| signal_generate | `src/subgraphs/signal/nodes/signal_generate.py` | 改为返回新列表项 |
| validation | `src/subgraphs/signal/nodes/validation.py` | 改为返回新列表项 |

### 回测子图节点

| 节点 | 文件 | 改动 |
|------|------|------|
| reflection | `src/subgraphs/backtest/nodes/reflection.py` | 改为返回新列表项 |
| backtest | `src/subgraphs/backtest/nodes/backtest.py` | 改为返回新列表项 |
| pnl_plot | `src/subgraphs/backtest/nodes/pnl_plot.py` | 改为返回新列表项 |

## 代码改动模式

### 原始模式（❌ 不推荐）
```python
# 检查是否已存在该字段
if 'execution_history' not in state:
    updates['execution_history'] = []
else:
    updates['execution_history'] = state['execution_history'].copy()

# 追加新项
updates['execution_history'].append(f"新步骤: {info}")
```

### 新模式（✓ 推荐）
```python
# 直接返回新项（由 add reducer 自动追加）
updates['execution_history'] = [f"新步骤: {info}"]
```

## 优势

1. **代码简洁**：减少了大量的条件判断和列表复制
2. **自动合并**：无需手动管理列表追加逻辑
3. **符合最佳实践**：遵循 LangGraph 的设计模式
4. **完整追踪**：永不丢失任何执行步骤或错误信息
5. **易于维护**：新节点开发时无需关心历史状态

## 使用规范

### 对于开发者

当实现新的节点时，处理 `execution_history` 和 `error_messages`：

```python
def my_node(state: SubgraphState) -> dict:
    updates = {}
    
    try:
        # 执行逻辑
        result = do_something()
        
        # 成功时：返回单项列表
        updates['execution_history'] = ["步骤: 操作成功"]
        
    except Exception as e:
        # 错误时：返回错误列表
        updates['error_messages'] = [f"错误: {str(e)}"]
        updates['execution_history'] = ["步骤: 操作失败"]
    
    return updates
```

### 关键要点

- ✓ 总是返回**新的列表**（包含要追加的项）
- ✗ 不要复制现有列表：`state.get('execution_history', []).copy()`
- ✗ 不要手动追加到列表：`updates['execution_history'].append(...)`
- ✓ 一个节点可以返回多条历史记录：`['步骤1', '步骤2', '步骤3']`

## 测试验证

重构后的代码已通过以下验证：

1. **Linting**：无语法错误
2. **导入**：`from operator import add` 正确导入
3. **类型检查**：`Annotated[list[str], add]` 类型正确
4. **逻辑验证**：所有节点都采用了新模式

## 向后兼容性

此改动是**向后兼容**的，因为：
- 主图中的 `execution_history` 和 `error_messages` 仍然是普通列表
- 状态映射函数（`to_signal_state`, `to_backtest_state`）正确初始化为空列表
- 现有的图流控制逻辑无需改动

## 相关文档

- [LangGraph State Management](https://python.langchain.com/docs/langgraph/concepts/state)
- [Reducer Functions](https://python.langchain.com/docs/langgraph/concepts/state#reducer-functions)
- 项目中的其他 reducer 示例：`messages` 字段使用 `add_messages`
