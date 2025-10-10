# 调试输出来源说明

## 问题
在测试输出中看到这些未格式化的打印：
```
<class 'dict'>
dict_keys(['ohlcv', 'indicators', 'signal'])
[('open', <class 'pandas.core.frame.DataFrame'>, (19, 1)), ...]
```

## 来源分析

这些输出**不是**来自我们编写的代码，而是来自 **LLM 通过 PythonAstREPLTool 动态生成并执行的验证代码**。

### 执行流程

```
┌─────────────────────────────────────────────────────────────┐
│ validation_node() 函数                                       │
├─────────────────────────────────────────────────────────────┤
│ 1. 创建 PythonAstREPLTool                                    │
│    - 提供 GLOBAL_DATA_STATE, pd, np 等全局变量              │
│                                                              │
│ 2. 创建 ReAct Agent (使用 get_light_llm())                  │
│    - Agent 可以调用 python_repl 工具                        │
│                                                              │
│ 3. 发送 VALIDATION_NODE_PROMPT 给 LLM                       │
│    - Prompt 包含验证代码示例                                │
│    - 告诉 LLM 如何检查数据                                  │
│                                                              │
│ 4. LLM 生成验证代码 ← 这里产生输出！                        │
│    例如：                                                    │
│    ```python                                                │
│    snapshot = GLOBAL_DATA_STATE.snapshot()                  │
│    print(type(snapshot))        # 输出: <class 'dict'>      │
│    print(snapshot.keys())        # 输出: dict_keys([...])   │
│    ```                                                      │
│                                                              │
│ 5. PythonAstREPLTool 执行这些代码                           │
│    - print() 语句直接输出到 stdout                          │
│    - 我们无法拦截这些输出                                   │
│                                                              │
│ 6. Agent 返回结果（通常是 JSON 格式的验证报告）             │
└─────────────────────────────────────────────────────────────┘
```

### 为什么会有这些输出？

1. **LLM 的探索行为**
   - LLM 在执行验证任务时，会先探索数据结构
   - 使用 `print(type(...))` 来了解对象类型
   - 使用 `print(...keys())` 来查看可用字段

2. **调试习惯**
   - LLM 模仿人类开发者的调试习惯
   - 在正式验证前先打印一些信息确认数据存在

3. **无法拦截**
   - PythonAstREPLTool 直接执行代码
   - print() 输出直接到 stdout
   - 我们的代码无法拦截或过滤这些输出

## 具体示例

### 第一个输出：`<class 'dict'>`

来自类似这样的 LLM 生成代码：
```python
snapshot = GLOBAL_DATA_STATE.snapshot()
print(type(snapshot))  # <class 'dict'>
```

### 第二个输出：`dict_keys(['ohlcv', 'indicators', 'signal'])`

来自：
```python
print(snapshot.keys())  # dict_keys(['ohlcv', 'indicators', 'signal'])
```

### 第三个输出：列表形式的字段信息

来自：
```python
ohlcv_info = [(k, type(v), v.shape) for k, v in snapshot['ohlcv'].items()]
print(ohlcv_info)
```

## 如何处理？

### 选项1：保持现状（推荐）
- **优点**：
  - 这些输出对调试很有帮助
  - 能看到 LLM 的思考过程
  - 不需要修改代码
- **缺点**：
  - 输出不够美观
  - 混在正常日志中

### 选项2：重定向 stdout
```python
import sys
from io import StringIO

def validation_node(state: SignalSubgraphState) -> dict:
    # 重定向 stdout
    old_stdout = sys.stdout
    sys.stdout = StringIO()
    
    try:
        # ... 执行 agent ...
        result = agent.invoke(...)
    finally:
        # 恢复 stdout
        captured = sys.stdout.getvalue()
        sys.stdout = old_stdout
    
    # 可选：记录捕获的输出用于调试
    # print(f"[DEBUG] Captured output: {captured}")
    
    return updates
```

**缺点**：
- 会隐藏有用的调试信息
- 可能影响其他 print 输出

### 选项3：优化 Prompt
在 VALIDATION_NODE_PROMPT 中明确要求 LLM：
```
## 注意事项
- 执行验证代码时，只在发现问题时才使用 print()
- 不要打印探索性的调试信息
- 最后以 JSON 格式输出验证结果
```

**缺点**：
- LLM 可能不会完全遵循
- 减少了调试信息的可见性

### 选项4：使用 verbose 参数控制
修改 `run_signal_subgraph_stream` 添加一个 `suppress_tool_output` 参数：

```python
def run_signal_subgraph_stream(
    compiled_graph, 
    initial_state: SignalSubgraphState, 
    verbose: bool = True,
    suppress_tool_output: bool = False
):
    if suppress_tool_output:
        # 重定向 stdout
        ...
```

## 建议

**保持现状**，原因：

1. ✅ **有助于理解 Agent 行为**
   - 可以看到 LLM 如何探索数据
   - 便于调试问题

2. ✅ **不影响功能**
   - 这些输出不会影响验证结果
   - 只是额外的信息

3. ✅ **符合开发阶段需求**
   - 当前处于开发和测试阶段
   - 详细的输出有助于发现问题

4. 📌 **生产环境可选择性隐藏**
   - 如果部署到生产，可以添加选项2或选项4
   - 开发时保持详细输出

## 总结

- ❌ 这些输出**不是 bug**
- ✅ 它们是 LLM 执行验证代码时的正常输出
- 🔍 可以通过这些输出了解 LLM 的工作过程
- 🎯 如果需要，可以通过重定向 stdout 来隐藏
