"""
测试 extract_json_from_response 函数的 required_keys 参数功能
"""
from json_parsing import extract_json_from_response


def test_basic_json_extraction():
    """测试基本的JSON提取（不验证键）"""
    response = '一些文字 ```json\n{"key": "value", "name": "test"}\n``` 更多文字'
    result = extract_json_from_response(response)
    
    assert result["success"] == True, "应该成功解析JSON"
    assert result["data"]["key"] == "value"
    assert result["data"]["name"] == "test"
    print("✓ test_basic_json_extraction 通过")


def test_with_required_keys_all_present():
    """测试required_keys参数，所有必需键都存在"""
    response = '```json\n{"key": "value", "name": "test", "age": 25}\n```'
    result = extract_json_from_response(response, required_keys=["key", "name"])
    
    assert result["success"] == True, "应该成功解析JSON"
    assert result["data"]["key"] == "value"
    assert result["data"]["name"] == "test"
    print("✓ test_with_required_keys_all_present 通过")


def test_with_required_keys_missing_one():
    """测试required_keys参数，缺少一个必需键"""
    response = '```json\n{"key": "value"}\n```'
    result = extract_json_from_response(response, required_keys=["key", "name"])
    
    assert result["success"] == False, "应该失败"
    assert result["error"]["type"] == "MissingRequiredKeysError"
    assert "name" in result["error"]["missing_keys"]
    assert result["error"]["expected_keys"] == ["key", "name"]
    assert result["error"]["found_keys"] == ["key"]
    print("✓ test_with_required_keys_missing_one 通过")


def test_with_required_keys_missing_multiple():
    """测试required_keys参数，缺少多个必需键"""
    response = '```json\n{"key": "value"}\n```'
    result = extract_json_from_response(response, required_keys=["key", "name", "age", "status"])
    
    assert result["success"] == False, "应该失败"
    assert result["error"]["type"] == "MissingRequiredKeysError"
    missing = set(result["error"]["missing_keys"])
    assert "name" in missing
    assert "age" in missing
    assert "status" in missing
    assert "key" not in missing
    print("✓ test_with_required_keys_missing_multiple 通过")


def test_invalid_json_with_required_keys():
    """测试无效JSON时，即使指定了required_keys也应该返回JSON解析错误"""
    response = '```json\n{invalid json}\n```'
    result = extract_json_from_response(response, required_keys=["key"])
    
    assert result["success"] == False, "应该失败"
    assert result["error"]["type"] == "JSONDecodeError"
    print("✓ test_invalid_json_with_required_keys 通过")


def test_no_json_found():
    """测试找不到JSON时"""
    response = '这是一个没有JSON的文本'
    result = extract_json_from_response(response)
    
    assert result["success"] == False, "应该失败"
    assert result["error"]["type"] == "ValueError"
    assert "未找到JSON" in result["error"]["message"]
    print("✓ test_no_json_found 通过")


def test_empty_required_keys():
    """测试空的required_keys列表"""
    response = '```json\n{"key": "value"}\n```'
    result = extract_json_from_response(response, required_keys=[])
    
    assert result["success"] == True, "应该成功，因为没有必需的键"
    print("✓ test_empty_required_keys 通过")


def test_without_required_keys_parameter():
    """测试不指定required_keys参数（向后兼容）"""
    response = '```json\n{"key": "value"}\n```'
    result = extract_json_from_response(response)
    
    assert result["success"] == True, "应该成功"
    assert result["data"]["key"] == "value"
    print("✓ test_without_required_keys_parameter 通过")


def test_nested_json_with_required_keys():
    """测试嵌套JSON与required_keys检查（检查顶级键）"""
    response = '```json\n{"key": "value", "nested": {"inner": "data"}}\n```'
    result = extract_json_from_response(response, required_keys=["key", "nested"])
    
    assert result["success"] == True, "应该成功"
    assert result["data"]["nested"]["inner"] == "data"
    print("✓ test_nested_json_with_required_keys 通过")


def test_error_message_context():
    """测试错误消息提供的上下文"""
    response = '这是LLM的回复：```json\n{"id": 123}\n```\n建议使用这个JSON'
    result = extract_json_from_response(response, required_keys=["id", "name", "email"])
    
    assert result["success"] == False
    assert result["error"]["raw_response"] == response, "应该包含原始响应"
    assert result["error"]["expected_keys"] == ["id", "name", "email"]
    assert result["error"]["found_keys"] == ["id"]
    assert set(result["error"]["missing_keys"]) == {"name", "email"}
    print("✓ test_error_message_context 通过")


if __name__ == "__main__":
    test_basic_json_extraction()
    test_with_required_keys_all_present()
    test_with_required_keys_missing_one()
    test_with_required_keys_missing_multiple()
    test_invalid_json_with_required_keys()
    test_no_json_found()
    test_empty_required_keys()
    test_without_required_keys_parameter()
    test_nested_json_with_required_keys()
    test_error_message_context()
    
    print("\n✅ 所有测试都通过了！")
