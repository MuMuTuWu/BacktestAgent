# Checkpointer 架构设计

## 概述

本项目采用 **主图统一管理 Checkpointer** 的架构，确保 human-in-the-loop 功能在整个系统中正常工作。

## 架构原则

### 1. Checkpointer 在主图上设置

```python
# src/graph.py
def create_main_graph(checkpointer=None):
    builder = StateGraph(MainGraphState)
    
    # ... 添加节点和边 ...
    
    # 在主图编译时设置 checkpointer
    if checkpointer is None:
        checkpointer = MemorySaver()  # 默认使用内存存储
    
    return builder.compile(checkpointer=checkpointer)
```

**为什么？**
- ✅ 子图自动继承主图的 checkpointer
- ✅ 统一的状态持久化管理
- ✅ 支持跨子图的 interrupt 和恢复
- ✅ 简化配置，避免重复设置

### 2. 子图不单独设置 Checkpointer

```python
# src/subgraphs/signal/graph.py
def build_signal_graph():
    builder = StateGraph(SignalSubgraphState)
    
    # ... 添加节点和边 ...
    
    # ❌ 不要在这里设置 checkpointer
    return builder.compile()  # 不传 checkpointer 参数
```

**为什么？**
- ✅ 避免 checkpointer 冲突
- ✅ 保持子图的可复用性
- ✅ 子图会自动使用主图的 checkpointer

### 3. Thread ID 在运行时配置

```python
# main.py
def main(query: str, thread_id: str = "main-session"):
    graph = create_main_graph()
    run_config = build_run_config(thread_id=thread_id)
    
    # thread_id 通过 config 传递，不硬编码
    graph.invoke(initial_state, config=run_config)
```

**为什么？**
- ✅ 支持多用户并发
- ✅ 每个会话独立持久化
- ✅ 便于会话管理和恢复

## 工作流程

### 正常执行流程

```mermaid
graph TD
    A[创建主图 + Checkpointer] --> B[设置 thread_id]
    B --> C[执行主图]
    C --> D[进入 Signal 子图]
    D --> E[执行节点]
    E --> F[完成]
```

### 中断和恢复流程

```mermaid
graph TD
    A[执行到 clarify_node] --> B[调用 interrupt]
    B --> C[保存状态到 Checkpointer]
    C --> D[暂停执行]
    D --> E[用户提供响应]
    E --> F[创建 Command 对象]
    F --> G[从 Checkpointer 加载状态]
    G --> H[恢复执行]
    H --> I[继续后续节点]
```

## 代码示例

### 基本使用

```python
from src.graph import create_main_graph, build_initial_state, build_run_config

# 1. 创建图（自动包含 MemorySaver）
graph = create_main_graph()

# 2. 准备初始状态和配置
initial_state = build_initial_state("生成交易信号")
config = build_run_config(thread_id="user-123")

# 3. 执行（可能会中断）
try:
    result = graph.invoke(initial_state, config=config)
    print("执行完成")
except Exception as e:
    if "interrupt" in str(e).lower():
        print("执行已暂停")
        
        # 4. 检查状态
        snapshot = graph.get_state(config)
        print(f"当前节点: {snapshot.next}")
        
        # 5. 恢复执行
        from langgraph.types import Command
        resume_cmd = Command(resume={"data": "用户响应"})
        result = graph.invoke(resume_cmd, config=config)
```

### 使用自定义 Checkpointer

```python
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres import PostgresSaver

# 开发环境：使用内存存储
dev_checkpointer = MemorySaver()
graph = create_main_graph(checkpointer=dev_checkpointer)

# 生产环境：使用 PostgreSQL
# prod_checkpointer = PostgresSaver.from_conn_string("postgresql://...")
# graph = create_main_graph(checkpointer=prod_checkpointer)

# 测试环境：禁用 checkpointer（不推荐）
# graph = create_main_graph(checkpointer=False)
```

### 多会话管理

```python
# 会话 1
config1 = build_run_config(thread_id="user-123-session-1")
graph.invoke(state1, config=config1)

# 会话 2（独立的状态）
config2 = build_run_config(thread_id="user-456-session-2")
graph.invoke(state2, config=config2)

# 恢复会话 1
snapshot1 = graph.get_state(config1)
resume_cmd = Command(resume={"data": "响应"})
graph.invoke(resume_cmd, config=config1)
```

## Checkpointer 类型对比

| Checkpointer | 适用场景 | 优点 | 缺点 |
|-------------|---------|------|------|
| **MemorySaver** | 开发、测试 | 简单、快速、无需配置 | 进程重启后丢失 |
| **PostgresSaver** | 生产环境 | 持久化、支持分布式 | 需要数据库配置 |
| **RedisSaver** | 高并发场景 | 快速、支持分布式 | 需要 Redis 配置 |
| **FileSaver** | 单机部署 | 简单持久化 | 不支持分布式 |

## 状态持久化范围

### 主图状态

```python
class MainGraphState(TypedDict):
    messages: list                    # ✅ 持久化
    user_intent: dict | None          # ✅ 持久化
    signal_ready: bool                # ✅ 持久化
    backtest_ready: bool              # ✅ 持久化
    signal_context: dict              # ✅ 持久化（包含子图状态）
    backtest_context: dict            # ✅ 持久化（包含子图状态）
    errors: list[str]                 # ✅ 持久化
```

### 子图状态

通过 `signal_context` 和 `backtest_context` 持久化：

