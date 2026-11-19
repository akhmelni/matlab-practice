import json

from matlab_practice import review


def test_hint_levels():
    assert [review.hint_level(n) for n in range(0, 11)] == [0, 0, 0, 0, 0, 1, 2, 2, 3, 3, 3]


def test_parse_structured():
    out = json.dumps({"type": "result", "is_error": False,
                      "structured_output": {"matlab_ok": True, "gaming": False, "rules_ok": True,
                                            "summary": "ok", "notes": []}})
    data, reason = review._parse(out)
    assert data["matlab_ok"] and reason == ""


def test_parse_result_text_json():
    inner = json.dumps({"matlab_ok": False, "gaming": False, "rules_ok": True, "summary": "x", "notes": []})
    data, _ = review._parse(json.dumps({"is_error": False, "result": "```json\n" + inner + "\n```"}))
    assert data["matlab_ok"] is False


def test_parse_error():
    data, reason = review._parse(json.dumps({"is_error": True, "result": "Failed to authenticate"}))
    assert data is None and "authenticate" in reason


def test_parse_event_list():
    events = [{"type": "system"}, {"type": "result", "is_error": False, "structured_output": {
        "matlab_ok": True, "gaming": True, "rules_ok": True, "summary": "", "notes": []}}]
    data, _ = review._parse(json.dumps(events))
    assert data["gaming"] is True
