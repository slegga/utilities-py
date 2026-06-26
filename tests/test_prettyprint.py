from utilities_perl.prettyprint import data_to_json_pretty, set_array_item


def test_set_array_item():
    array = ["a", "b", ["c", "d"]]
    set_array_item(array, 1, "e")
    assert array == ["a", "e", ["c", "d"]]


def test_json_easy():
    out = data_to_json_pretty({"a": "b"}, {"order": ["b"], "indent_text": " "})
    assert out == '{\n "a": "b"\n}'


def test_json_reorder():
    out = data_to_json_pretty({"a": "b", "c": "d"}, {"order": ["c"], "indent_text": " "})
    assert out == '{\n "c": "d",\n "a": "b"\n}'


def test_json_nested_hash():
    out = data_to_json_pretty(
        {"a": {"e": "f"}, "c": "d"}, {"order": ["c"], "indent_text": " "}
    )
    assert out == '{\n "c": "d",\n "a": {\n  "e": "f"\n }\n}'


def test_json_array():
    out = data_to_json_pretty(
        {"a": ["e", "f"], "c": "d"}, {"order": ["c"], "indent_text": " "}
    )
    assert out == '{\n "c": "d",\n "a": [\n  "e",\n  "f"\n ]\n}'
