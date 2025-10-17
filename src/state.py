from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock
from typing import Annotated, Any, Dict, TYPE_CHECKING

from pandas import DataFrame
from typing_extensions import NotRequired, TypedDict, cast

from langgraph.graph.message import add_messages

if TYPE_CHECKING:
    from .subgraphs.signal.state import SignalSubgraphState  # pragma: no cover
    from .subgraphs.backtest.state import BacktestSubgraphState  # pragma: no cover
else:  # 在运行时避免循环依赖
    SignalSubgraphState = Dict[str, Any]
    BacktestSubgraphState = Dict[str, Any]


class MainGraphState(TypedDict):
    """主图在各子图之间传递的状态定义。"""

    messages: Annotated[list, add_messages]
    user_intent: NotRequired[dict | None]
    signal_ready: NotRequired[bool]
    backtest_ready: NotRequired[bool]
    signal_context: NotRequired[dict[str, Any]]
    backtest_context: NotRequired[dict[str, Any]]
    errors: NotRequired[list[str]]


_SIGNAL_CONTEXT_KEYS: tuple[str, ...] = (
    "current_task",
    "data_ready",
    "indicators_ready",
    "signal_ready",
    "execution_history",
    "error_messages",
    "max_retries",
    "retry_count",
)

_BACKTEST_CONTEXT_KEYS: tuple[str, ...] = (
    "current_task",
    "signal_ready",
    "backtest_completed",
    "returns_ready",
    "pnl_plot_ready",
    "backtest_params",
    "execution_history",
    "error_messages",
    "max_retries",
    "retry_count",
)


def default_main_state() -> MainGraphState:
    """创建主图的初始状态。"""
    return {
        "messages": [],
        "user_intent": None,
        "signal_ready": False,
        "backtest_ready": False,
        "signal_context": {},
        "backtest_context": {},
        "errors": [],
    }


def to_signal_state(main_state: MainGraphState) -> SignalSubgraphState:
    """将主图状态映射为信号子图所需的状态。"""
    context = dict(main_state.get("signal_context", {}))
    user_intent = main_state.get("user_intent") or {}

    state: SignalSubgraphState = {
        "messages": list(main_state["messages"]),
        "current_task": context.get("current_task", ""),
        "data_ready": context.get("data_ready", False),
        "indicators_ready": context.get("indicators_ready", False),
        "signal_ready": context.get("signal_ready", False),
        "user_intent": user_intent,
        "execution_history": context.get("execution_history", []).copy(),
        "error_messages": context.get("error_messages", []).copy(),
        "max_retries": context.get("max_retries", 3),
        "retry_count": context.get("retry_count", 0),
    }
    return state


def merge_signal_state(
    main_state: MainGraphState,
    signal_state: SignalSubgraphState,
) -> MainGraphState:
    """将信号子图的执行结果写回主图状态。"""
    next_state: Dict[str, Any] = dict(main_state)
    next_state["user_intent"] = signal_state.get("user_intent")
    next_state["signal_ready"] = signal_state.get("signal_ready", False)

    next_state["signal_context"] = _pick_context(signal_state, _SIGNAL_CONTEXT_KEYS)

    aggregated_errors = list(main_state.get("errors", []))
    aggregated_errors.extend(signal_state.get("error_messages", []))
    next_state["errors"] = aggregated_errors
    return cast(MainGraphState, next_state)


def to_backtest_state(main_state: MainGraphState) -> BacktestSubgraphState:
    """将主图状态映射为回测子图所需的状态。"""
    context = dict(main_state.get("backtest_context", {}))

    state: BacktestSubgraphState = {
        "messages": list(main_state["messages"]),
        "current_task": context.get("current_task", ""),
        "signal_ready": context.get(
            "signal_ready", main_state.get("signal_ready", False)
        ),
        "backtest_completed": context.get("backtest_completed", False),
        "returns_ready": context.get("returns_ready", False),
        "pnl_plot_ready": context.get("pnl_plot_ready", False),
        "backtest_params": context.get(
            "backtest_params",
            {"init_cash": 100000, "fees": 0.001, "slippage": 0.0},
        ),
        "execution_history": context.get("execution_history", []).copy(),
        "error_messages": context.get("error_messages", []).copy(),
        "max_retries": context.get("max_retries", 3),
        "retry_count": context.get("retry_count", 0),
    }
    return state


def merge_backtest_state(
    main_state: MainGraphState,
    backtest_state: BacktestSubgraphState,
) -> MainGraphState:
    """将回测子图的执行结果写回主图状态。"""
    next_state: Dict[str, Any] = dict(main_state)
    next_state["backtest_ready"] = backtest_state.get("backtest_completed", False)
    next_state["backtest_context"] = _pick_context(
        backtest_state, _BACKTEST_CONTEXT_KEYS
    )

    aggregated_errors = list(main_state.get("errors", []))
    aggregated_errors.extend(backtest_state.get("error_messages", []))
    next_state["errors"] = aggregated_errors
    return cast(MainGraphState, next_state)


def _pick_context(source: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    """从子图结果中提取需要保留到主图的上下文。"""
    context: dict[str, Any] = {}
    for key in keys:
        if key not in source:
            continue
        value = source[key]
        if isinstance(value, list):
            context[key] = value.copy()
        elif isinstance(value, dict):
            context[key] = value.copy()
        else:
            context[key] = value
    return context


DataFrameMap = dict[str, DataFrame]


@dataclass
class GlobalDataState:
    ohlcv: DataFrameMap = field(default_factory=dict)
    indicators: DataFrameMap = field(default_factory=dict)
    signal: DataFrameMap = field(default_factory=dict)
    backtest_results: DataFrameMap = field(default_factory=dict)

    _lock: RLock = field(default_factory=RLock, repr=False)
    _DICT_FIELDS: tuple[str, ...] = ("ohlcv", "indicators", "signal", "backtest_results")

    def override(self, **entries: dict[str, Any] | None) -> None:
        """Override provided dict fields atomically."""
        with self._lock:
            for key, value in entries.items():
                if value is None or not hasattr(self, key):
                    continue
                if not isinstance(value, dict):
                    continue
                setattr(self, key, dict(value))

    def update(self, field_name: str, entries: DataFrameMap) -> None:
        """Update a dict field with the provided DataFrame values."""
        if not hasattr(self, field_name):
            raise KeyError(f"Unknown field '{field_name}' in GlobalDataState")
        if not isinstance(entries, dict):
            raise TypeError("entries must be a dict[str, DataFrame]")

        with self._lock:
            target = getattr(self, field_name)
            if not isinstance(target, dict):
                raise TypeError(
                    f"Field '{field_name}' is not a dict and cannot be updated"
                )
            for key, value in entries.items():
                target[key] = value.copy(deep=False) if isinstance(value, DataFrame) else value

    def snapshot(self) -> dict[str, DataFrameMap]:
        """Return a copy of the current data for read-only use."""
        with self._lock:
            return {name: self._copy_df_map(getattr(self, name)) for name in self._DICT_FIELDS}

    def get_field(self, field_name: str) -> DataFrameMap:
        """Thread-safe access to a single dictionary field by name."""
        if field_name not in self._DICT_FIELDS:
            raise KeyError(f"Unknown field '{field_name}' in GlobalDataState")
        with self._lock:
            return self._copy_df_map(getattr(self, field_name))

    @staticmethod
    def _copy_df_map(source: DataFrameMap | None) -> DataFrameMap:
        if not source:
            return {}
        return {key: df.copy(deep=False) for key, df in source.items()}


GLOBAL_DATA_STATE = GlobalDataState()