```python
# signal_context 包含的子图状态
{
    "current_task": str,
    "data_ready": bool,
    "indicators_ready": bool,
    "signal_ready": bool,
    "clarification_needed": str | None,
    "clarification_count": int,
    "execution_history": list[str],
    "error_messages": list[str],
    "max_retries": int,
    "retry_count": int,
}
```

### 全局数据状态

```python
# GLOBAL_DATA_STATE 不通过 checkpointer 持久化
# 原因：DataFrame 数据量大，不适合序列化
# 解决方案：通过文件系统或数据库单独管理
GLOBAL_DATA_STATE = GlobalDataState()
```

## 最佳实践

### 1. Thread ID 命名规范

```python
# ✅ 推荐：包含用户ID和会话ID
thread_id = f"user-{user_id}-session-{session_id}"

# ✅ 推荐：包含时间戳
from datetime import datetime
thread_id = f"session-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

# ❌ 避免：使用固定值（会导致会话冲突）
thread_id = "default"
```

### 2. 状态检查

```python
# 检查是否有未完成的会话
snapshot = graph.get_state(config)

if snapshot.next:
    print(f"会话未完成，下一步: {snapshot.next}")
    # 可以选择恢复或重新开始
else:
    print("会话已完成")
```

### 3. 错误处理

```python
try:
    result = graph.invoke(state, config=config)
except Exception as e:
    error_msg = str(e).lower()
    
    if "interrupt" in error_msg:
        # 正常的中断，等待用户输入
        handle_interrupt(graph, config)
    elif "command" in error_msg:
        # Command 相关错误
        print("恢复执行失败，请检查 Command 格式")
    else:
        # 其他错误
        raise
```

### 4. 清理旧会话

```python
# 对于 MemorySaver，重启进程会自动清理
# 对于持久化存储，需要定期清理

from datetime import datetime, timedelta

def cleanup_old_sessions(checkpointer, days=7):
    """清理超过指定天数的会话"""
    cutoff_date = datetime.now() - timedelta(days=days)
    
    # 具体实现取决于 checkpointer 类型
    # PostgresSaver 可以通过 SQL 删除
    # MemorySaver 不需要清理
    pass
```

### 5. 监控和日志

```python
import logging

logger = logging.getLogger(__name__)

def execute_with_monitoring(graph, state, config):
    """执行并监控状态"""
    thread_id = config["configurable"]["thread_id"]
    
    logger.info(f"开始执行会话: {thread_id}")
    
    try:
        result = graph.invoke(state, config=config)
        logger.info(f"会话完成: {thread_id}")
        return result
    except Exception as e:
        if "interrupt" in str(e).lower():
            logger.info(f"会话中断: {thread_id}")
            snapshot = graph.get_state(config)
            logger.info(f"中断位置: {snapshot.next}")
        else:
            logger.error(f"会话失败: {thread_id}", exc_info=True)
        raise
```

## 迁移到生产环境

### 从 MemorySaver 迁移到 PostgresSaver

```python
# 1. 安装依赖
# pip install langgraph-checkpoint-postgres

# 2. 配置数据库
from langgraph.checkpoint.postgres import PostgresSaver

conn_string = "postgresql://user:password@host:port/dbname"
checkpointer = PostgresSaver.from_conn_string(conn_string)

# 3. 创建表（首次运行）
checkpointer.setup()

# 4. 使用
graph = create_main_graph(checkpointer=checkpointer)
```

### 配置环境变量

```bash
# .env
DATABASE_URL=postgresql://user:password@host:port/dbname
CHECKPOINTER_TYPE=postgres  # 或 memory, redis, file
```

```python
# src/config.py
import os
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres import PostgresSaver

def get_checkpointer():
    """根据环境变量选择 checkpointer"""
    checkpointer_type = os.getenv("CHECKPOINTER_TYPE", "memory")
    
    if checkpointer_type == "postgres":
        conn_string = os.getenv("DATABASE_URL")
        return PostgresSaver.from_conn_string(conn_string)
    elif checkpointer_type == "memory":
        return MemorySaver()
    else:
        raise ValueError(f"Unknown checkpointer type: {checkpointer_type}")

# 使用
graph = create_main_graph(checkpointer=get_checkpointer())
```

## 常见问题

### Q1: 为什么子图不需要单独设置 checkpointer？

**A:** 子图会自动继承主图的 checkpointer。如果在子图上也设置 checkpointer，可能会导致状态不一致或冲突。

### Q2: MemorySaver 的状态会在进程重启后丢失吗？

**A:** 是的。MemorySaver 只在内存中保存状态，进程重启后会丢失。生产环境建议使用 PostgresSaver 或其他持久化存储。

### Q3: 如何在不同的图实例之间共享状态？

**A:** 使用同一个 checkpointer 实例：

```python
checkpointer = MemorySaver()

graph1 = create_main_graph(checkpointer=checkpointer)
graph2 = create_main_graph(checkpointer=checkpointer)

# graph1 和 graph2 共享状态
```

### Q4: thread_id 必须是字符串吗？

**A:** 是的，thread_id 必须是字符串类型。

### Q5: 如何查看所有活跃的会话？

**A:** 取决于 checkpointer 类型。对于 PostgresSaver，可以查询数据库；对于 MemorySaver，可以访问内部存储（不推荐）。

## 参考资料

- [LangGraph Persistence](https://langchain-ai.github.io/langgraph/concepts/persistence/)
- [LangGraph Checkpointers](https://langchain-ai.github.io/langgraph/concepts/persistence/#checkpointer-libraries)
- [Human-in-the-Loop Tutorial](https://langchain-ai.github.io/langgraph/tutorials/get-started/4-human-in-the-loop/)

