"""
主图：统一 orchestrate 信号生成与回测子图。

主图仅负责编排子图与状态转换，所有日志、回调、重试等配置集中在这里。
"""
from __future__ import annotations

import dotenv

from typing import Any

from typing_extensions import NotRequired, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph
from langgraph.checkpoint.memory import MemorySaver

from .config import configurable
from .state import (
    MainGraphState,
    default_main_state,
    merge_backtest_state,
    merge_signal_state,
    to_backtest_state,
    to_signal_state,
)
from .subgraphs.backtest import build_backtest_graph
from .subgraphs.signal import build_signal_graph
from .task_logger import TaskLoggerCallbackHandler

dotenv.load_dotenv()


def create_main_graph(checkpointer=None):
    """
    构建并编译主图。
    
    Args:
        checkpointer: 可选的 checkpointer 实例，用于支持 human-in-the-loop 和状态持久化。
                     如果为 None，将使用默认的 MemorySaver。
                     传入 False 可以禁用 checkpointer（不推荐，会导致无法使用 interrupt）。
    
    Returns:
        编译后的主图实例
    
    注意：
        - Checkpointer 在主图上设置，子图会自动继承
        - 这样可以确保在子图中断（如 clarify_node）时，整个主图状态都被保存
        - 使用 MemorySaver 适合开发和测试，生产环境建议使用持久化存储（如 PostgreSQL）
    """
    builder = StateGraph(MainGraphState)

    signal_compiled = build_signal_graph().compile()
    backtest_compiled = build_backtest_graph().compile()

    def signal_node(state: MainGraphState, config: RunnableConfig = None):
        return _run_signal_subgraph(state, config, signal_compiled)

    def backtest_node(state: MainGraphState, config: RunnableConfig = None):
        return _run_backtest_subgraph(state, config, backtest_compiled)

    builder.add_node("signal", signal_node)
    builder.add_node("backtest", backtest_node)

    builder.set_entry_point("signal")
    builder.add_conditional_edges(
        "signal",
        _route_after_signal,
        {
            "backtest": "backtest",
            END: END,
        },
    )
    builder.add_edge("backtest", END)
    
    # 如果没有提供 checkpointer，使用默认的 MemorySaver
    # 如果明确传入 False，则不使用 checkpointer
    if checkpointer is None:
        checkpointer = MemorySaver()
    elif checkpointer is False:
        checkpointer = None
    
    return builder.compile(checkpointer=checkpointer)


def build_initial_state(query: str) -> MainGraphState:
    """根据用户问题构造主图初始状态。"""
    state = default_main_state()
    state["messages"] = [{"role": "user", "content": query}]
    state["user_intent"] = None
    return state


def build_run_config(thread_id: str = None) -> RunnableConfig:
    """
    统一构造执行配置，注入任务日志回调和 thread_id。
    
    Args:
        thread_id: 可选的线程ID，用于标识会话。如果为 None，将使用默认值 "default"。
                  对于 human-in-the-loop 场景，每个用户会话应该有唯一的 thread_id。
    
    Returns:
        RunnableConfig 配置字典
    """
    logger = TaskLoggerCallbackHandler(trim_log=False)
    
    # 合并 configurable，添加 thread_id
    config_dict = dict(configurable)
    config_dict["thread_id"] = thread_id or "default"

    return {
        "configurable": config_dict,
        "callbacks": [logger],
    }

def _run_signal_subgraph(
    state: MainGraphState,
    config: RunnableConfig | None,
    compiled_subgraph,
) -> SignalNodeUpdate:
    logger = _get_task_logger(config)
    if logger:
        logger.set_current_node("signal")

    previous_count = len(state.get("messages", []))
    sub_state = to_signal_state(state)
    result = compiled_subgraph.invoke(sub_state, config=config)

    if logger:
        logger.log_node_output("signal", result)
        logger.write_summary(result)

    merged = merge_signal_state(state, result)
    return {
        "messages": _messages_delta(result.get("messages", []), previous_count),
        "user_intent": merged.get("user_intent"),
        "signal_ready": merged.get("signal_ready"),
        "signal_context": merged.get("signal_context"),
        "errors": merged.get("errors"),
    }


def _run_backtest_subgraph(
    state: MainGraphState,
    config: RunnableConfig | None,
    compiled_subgraph,
) -> BacktestNodeUpdate:
    logger = _get_task_logger(config)
    if logger:
        logger.set_current_node("backtest")

    previous_count = len(state.get("messages", []))
    sub_state = to_backtest_state(state)
    result = compiled_subgraph.invoke(sub_state, config=config)

    if logger:
        logger.log_node_output("backtest", result)
        logger.write_summary(result)

    merged = merge_backtest_state(state, result)
    return {
        "messages": _messages_delta(result.get("messages", []), previous_count),
        "backtest_ready": merged.get("backtest_ready"),
        "backtest_context": merged.get("backtest_context"),
        "errors": merged.get("errors"),
    }


def _route_after_signal(state: MainGraphState) -> str:
    """根据信号生成结果决定是否进入回测子图。"""
    if state.get("signal_ready"):
        return "backtest"
    return END


def _messages_delta(messages: list, start_index: int) -> list:
    """提取从 start_index 起新增的消息，用于 add_messages 聚合。"""
    if not isinstance(messages, list):
        return [messages]
    if start_index <= 0:
        return messages
    if start_index >= len(messages):
        return []
    return messages[start_index:]


def _get_task_logger(config: RunnableConfig | None) -> TaskLoggerCallbackHandler | None:
    """从RunnableConfig中提取任务日志回调实例。"""
    if not config:
        return None
    callbacks = config.get("callbacks")
    if not callbacks:
        return None
    
    # 如果是 CallbackManager，需要访问其 handlers 属性
    if hasattr(callbacks, "handlers"):
        handlers = callbacks.handlers
    elif isinstance(callbacks, list):
        handlers = callbacks
    else:
        return None
    
    for callback in handlers:
        if isinstance(callback, TaskLoggerCallbackHandler):
            return callback
    return None


class SignalNodeUpdate(TypedDict, total=False):
    messages: list
    user_intent: NotRequired[dict | None]
    signal_ready: NotRequired[bool]
    signal_context: NotRequired[dict[str, Any]]
    errors: NotRequired[list[str]]


class BacktestNodeUpdate(TypedDict, total=False):
    messages: list
    backtest_ready: NotRequired[bool]
    backtest_context: NotRequired[dict[str, Any]]
    errors: NotRequired[list[str]]
