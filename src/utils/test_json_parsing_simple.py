"""
JSON解析工具的简单测试（不依赖pytest）
"""
import json
from .json_parsing import extract_json_from_response


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
    assert result == {"key": "value", "number": 42}, f"期望 {{'key': 'value', 'number': 42}}, 得到 {result}"
    print("✓ test_markdown_code_block 通过")


def test_plain_json():
    """测试从普通JSON文本中提取"""
    response = """
    分析: 我认为应该这样做。
    {"analysis": "某个分析", "next_action": "data_fetch"}
    更多信息。
    """
    result = extract_json_from_response(response)
    assert result["next_action"] == "data_fetch"
    assert result["analysis"] == "某个分析"
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
    assert result["validation_passed"] is True
    assert len(result["issues_found"]) == 2
    assert result["issues_found"][0]["severity"] == "error"
    assert result["data_summary"]["count"] == 300
    print("✓ test_nested_structure 通过")


def test_default_on_error():
    """测试提取失败时返回默认值"""
    response = "这个响应中没有JSON"
    default = {"validation_passed": True, "issues_found": []}
    result = extract_json_from_response(response, default_on_error=default)
    assert result == default, f"期望返回默认值，得到 {result}"
    print("✓ test_default_on_error 通过")


def test_invalid_json_with_default():
    """测试JSON无效时返回默认值"""
    response = """```json
    {invalid json
    ```"""
    default = {"fallback": True}
    result = extract_json_from_response(response, default_on_error=default)
    assert result == default, f"期望返回默认值，得到 {result}"
    print("✓ test_invalid_json_with_default 通过")


def test_raises_without_default():
    """测试没有默认值时抛异常"""
    response = "没有JSON的响应"
    try:
        extract_json_from_response(response)
        assert False, "应该抛出异常"
    except ValueError:
        print("✓ test_raises_without_default 通过")


def test_raises_invalid_json_without_default():
    """测试无效JSON且没有默认值时抛异常"""
    response = """```json
    {not valid json}
    ```"""
    try:
        extract_json_from_response(response)
        assert False, "应该抛出异常"
    except json.JSONDecodeError:
        print("✓ test_raises_invalid_json_without_default 通过")


def test_multiple_braces():
    """测试当有多个大括号时，提取最后一个配对的括号范围"""
    response = """
    之前的JSON: {"old": "data"}
    最终结果:
    {"latest": "data", "status": "completed"}
    """
    result = extract_json_from_response(response)
    # 应该提取最后的JSON对象
    assert result["status"] == "completed"
    print("✓ test_multiple_braces 通过")


if __name__ == "__main__":
    print("开始运行JSON解析工具测试...\n")
    test_markdown_code_block()
    test_plain_json()
    test_nested_structure()
    test_default_on_error()
    test_invalid_json_with_default()
    test_raises_without_default()
    test_raises_invalid_json_without_default()
    test_multiple_braces()
    print("\n✓ 所有测试通过！")
