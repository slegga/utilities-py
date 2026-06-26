import io

from utilities_perl.ask import ask
from utilities_perl.prettyprint import print_arrays, print_hashes


def test_print_arrays():
    out = print_arrays([["col1", "col2"], ["2col1", "2col2"]])
    assert out == "col1\tcol2\n2col1\t2col2\n"


def test_print_hashes_header_and_alignment():
    out = print_hashes([{"a": "1", "bb": "22"}, {"a": "333", "bb": "4"}])
    lines = out.splitlines()
    assert lines[0].split() == ["a", "bb"]
    assert "333" in lines[2]


def test_print_hashes_columns_first():
    out = print_hashes([{"a": "1", "z": "2"}], {"columns": ["z"]})
    header = out.splitlines()[0].split()
    assert header[0] == "z"


def test_ask_choice(monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("yes\n"))
    answer = ask("Continue?", ["yes", "no"])
    assert answer == "yes"


def test_ask_default_on_empty(monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("\n"))
    answer = ask("Pick", ["a", "b"], {"forced_answer": "a"})
    assert answer == "a"
