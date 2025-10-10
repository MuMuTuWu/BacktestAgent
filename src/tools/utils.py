import os
import json
import tushare as ts
from typing import Any


# 全局变量管理Tushare API初始化状态
_tushare_pro = None
_tushare_initialized = False


def _init_tushare_api():
    """初始化Tushare API"""
    global _tushare_pro, _tushare_initialized
    
    if _tushare_initialized:
        return _tushare_pro
        
    # 从环境变量获取Tushare token
    tushare_token = os.getenv('TUSHARE_TOKEN')
    if not tushare_token:
        raise ValueError(
            "请设置TUSHARE_TOKEN环境变量。"
            "可以在https://tushare.pro/register注册获取token"
        )
    
    # 设置token
    ts.set_token(tushare_token)
    _tushare_pro = ts.pro_api()
    _tushare_initialized = True
    
    return _tushare_pro


def print_llm_api_content(tool):
    """打印实际传入LLM API的核心内容"""
    print("=" * 50)
    print(f"name: {tool.name}")
    print(f"description: {tool.description}")
    print("=" * 50)
    schema = tool.tool_call_schema.model_json_schema()
    print(json.dumps(schema, indent=2, ensure_ascii=False))