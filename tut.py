# %%
import os
from langchain.chat_models import init_chat_model
import dotenv
dotenv.load_dotenv()

llm = init_chat_model(
    model="openai:gpt-4.1-nano",
    base_url=os.getenv("BASE_URL"),
    reasoning_effort="minimal",
)

# %%
from typing import Annotated, Any, Iterable

from langchain_tavily import TavilySearch
from langchain_core.tools import tool
from typing_extensions import TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from langgraph.types import Command, interrupt

class State(TypedDict):
    messages: Annotated[list, add_messages]
    name: str
    birthday: str

graph_builder = StateGraph(State)

from langchain_core.messages import AIMessageChunk, ToolMessage
from langchain_core.tools import InjectedToolCallId, tool

@tool
# Note that because we are generating a ToolMessage for a state update, we
# generally require the ID of the corresponding tool call. We can use
# LangChain's InjectedToolCallId to signal that this argument should not
# be revealed to the model in the tool's schema.
def human_assistance(
    name: str, birthday: str, tool_call_id: Annotated[str, InjectedToolCallId]
) -> str:
    """Request assistance from a human."""
    human_response = interrupt(
        {
            "question": "Is this correct?",
            "name": name,
            "birthday": birthday,
        },
    )
    # If the information is correct, update the state as-is.
    if human_response.get("correct", "").lower().startswith("y"):
        verified_name = name
        verified_birthday = birthday
        response = "Correct"
    # Otherwise, receive information from the human reviewer.
    else:
        verified_name = human_response.get("name", name)
        verified_birthday = human_response.get("birthday", birthday)
        response = f"Made a correction: {human_response}"

    # This time we explicitly update the state with a ToolMessage inside
    # the tool.
    state_update = {
        "name": verified_name,
        "birthday": verified_birthday,
        "messages": [ToolMessage(response, tool_call_id=tool_call_id)],
    }
    # We return a Command object in the tool to update our state.
    return Command(update=state_update)


tool = TavilySearch(max_results=2)
tools = [tool, human_assistance]
llm_with_tools = llm.bind_tools(tools)

def chatbot(state: State):
    message = llm_with_tools.invoke(state["messages"])
    # Because we will be interrupting during tool execution,
    # we disable parallel tool calling to avoid repeating any
    # tool invocations when we resume.
    assert len(message.tool_calls) <= 1
    return {"messages": [message]}

graph_builder.add_node("chatbot", chatbot)

tool_node = ToolNode(tools=tools)
graph_builder.add_node("tools", tool_node)

graph_builder.add_conditional_edges(
    "chatbot",
    tools_condition,
)
graph_builder.add_edge("tools", "chatbot")
graph_builder.add_edge(START, "chatbot")

# %%
memory = InMemorySaver()
graph = graph_builder.compile(checkpointer=memory)

# %%
from IPython.display import Image, display

try:
    display(Image(graph.get_graph().draw_mermaid_png()))
except Exception:
    # This requires some extra dependencies and is optional
    pass


# %%
user_input = (
    "Can you look up when LangGraph was released? "
    "When you have the answer, use the human_assistance tool for review."
)
config = {"configurable": {"thread_id": "1"}}


def _flatten_chunk_content(chunk: AIMessageChunk) -> str:
    content = chunk.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        pieces = []
        for item in content:
            text = getattr(item, "text", None)
            if text:
                pieces.append(text)
            elif isinstance(item, dict) and item.get("text"):
                pieces.append(item["text"])
            else:
                pieces.append(str(item))
        return "".join(pieces)
    fallback = getattr(chunk, "text", None)
    if fallback:
        return fallback
    return str(content)


def _print_stream(events: Iterable[Any]) -> None:
    trailing_stream = False

    for chunk in events:
        if isinstance(chunk, tuple):
            if len(chunk) == 2 and isinstance(chunk[0], str):
                mode, payload = chunk
            elif len(chunk) >= 1 and isinstance(chunk[0], AIMessageChunk):
                mode, payload = "messages", chunk[0]
            elif len(chunk) >= 1:
                mode, payload = "values", chunk[0]
            else:
                mode, payload = "values", chunk
        else:
            mode = "messages" if isinstance(chunk, AIMessageChunk) else "values"
            payload = chunk

        if mode == "messages":
            if isinstance(payload, tuple):
                first = payload[0] if payload else None
                if isinstance(first, AIMessageChunk):
                    payload = first
                else:
                    payload = payload if isinstance(payload, AIMessageChunk) else first
            if isinstance(payload, AIMessageChunk):
                text = _flatten_chunk_content(payload)
                if text:
                    print(text, end="", flush=True)
                    trailing_stream = True
            continue

        if isinstance(payload, dict) and "messages" in payload:
            payload["messages"][-1].pretty_print()
            continue

        if isinstance(payload, tuple) and payload:
            primary = payload[0]
            if isinstance(primary, dict) and "messages" in primary:
                primary["messages"][-1].pretty_print()
            continue

    if trailing_stream:
        print()


events = graph.stream(
    {"messages": [{"role": "user", "content": user_input}]},
    config,
    stream_mode=["values", "messages"],
)
_print_stream(events)

# %%
human_command = Command(
    resume={
        "name": "LangGraph",
        "birthday": "Jan 17, 2024",
    },
)

events = graph.stream(
    human_command,
    config,
    stream_mode=["values", "messages"],
)
_print_stream(events)
# %%
