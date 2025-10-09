# 导入必要的模块
import sys
import os
sys.path.append('..')

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
    description="对内存变量 df 进行分析；务必 print 结果",
    globals={"df": df},
)

# 通过轻量模型创建一个简单的 ReAct 代理
agent = create_react_agent(
    light_llm,
    tools=[py_df_tool],
)

if __name__ == "__main__":
    result = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": "用 Python 计算 df 按 'city' 分组的均值并展示前 5 行",
                }
            ]
        }
    )
    final_message = result["messages"][-1]
    print(final_message.content)
