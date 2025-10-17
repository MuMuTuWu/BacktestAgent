"""
JSON解析工具模块

提供从LLM响应中提取和解析JSON的通用函数。
"""
import json
from typing import Dict, Any, List, Optional


def extract_json_from_response(
    response_content: str, 
    required_keys: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    从LLM响应中提取并解析JSON
    
    该函数尝试以下几种方式从响应中提取JSON：
    1. 查找 ```json 代码块
    2. 查找大括号包围的JSON对象
    3. 尝试从右往左查找有效的JSON对象
    
    之后可选地验证必需的键是否存在。
    
    返回统一的结构化格式：
    
    成功时：
    {
        "success": True,
        "data": {解析后的JSON对象}
    }
    
    失败时：
    {
        "success": False,
        "error": {
            "type": "错误类型 (ValueError|JSONDecodeError|MissingRequiredKeys)",
            "message": "具体错误信息",
            "raw_response": "原始响应内容",
            "expected_keys": "required_keys参数的值（仅在键验证失败时出现）",
            "found_keys": "实际找到的键列表（仅在键验证失败时出现）",
            "missing_keys": "缺失的键列表（仅在键验证失败时出现）"
        }
    }
    
    参数:
        response_content (str): LLM的原始响应文本
        required_keys (Optional[List[str]]): 必需的键列表，默认为None（不验证）
    
    返回:
        Dict[str, Any]: 包含success标志和data/error的字典
    
    示例:
        >>> response = '一些文字 ```json\\n{"key": "value", "name": "test"}\\n``` 更多文字'
        >>> result = extract_json_from_response(response, required_keys=["key", "name"])
        >>> if result["success"]:
        ...     print(result["data"])
        ... else:
        ...     print(f"错误: {result['error']['message']}")
        
        >>> result2 = extract_json_from_response(response, required_keys=["key", "missing"])
        >>> if not result2["success"]:
        ...     print(f"缺失的键: {result2['error']['missing_keys']}")
    """
    try:
        json_data = None
        
        # 方式1：查找 ```json 代码块
        if "```json" in response_content:
            json_start = response_content.find("```json") + 7
            json_end = response_content.find("```", json_start)
            json_str = response_content[json_start:json_end].strip()
            json_data = json.loads(json_str)
        
        # 方式2：查找大括号包围的JSON对象
        if json_data is None and "{" in response_content and "}" in response_content:
            json_start = response_content.find("{")
            json_end = response_content.rfind("}") + 1
            json_str = response_content[json_start:json_end]
            
            try:
                json_data = json.loads(json_str)
            except json.JSONDecodeError:
                # 如果从第一个{到最后一个}的内容不是有效JSON，
                # 尝试从右往左查找，找到最后一个完整的JSON对象
                json_str = _find_last_json_object(response_content)
                if json_str:
                    json_data = json.loads(json_str)
                else:
                    raise
        
        # 都没找到
        if json_data is None:
            raise ValueError("未找到JSON格式的响应")
        
        # 验证必需的键
        if required_keys is not None:
            _validate_required_keys(json_data, required_keys, response_content)
        
        return {
            "success": True,
            "data": json_data
        }
        
    except (json.JSONDecodeError, ValueError) as e:
        error_type = type(e).__name__
        error_message = str(e)
        
        error_info = {
            "type": error_type,
            "message": error_message,
            "raw_response": response_content
        }
        
        # 如果是缺失必需键的错误，添加详细信息
        if isinstance(e, MissingRequiredKeysError):
            error_info["expected_keys"] = e.expected_keys
            error_info["found_keys"] = e.found_keys
            error_info["missing_keys"] = e.missing_keys
        
        return {
            "success": False,
            "error": error_info
        }


def _find_last_json_object(text: str) -> str | None:
    """
    从文本中查找最后一个完整的JSON对象
    
    通过从右往左扫描找到配对的大括号。
    """
    # 从右往左找到最后一个}
    last_brace = text.rfind("}")
    if last_brace == -1:
        return None
    
    # 从该位置往左查找对应的{
    brace_count = 0
    for i in range(last_brace, -1, -1):
        if text[i] == "}":
            brace_count += 1
        elif text[i] == "{":
            brace_count -= 1
            if brace_count == 0:
                return text[i:last_brace + 1]
    
    return None


def _validate_required_keys(
    json_data: Dict[str, Any], 
    required_keys: List[str], 
    response_content: str
) -> None:
    """
    验证JSON数据是否包含所有必需的键
    
    参数:
        json_data: 解析后的JSON数据
        required_keys: 必需的键列表
        response_content: 原始响应内容（用于错误消息的上下文）
    
    异常:
        MissingRequiredKeysError: 当缺少必需的键时抛出
    """
    found_keys = set(json_data.keys())
    required_keys_set = set(required_keys)
    missing_keys = required_keys_set - found_keys
    
    if missing_keys:
        raise MissingRequiredKeysError(
            expected_keys=required_keys,
            found_keys=list(found_keys),
            missing_keys=sorted(list(missing_keys))
        )


class MissingRequiredKeysError(ValueError):
    """当JSON缺少必需的键时抛出"""
    
    def __init__(self, expected_keys: List[str], found_keys: List[str], missing_keys: List[str]):
        self.expected_keys = expected_keys
        self.found_keys = found_keys
        self.missing_keys = missing_keys
        message = (
            f"JSON缺少必需的键。"
            f"期望的键: {expected_keys}, "
            f"实际找到的键: {found_keys}, "
            f"缺失的键: {missing_keys}"
        )
        super().__init__(message)
