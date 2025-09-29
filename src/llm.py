"""
LLM 模块：提供懒加载的全局单例 LLM 实例
"""

import os
import dotenv
from typing import Optional
from langchain.chat_models import init_chat_model
from config import config

# 加载环境变量
dotenv.load_dotenv()

# 全局变量存储 LLM 实例
_main_llm_instance: Optional[object] = None
_light_llm_instance: Optional[object] = None


def get_llm():
    """获取主要的 LLM 实例，采用懒加载模式"""
    global _main_llm_instance
    if _main_llm_instance is None:
        _main_llm_instance = init_chat_model(
            model=config["model_name"],
            base_url=os.getenv("BASE_URL"),
            reasoning_effort="minimal",
        )
    return _main_llm_instance


def get_light_llm():
    """获取轻量级 LLM 实例，采用懒加载模式"""
    global _light_llm_instance
    if _light_llm_instance is None:
        _light_llm_instance = init_chat_model(
            model=config["light_model_name"],
            base_url=os.getenv("BASE_URL"),
            reasoning_effort="minimal",
        )
    return _light_llm_instance


def reset_llm():
    """重置所有 LLM 实例（主要用于测试）"""
    global _main_llm_instance, _light_llm_instance
    _main_llm_instance = None
    _light_llm_instance = None
