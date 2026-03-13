# tests/unit/test_json_utils.py
"""Unit tests for JSON cleaning and parsing utilities."""
import pytest
from core.llm.json_utils import clean_json_string, parse_json_response


class TestCleanJsonString:
    """Test JSON string cleaning."""

    def test_clean_markdown_code_block(self):
        text = '```json\n{"key": "value"}\n```'
        result = clean_json_string(text)
        assert result == '{"key": "value"}'

    def test_clean_double_braces(self):
        text = '{{"key": "value"}}'
        result = clean_json_string(text)
        assert '"key"' in result

    def test_clean_trailing_comma(self):
        text = '{"key": "value",}'
        result = clean_json_string(text)
        assert result == '{"key": "value"}'

    def test_clean_trailing_comma_in_array(self):
        text = '{"items": ["a", "b",]}'
        result = clean_json_string(text)
        assert result == '{"items": ["a", "b"]}'

    def test_extract_json_from_text(self):
        text = 'Here is the JSON: {"score": 85} and some more text.'
        result = clean_json_string(text)
        assert result == '{"score": 85}'

    def test_empty_string(self):
        result = clean_json_string("")
        assert result == ""

    def test_no_json_in_text(self):
        text = "No JSON here at all"
        result = clean_json_string(text)
        assert isinstance(result, str)


class TestParseJsonResponse:
    """Test JSON response parsing."""

    def test_parse_valid_json(self):
        text = '{"score": 85, "verdict": "MATCH"}'
        result = parse_json_response(text)
        assert result["score"] == 85
        assert result["verdict"] == "MATCH"

    def test_parse_json_with_markdown(self):
        text = '```json\n{"score": 90}\n```'
        result = parse_json_response(text)
        assert result["score"] == 90

    def test_parse_json_with_surrounding_text(self):
        text = 'Here is the result: {"score": 75} Hope this helps!'
        result = parse_json_response(text)
        assert result["score"] == 75

    def test_parse_invalid_json_returns_none(self):
        text = "This is not JSON at all"
        result = parse_json_response(text, retry_with_repair=False)
        assert result is None

    def test_parse_empty_string_returns_none(self):
        result = parse_json_response("")
        assert result is None

    def test_parse_nested_json(self):
        text = '{"data": {"name": "test", "items": [1, 2, 3]}}'
        result = parse_json_response(text)
        assert result["data"]["name"] == "test"
        assert len(result["data"]["items"]) == 3

    def test_parse_json_with_trailing_comma(self):
        text = '{"key": "value", "num": 42,}'
        result = parse_json_response(text)
        assert result is not None
        assert result["key"] == "value"

    def test_parse_json_with_double_braces(self):
        text = '{{"score": 50}}'
        result = parse_json_response(text)
        assert result is not None
