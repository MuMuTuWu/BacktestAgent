# Clarify Node 使用指南

## 概述

`clarify_node` 实现了 LangGraph 的 human-in-the-loop 模式，允许在执行过程中暂停并请求用户澄清信息。

## 核心概念

### 1. interrupt() 函数

`interrupt()` 是 LangGraph 提供的核心函数，用于暂停图的执行：

```python
from langgraph.types import interrupt

# 暂停执行并发送数据给用户
result = interrupt({"query": "请提供股票代码"})
user_response = result["data"]  # 从返回值的 "data" 字段获取用户响应
```

### 2. Command 对象

用户通过 `Command` 对象恢复执行并提供数据：

```python
from langgraph.types import Command

# 恢复执行并提供用户响应
command = Command(resume={"data": "000001.SZ"})
graph.stream(command, config)
```

### 3. Checkpointer

必须使用 checkpointer 来支持暂停和恢复：

```python
from langgraph.checkpoint.memory import MemorySaver

checkpointer = MemorySaver()
graph = graph_builder.compile(checkpointer=checkpointer)
```

## 使用流程

### 步骤 1: 启动执行

```python
from langgraph.checkpoint.memory import MemorySaver
from src.subgraphs.signal.graph import create_signal_subgraph

# 创建图并编译
checkpointer = MemorySaver()
signal_graph = create_signal_subgraph()
compiled_graph = signal_graph.compile(checkpointer=checkpointer)

# 配置线程ID
config = {"configurable": {"thread_id": "user-session-1"}}

# 初始状态
initial_state = {
    "messages": [{"role": "user", "content": "帮我生成交易信号"}],
    "current_task": "clarify",
    "clarification_needed": "缺少股票代码",
    "clarification_count": 0,
    # ... 其他字段
}

# 开始执行
for event in compiled_graph.stream(initial_state, config, stream_mode="values"):
    print(event)
```

### 步骤 2: 检查中断状态

当执行到 `clarify_node` 时，图会暂停。检查状态：

```python
# 获取当前状态
snapshot = compiled_graph.get_state(config)

# 查看下一个要执行的节点
print(f"下一个节点: {snapshot.next}")

# 查看中断信息
if hasattr(snapshot, 'tasks') and snapshot.tasks:
    for task in snapshot.tasks:
        if hasattr(task, 'interrupts') and task.interrupts:
            for interrupt_info in task.interrupts:
                # 获取澄清问题
                query = interrupt_info.value.get('query')
                print(f"澄清问题: {query}")
                
                # 获取上下文信息
                reason = interrupt_info.value.get('clarification_reason')
                count = interrupt_info.value.get('clarification_count')
                print(f"原因: {reason}, 次数: {count}")
```

### 步骤 3: 恢复执行

使用 Python 的 `input()` 获取用户响应，然后使用 `Command` 恢复：

```python
from langgraph.types import Command

# 使用 input() 获取用户响应
user_response = input("请输入您的响应: ").strip()

if not user_response:
    print("输入为空，终止执行")
else:
    # 创建 Command 对象
    # 注意：必须使用 {"data": ...} 格式
    resume_command = Command(resume={"data": user_response})
    
    # 恢复执行
    for event in compiled_graph.stream(resume_command, config, stream_mode="values"):
        print(event)
```

### 步骤 4: 验证结果

```python
# 再次获取状态
final_snapshot = compiled_graph.get_state(config)

# 检查澄清是否成功
print(f"澄清次数: {final_snapshot.values.get('clarification_count')}")
print(f"是否还需要澄清: {final_snapshot.values.get('clarification_needed')}")

# 查看更新后的消息
messages = final_snapshot.values.get('messages', [])
for msg in messages:
    print(f"{msg.get('role')}: {msg.get('content')}")
```

## 完整示例（使用 input()）

