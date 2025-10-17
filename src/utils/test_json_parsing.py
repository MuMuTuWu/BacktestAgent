"""
JSON解析工具的单元测试
"""
import json
import pytest
from .json_parsing import extract_json_from_response


class TestExtractJsonFromResponse:
    """测试extract_json_from_response函数"""
    
    def test_extract_json_from_markdown_code_block(self):
        """测试从markdown的json代码块中提取JSON"""
        response = """
        这是一些分析：
        ```json
        {"key": "value", "number": 42}
        ```
        这是其他信息。
        """
        result = extract_json_from_response(response)
        assert result == {"key": "value", "number": 42}
    
    def test_extract_json_from_plain_json(self):
        """测试从普通JSON文本中提取"""
        response = """
        分析: 我认为应该这样做。
        {"analysis": "某个分析", "next_action": "data_fetch"}
        更多信息。
        """
        result = extract_json_from_response(response)
        assert result["next_action"] == "data_fetch"
        assert result["analysis"] == "某个分析"
    
    def test_extract_json_with_nested_structure(self):
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
    
    def test_extract_json_with_default_on_error(self):
        """测试提取失败时返回默认值"""
        response = "这个响应中没有JSON"
        default = {"validation_passed": True, "issues_found": []}
        result = extract_json_from_response(response, default_on_error=default)
        assert result == default
    
    def test_extract_json_with_invalid_json_and_default(self):
        """测试JSON无效时返回默认值"""
        response = """```json
        {invalid json
        ```"""
        default = {"fallback": True}
        result = extract_json_from_response(response, default_on_error=default)
        assert result == default
    
    def test_extract_json_raises_without_default(self):
        """测试没有默认值时抛异常"""
        response = "没有JSON的响应"
        with pytest.raises(ValueError):
            extract_json_from_response(response)
    
    def test_extract_json_raises_invalid_json_without_default(self):
        """测试无效JSON且没有默认值时抛异常"""
        response = """```json
        {not valid json}
        ```"""
        with pytest.raises(json.JSONDecodeError):
            extract_json_from_response(response)
    
    def test_extract_json_multiple_braces(self):
        """测试当有多个大括号时，提取最后一个配对的括号范围"""
        response = """
        之前的JSON: {"old": "data"}
        最终结果:
        {"latest": "data", "status": "completed"}
        """
        result = extract_json_from_response(response)
        # 应该提取最后的JSON对象
        assert result["status"] == "completed"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
