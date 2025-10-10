from dataclasses import dataclass, field
from threading import RLock
from typing import Annotated, Any

from pandas import DataFrame

from typing_extensions import TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    # Messages have the type "list". The `add_messages` function
    # in the annotation defines how this state key should be updated
    # (in this case, it appends messages to the list, rather than overwriting them)
    messages: Annotated[list, add_messages]



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
                raise TypeError(f"Field '{field_name}' is not a dict and cannot be updated")
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


graph_builder = StateGraph(AgentState)
