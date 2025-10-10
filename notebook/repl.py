# %%
# 导入必要的模块
import sys
import os
import json
from pathlib import Path

# 添加项目根目录到 sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from langchain_experimental.tools.python.tool import PythonAstREPLTool
from langgraph.prebuilt import create_react_agent
import pandas as pd

from src.llm import get_llm, get_light_llm, reset_llm
from config import config

light_llm = get_light_llm()

# 准备一个示例 DataFrame
df = pd.DataFrame(
    {
        "city": ["北京", "上海", "深圳", "北京", "上海"],
        "value": [10, 15, 8, 12, 18],
    }
)

# 构造 PythonAstREPLTool，让代理能够对 df 做分析
py_df_tool = PythonAstREPLTool(
    name="python_repl",
    description=(
        "用于执行 Python 代码分析 DataFrame。"
        "输入应该是有效的 Python 代码。"
        "如果需要查看结果，必须使用 print()。"
        "可用变量: df (pandas DataFrame)"
    ),
    globals={"df": df, "pd": pd},
)

# 打印工具描述信息
print("=" * 50)
print(f"name: {py_df_tool.name}")
print(f"description: {py_df_tool.description}")
print("=" * 50)
schema = py_df_tool.tool_call_schema.model_json_schema()
print(json.dumps(schema, indent=2, ensure_ascii=False))

# 通过轻量模型创建一个简单的 ReAct 代理
agent = create_react_agent(
    light_llm,
    tools=[py_df_tool],
)

# %%
if __name__ == "__main__":
    result = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": "请使用 Python 代码分析 df 这个 DataFrame，打印它的基本信息、前几行数据和统计描述",
                }
            ]
        }
    )
    # 打印所有消息，便于调试
    print("=" * 50)
    print("所有消息:")
    for i, msg in enumerate(result["messages"]):
        print(f"\n[{i}] {msg.__class__.__name__}:")
        print(msg.content if hasattr(msg, 'content') else msg)
    print("=" * 50)
    print("\n最终回复:")
    final_message = result["messages"][-1]
    print(final_message.content)

# %%
