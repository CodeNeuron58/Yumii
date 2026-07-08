"""Tests for the bind-time tool schema sanitizer.

Composio schemas declare optional fields as bare types with
``default: null``; llama fills optionals with explicit ``null`` and
Groq validates strictly — rejecting semantically correct tool calls
with ``tool_use_failed``. The sanitizer widens null-defaulted fields
to nullable unions so the model's behaviour is legal.
"""

from yumii.tools.registry import _make_null_defaults_nullable


def test_null_default_bare_type_becomes_union():
    params = {"properties": {"query": {"type": "string", "default": None}}}
    _make_null_defaults_nullable(params)
    assert params["properties"]["query"]["type"] == ["string", "null"]


def test_non_null_default_untouched():
    params = {
        "properties": {
            "max_results": {"type": "integer", "default": 1},
            "verbose": {"type": "boolean", "default": True},
        }
    }
    _make_null_defaults_nullable(params)
    assert params["properties"]["max_results"]["type"] == "integer"
    assert params["properties"]["verbose"]["type"] == "boolean"


def test_no_default_untouched():
    params = {"properties": {"thread_id": {"type": "string"}}}
    _make_null_defaults_nullable(params)
    assert params["properties"]["thread_id"]["type"] == "string"


def test_null_default_anyof_gains_null_branch():
    params = {
        "properties": {
            "attachment": {
                "default": None,
                "anyOf": [{"type": "object", "properties": {}}, {"type": "array"}],
            }
        }
    }
    _make_null_defaults_nullable(params)
    assert {"type": "null"} in params["properties"]["attachment"]["anyOf"]


def test_anyof_with_existing_null_not_duplicated():
    params = {
        "properties": {
            "x": {"default": None, "anyOf": [{"type": "string"}, {"type": "null"}]}
        }
    }
    _make_null_defaults_nullable(params)
    nulls = [o for o in params["properties"]["x"]["anyOf"] if o.get("type") == "null"]
    assert len(nulls) == 1


def test_nested_object_properties_are_fixed():
    params = {
        "properties": {
            "config": {
                "type": "object",
                "properties": {"inner": {"type": "string", "default": None}},
            }
        }
    }
    _make_null_defaults_nullable(params)
    assert params["properties"]["config"]["properties"]["inner"]["type"] == [
        "string",
        "null",
    ]


def test_real_gmail_shape_end_to_end():
    """The exact three fields from Groq's tool_use_failed error."""
    params = {
        "properties": {
            "query": {"type": "string", "default": None},
            "label_ids": {"type": "array", "default": None, "items": {"type": "string"}},
            "page_token": {"type": "string", "default": None},
            "max_results": {"type": "integer", "default": 1},
        }
    }
    _make_null_defaults_nullable(params)
    p = params["properties"]
    assert p["query"]["type"] == ["string", "null"]
    assert p["label_ids"]["type"] == ["array", "null"]
    assert p["page_token"]["type"] == ["string", "null"]
    assert p["max_results"]["type"] == "integer"