```python
from langgraph.types import Command
from src.graph import (
    build_initial_state,
    build_run_config,
    create_main_graph,
)


def run_with_clarification():
    """演示完整的 human-in-the-loop 流程，使用 input() 获取用户输入"""
    
    # 1. 创建图（自动包含 checkpointer）
    graph = create_main_graph()
    
    # 2. 配置
    thread_id = "demo-session"
    config = build_run_config(thread_id=thread_id)
    
    # 3. 初始查询（缺少信息会触发澄清）
    query = "生成交易信号"
    initial_state = build_initial_state(query)
    
    print(f"查询: {query}")
    print(f"线程ID: {thread_id}\n")
    
    # 4. 执行循环，处理可能的多次中断
    while True:
        try:
            # 尝试执行
            final_state = graph.invoke(initial_state, config=config)
            
            # 执行完成
            print("\n✅ 执行完成")
            print(f"信号生成: {'✅' if final_state.get('signal_ready') else '❌'}")
            print(f"回测完成: {'✅' if final_state.get('backtest_ready') else '❌'}")
            break
            
        except Exception as e:
            # 检查是否是 interrupt
            if "interrupt" not in str(e).lower():
                raise
            
            # 执行被中断
            print("\n⏸️  执行已暂停\n")
            
            # 获取中断信息
            snapshot = graph.get_state(config)
            
            # 打印澄清问题
            if hasattr(snapshot, 'tasks') and snapshot.tasks:
                for task in snapshot.tasks:
                    if hasattr(task, 'interrupts') and task.interrupts:
                        for interrupt_info in task.interrupts:
                            value = interrupt_info.value
                            if isinstance(value, dict) and 'query' in value:
                                print("📋 澄清问题：")
                                print(value['query'])
                                print()
            
            # 使用 input() 获取用户响应
            user_response = input("请输入您的响应: ").strip()
            
            if not user_response:
                print("输入为空，终止执行")
                break
            
            print(f"\n收到响应: {user_response}")
            print("恢复执行...\n")
            
            # 创建 Command 恢复执行
            initial_state = Command(resume={"data": user_response})


if __name__ == "__main__":
    run_with_clarification()
```

## 注意事项

### 1. 数据格式

- **发送给用户**: `interrupt({"query": question, ...})`
- **用户响应**: `Command(resume={"data": response})`
- **获取响应**: `result = interrupt(...); user_data = result["data"]`

### 2. Checkpointer 必需

没有 checkpointer，图无法暂停和恢复：

```python
# ❌ 错误：没有 checkpointer
graph = graph_builder.compile()

# ✅ 正确：使用 checkpointer
from langgraph.checkpoint.memory import MemorySaver
graph = graph_builder.compile(checkpointer=MemorySaver())
```

### 3. 线程 ID

每个会话需要唯一的线程 ID：

```python
# 为每个用户会话使用不同的 thread_id
config = {"configurable": {"thread_id": f"user-{user_id}-session-{session_id}"}}
```

### 4. 多次澄清

如果需要多次澄清，每次都会增加 `clarification_count`：

```python
# 第一次澄清
clarification_count = 0  # -> 1

# 第二次澄清
clarification_count = 1  # -> 2

# 建议设置上限
if state.get('clarification_count', 0) >= 3:
    # 提供默认方案或终止
    pass
```

### 5. 错误处理

```python
try:
    for event in graph.stream(initial_state, config):
        process_event(event)
except Exception as e:
    # 中断是正常行为，不是错误
    if "interrupt" in str(e).lower():
        print("执行已暂停，等待用户输入")
    else:
        raise
```

## 与主图集成

在主图中使用 signal subgraph 时，中断会传播到主图：

```python
# main.py
from src.graph import create_main_graph

main_graph = create_main_graph()
config = {"configurable": {"thread_id": "main-session"}}

# 执行主图
for event in main_graph.stream({"messages": [...]}, config):
    print(event)

# 如果 signal subgraph 中断，主图也会中断
# 使用相同的 config 恢复
resume_cmd = Command(resume={"data": user_response})
for event in main_graph.stream(resume_cmd, config):
    print(event)
```

## 调试技巧

### 查看完整状态

```python
snapshot = graph.get_state(config)

# 查看所有状态值
print("State values:", snapshot.values)

# 查看下一步
print("Next nodes:", snapshot.next)

# 查看任务和中断
if hasattr(snapshot, 'tasks'):
    for task in snapshot.tasks:
        print(f"Task: {task.name}")
        if hasattr(task, 'interrupts'):
            print(f"Interrupts: {task.interrupts}")
```

### 日志记录

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# 在 clarify_node 中
logger.info(f"触发中断，原因: {state.get('clarification_needed')}")
logger.debug(f"中断 payload: {interrupt_payload}")
```

## 参考资料

- [LangGraph Human-in-the-Loop Tutorial](https://langchain-ai.github.io/langgraph/tutorials/get-started/4-human-in-the-loop/)
- [LangGraph Persistence](https://langchain-ai.github.io/langgraph/concepts/persistence/)
- [LangGraph Command API](https://langchain-ai.github.io/langgraph/concepts/low_level/#command)

