"""Tests for safe operations utility module."""

from optipanel.utils.safe_ops import (
    safe_divide,
    safe_float_env,
    safe_get_nested,
    safe_index,
    safe_int_env,
    safe_json_load_file,
    safe_json_loads,
    safe_list_stats,
    safe_percentage,
)


class TestSafeDivide:
    def test_normal_division(self):
        assert safe_divide(10, 2) == 5.0
        assert safe_divide(15, 3) == 5.0

    def test_division_by_zero(self):
        assert safe_divide(10, 0) == 0.0
        assert safe_divide(10, 0, default=42.0) == 42.0

    def test_near_zero_division(self):
        assert safe_divide(10, 1e-10) == 0.0
        assert safe_divide(10, 1e-10, default=-1) == -1


class TestSafeIndex:
    def test_valid_index(self):
        lst = [1, 2, 3, 4, 5]
        assert safe_index(lst, 0) == 1
        assert safe_index(lst, 2) == 3
        assert safe_index(lst, -1) == 5

    def test_out_of_bounds(self):
        lst = [1, 2, 3]
        assert safe_index(lst, 5) is None
        assert safe_index(lst, -10) is None
        assert safe_index(lst, 5, default=42) == 42

    def test_empty_sequence(self):
        assert safe_index([], 0) is None
        assert safe_index([], 0, default="empty") == "empty"


class TestSafeEnvParsing:
    def test_safe_int_env(self, monkeypatch):
        monkeypatch.setenv("TEST_INT", "42")
        assert safe_int_env("TEST_INT") == 42

        monkeypatch.setenv("TEST_INT", "not_a_number")
        assert safe_int_env("TEST_INT", default=10) == 10

        assert safe_int_env("NONEXISTENT_VAR", default=5) == 5

    def test_safe_float_env(self, monkeypatch):
        monkeypatch.setenv("TEST_FLOAT", "3.14")
        assert safe_float_env("TEST_FLOAT") == 3.14

        monkeypatch.setenv("TEST_FLOAT", "invalid")
        assert safe_float_env("TEST_FLOAT", default=2.5) == 2.5


class TestSafeJson:
    def test_safe_json_loads(self):
        valid = '{"key": "value", "num": 42}'
        result = safe_json_loads(valid)
        assert result == {"key": "value", "num": 42}

    def test_malformed_json(self):
        invalid = '{"key": value"}'  # Missing quotes
        result = safe_json_loads(invalid)
        assert result == {}

        result = safe_json_loads(invalid, default={"error": True})
        assert result == {"error": True}

    def test_non_dict_json(self):
        array_json = '["a", "b", "c"]'
        result = safe_json_loads(array_json)
        assert result == {}  # Returns default since not a dict

    def test_safe_json_load_file(self, tmp_path):
        # Valid JSON file
        valid_file = tmp_path / "valid.json"
        valid_file.write_text('{"test": "data"}')
        result = safe_json_load_file(valid_file)
        assert result == {"test": "data"}

        # Invalid JSON file
        invalid_file = tmp_path / "invalid.json"
        invalid_file.write_text("{broken json}")
        result = safe_json_load_file(invalid_file, default={"fallback": True})
        assert result == {"fallback": True}

        # Nonexistent file
        missing = tmp_path / "missing.json"
        result = safe_json_load_file(missing)
        assert result == {}


class TestSafeGetNested:
    def test_valid_path(self):
        data = {"a": {"b": {"c": 42}}}
        assert safe_get_nested(data, "a", "b", "c") == 42
        assert safe_get_nested(data, "a", "b") == {"c": 42}

    def test_invalid_path(self):
        data = {"a": {"b": 1}}
        assert safe_get_nested(data, "a", "x") is None
        assert safe_get_nested(data, "a", "b", "c", default=99) == 99

    def test_non_dict_in_path(self):
        data = {"a": "string"}
        assert safe_get_nested(data, "a", "b") is None


class TestSafePercentage:
    def test_normal_percentage(self):
        assert safe_percentage(25, 100) == 25.0
        assert safe_percentage(1, 2) == 50.0

    def test_zero_whole(self):
        assert safe_percentage(10, 0) == 0.0
        assert safe_percentage(10, 0, default=100.0) == 100.0


class TestSafeListStats:
    def test_normal_stats(self):
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        stats = safe_list_stats(values)
        assert stats["avg"] == 3.0
        assert stats["min"] == 1.0
        assert stats["max"] == 5.0
        assert stats["p50"] == 3.0

    def test_empty_list(self):
        stats = safe_list_stats([])
        assert stats == {"avg": 0.0, "min": 0.0, "max": 0.0, "p50": 0.0, "p95": 0.0}

    def test_single_value(self):
        stats = safe_list_stats([42.0])
        assert stats["avg"] == 42.0
        assert stats["min"] == 42.0
        assert stats["max"] == 42.0
        assert stats["p50"] == 42.0
        assert stats["p95"] == 42.0
