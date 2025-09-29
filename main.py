# %%
# Create a StateGraph
from typing import Annotated, Any, Sequence

from typing_extensions import TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.types import StreamMode
from langchain_core.runnables.config import RunnableConfig


class State(TypedDict):
    # Messages have the type "list". The `add_messages` function
    # in the annotation defines how this state key should be updated
    # (in this case, it appends messages to the list, rather than overwriting them)
    messages: Annotated[list, add_messages]


graph_builder = StateGraph(State)

# %%
# Add a node
import dotenv
dotenv.load_dotenv()

import os
from src.llm import get_llm

def chatbot(state: State):
    llm = get_llm()
    return {"messages": [llm.invoke(state["messages"])]}


# The first argument is the unique node name
# The second argument is the function or object that will be called whenever
# the node is used.
graph_builder.add_node("chatbot", chatbot)

# %%
# Add an entry point
graph_builder.add_edge(START, "chatbot")
# Add an exit point
graph_builder.add_edge("chatbot", END)
# Compile the graph
graph = graph_builder.compile()




# %%
# # Run the chatbot
# def _as_message_list(candidate: Any) -> list[Any] | None:
#     if isinstance(candidate, list):
#         return candidate
#     return None


# def _message_content(message: Any) -> str | None:
#     content = getattr(message, "content", None)
#     if content:
#         return content
#     if isinstance(message, dict):
#         raw = message.get("content")
#         if isinstance(raw, str):
#             return raw
#     return None


# def _message_role(message: Any) -> str | None:
#     role = getattr(message, "type", None)
#     if isinstance(role, str):
#         return role
#     if isinstance(message, dict):
#         role = message.get("role")
#         if isinstance(role, str):
#             return role
#     return None


# def _display_message(message: Any, prefix: str) -> bool:
#     pretty_printer = getattr(message, "pretty_print", None)
#     if callable(pretty_printer):
#         if prefix not in ("", "Assistant"):
#             print(f"{prefix}:")
#         pretty_printer()
#         return True

#     content = _message_content(message)
#     if content:
#         print(f"{prefix}: {content}")
#         return True
#     return False


# def _print_assistant_messages(messages: list[Any], prefix: str = "Assistant") -> bool:
#     printed = False
#     for msg in messages:
#         if _message_role(msg) in ("assistant", "ai"):
#             if _display_message(msg, prefix):
#                 printed = True
#     return printed


# def _print_last_assistant(messages: list[Any]) -> bool:
#     for msg in reversed(messages):
#         if _message_role(msg) in ("assistant", "ai"):
#             if _display_message(msg, "Assistant"):
#                 return True
#     return False


# def _handle_updates(payload: dict[str, Any]) -> None:
#     for node_name, update in payload.items():
#         if node_name == "__interrupt__":
#             print(f"[updates] interrupt: {update}")
#             continue
#         if isinstance(update, dict):
#             messages = _as_message_list(update.get("messages"))
#             if messages:
#                 _print_assistant_messages(messages, prefix=f"Assistant[{node_name}]")
#             for key, value in update.items():
#                 if key == "messages":
#                     continue
#                 print(f"[updates] {node_name}.{key}: {value}")
#         else:
#             print(f"[updates] {node_name}: {update}")


# def _handle_values(payload: dict[str, Any]) -> None:
#     messages = _as_message_list(payload.get("messages")) if isinstance(payload, dict) else None
#     if messages and _print_last_assistant(messages):
#         return
#     print(f"[values] {payload}")


# def _handle_messages(payload: Any) -> None:
#     if isinstance(payload, tuple) and len(payload) == 2:
#         token, metadata = payload
#         print(f"[messages] token={token!s} metadata={metadata}")
#     else:
#         print(f"[messages] {payload}")


# def _handle_tasks(payload: Any) -> None:
#     if isinstance(payload, dict):
#         name = payload.get("name", "<unknown>")
#         if "result" in payload or "error" in payload:
#             status = "failed" if payload.get("error") else "finished"
#             print(f"[tasks] {name} {status}: {payload}")
#         else:
#             print(f"[tasks] {name} started: {payload}")
#     else:
#         print(f"[tasks] {payload}")


# def _handle_checkpoint(payload: Any) -> None:
#     print(f"[checkpoints] {payload}")


# def _dispatch_event(mode: StreamMode, payload: Any) -> None:
#     if mode == "updates" and isinstance(payload, dict):
#         _handle_updates(payload)
#     elif mode == "values" and isinstance(payload, dict):
#         _handle_values(payload)
#     elif mode == "messages":
#         _handle_messages(payload)
#     elif mode == "custom":
#         print(f"[custom] {payload}")
#     elif mode == "tasks":
#         _handle_tasks(payload)
#     elif mode == "checkpoints":
#         _handle_checkpoint(payload)
#     else:
#         print(f"[{mode}] {payload}")


# def _normalize_modes(stream_mode: StreamMode | Sequence[StreamMode]) -> list[StreamMode]:
#     if isinstance(stream_mode, str):
#         return [stream_mode]
#     return list(stream_mode)


# def stream_graph_updates(
#     user_input: str,
#     stream_mode: StreamMode | Sequence[StreamMode] = "updates",
#     config: RunnableConfig | None = None,
# ) -> None:
#     modes = _normalize_modes(stream_mode)
#     if not modes:
#         raise ValueError("stream_mode 不能为空")

#     multi_mode = len(modes) > 1
#     stream_arg: StreamMode | Sequence[StreamMode]
#     stream_arg = modes if multi_mode else modes[0]

#     for chunk in graph.stream(
#         {"messages": [{"role": "user", "content": user_input}]},
#         config,
#         stream_mode=stream_arg,
#     ):
#         if multi_mode:
#             mode, payload = chunk
#         else:
#             mode, payload = modes[0], chunk
#         _dispatch_event(mode, payload)

# %%
user_input = "Hi there! My name is Will."
config: RunnableConfig | None = None

# The config is the second positional argument to stream()
events = graph.stream(
    {"messages": [{"role": "user", "content": user_input}]},
    config,
    stream_mode="values",
)

for event in events:
    messages = event.get("messages") if isinstance(event, dict) else None
    if isinstance(messages, list) and messages:
        last_message = messages[-1]
        print(f"Assistant: {last_message}")
    else:
        print(f"[values] {event}")
