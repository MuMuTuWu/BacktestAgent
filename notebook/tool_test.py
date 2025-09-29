# %%
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.tools.utils import print_llm_api_content

from src.tools.daily_ind import tushare_daily_basic_tool

print_llm_api_content(tushare_daily_basic_tool)
# %%
