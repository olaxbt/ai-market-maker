from __future__ import annotations

from llm.json_parse import parse_json_object


def test_parse_json_object_plain() -> None:
    assert parse_json_object('{"a": 1, "b": "x"}') == {"a": 1, "b": "x"}


def test_parse_json_object_fenced() -> None:
    txt = 'Here you go:\n```json\n{"stance":"neutral","confidence":0.5,"reasons":["x"]}\n```'
    assert parse_json_object(txt) == {
        "stance": "neutral",
        "confidence": 0.5,
        "reasons": ["x"],
    }


def test_parse_json_object_preamble_and_trailing_text() -> None:
    txt = 'Preamble...\n{ "a": 1 }\nThanks!'
    assert parse_json_object(txt) == {"a": 1}


def test_parse_json_object_non_object_returns_none() -> None:
    assert parse_json_object("[1,2,3]") is None
    assert parse_json_object("null") is None
    assert parse_json_object("") is None
