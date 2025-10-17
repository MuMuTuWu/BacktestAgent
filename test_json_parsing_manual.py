"""
JSON解析工具的手动测试
"""
import json
import sys
from src.utils.json_parsing import extract_json_from_response


def test_markdown_code_block():
    """测试从markdown的json代码块中提取JSON"""
    response = """
    这是一些分析：
    ```json
    {"key": "value", "number": 42}
    ```
    这是其他信息。
    """
    result = extract_json_from_response(response)
    assert result["success"] is True, f"期望成功，得到 {result}"
    assert result["data"] == {"key": "value", "number": 42}
    print("✓ test_markdown_code_block 通过")


def test_plain_json():
    """测试从普通JSON文本中提取"""
    response = """
    分析: 我认为应该这样做。
    {"analysis": "某个分析", "next_action": "data_fetch"}
    更多信息。
    """
    result = extract_json_from_response(response)
    assert result["success"] is True
    assert result["data"]["next_action"] == "data_fetch"
    assert result["data"]["analysis"] == "某个分析"
    print("✓ test_plain_json 通过")


def test_nested_structure():
    """测试提取包含嵌套结构的JSON"""
    response = """```json
    {
        "validation_passed": true,
        "issues_found": [
            {"severity": "error", "message": "缺少数据"},
            {"severity": "warning", "message": "数据质量低"}
        ],
        "data_summary": {"count": 300, "records": 75000}
    }
    ```"""
    result = extract_json_from_response(response)
    assert result["success"] is True
    assert result["data"]["validation_passed"] is True
    assert len(result["data"]["issues_found"]) == 2
    assert result["data"]["issues_found"][0]["severity"] == "error"
    assert result["data"]["data_summary"]["count"] == 300
    print("✓ test_nested_structure 通过")


def test_no_json():
    """测试没有JSON的响应，应返回error"""
    response = "这个响应中没有JSON"
    result = extract_json_from_response(response)
    assert result["success"] is False, "期望失败"
    assert "error" in result
    assert result["error"]["type"] == "ValueError"
    assert "未找到JSON格式的响应" in result["error"]["message"]
    assert result["error"]["raw_response"] == response
    print("✓ test_no_json 通过")


def test_invalid_json():
    """测试无效JSON，应返回error"""
    response = """```json
    {invalid json
    ```"""
    result = extract_json_from_response(response)
    assert result["success"] is False, "期望失败"
    assert "error" in result
    assert result["error"]["type"] == "JSONDecodeError"
    assert result["error"]["raw_response"] is not None
    print("✓ test_invalid_json 通过")


def test_multiple_json_objects():
    """测试多个JSON对象，提取最后一个完整的"""
    response = """
    之前的JSON: {"old": "data"}
    最终结果:
    {"latest": "data", "status": "completed"}
    """
    result = extract_json_from_response(response)
    assert result["success"] is True
    assert isinstance(result["data"], dict)
    print("✓ test_multiple_json_objects 通过")


def test_error_structure():
    """测试错误返回格式的完整性"""
    response = "无效响应"
    result = extract_json_from_response(response)
    
    assert not result["success"]
    assert "error" in result
    error = result["error"]
    assert "type" in error
    assert "message" in error
    assert "raw_response" in error
    assert error["type"] in ["ValueError", "JSONDecodeError"]
    print("✓ test_error_structure 通过")


def test_success_structure():
    """测试成功返回格式的完整性"""
    response = '```json\n{"test": "data"}\n```'
    result = extract_json_from_response(response)
    
    assert result["success"] is True
    assert "data" in result
    assert result["data"] == {"test": "data"}
    assert "error" not in result or result.get("error") is None
    print("✓ test_success_structure 通过")


if __name__ == "__main__":
    print("开始运行JSON解析工具测试...\n")
    try:
        test_markdown_code_block()
        test_plain_json()
        test_nested_structure()
        test_no_json()
        test_invalid_json()
        test_multiple_json_objects()
        test_error_structure()
        test_success_structure()
        print("\n✓ 所有测试通过！")
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
