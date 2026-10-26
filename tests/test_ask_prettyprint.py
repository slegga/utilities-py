import io
import re

import pytest

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


def test_ask_regexvalg(monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("yes\n"))
    assert ask("Fortsett?", re.compile(r"(yes|no)")) == "yes"


def test_ask_regexvalg_gjentar_ved_feil_svar(monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("kanskje\nno\n"))
    assert ask("Fortsett?", re.compile(r"(yes|no)")) == "no"


def test_ask_exit_on_nochoice_1_stopper(monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("kanskje\n"))
    with pytest.raises(RuntimeError, match="Execution stopped"):
        ask("Velg", ["yes", "no"], {"exit_on_nochoice": 1})


def test_ask_exit_on_nochoice_2_gir_none(monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("kanskje\n"))
    assert ask("Velg", ["yes", "no"], {"exit_on_nochoice": 2}) is None


def test_ask_remember_henter_forrige_svar(monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("yes\n"))
    assert ask("Husk meg?", ["yes", "no"], {"remember": True}) == "yes"
    monkeypatch.setattr("sys.stdin", io.StringIO("\n"))
    assert ask("Husk meg?", ["yes", "no"], {"remember": True}) == "yes"


def test_ask_secret_bruker_getpass(monkeypatch):
    kall = []

    def fake_getpass(prompt=""):
        kall.append(prompt)
        return "hemmelig"

    monkeypatch.setattr("getpass.getpass", fake_getpass)
    monkeypatch.setattr("sys.stdin", io.StringIO("feil\n"))
    assert ask("Passord?", ["hemmelig"], {"secret": True}) == "hemmelig"
    assert kall == [""]


def test_ask_is_forced_1_skriver_svaret(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("b\n"))
    assert ask("Tving", ["a", "b"], {"forced_answer": "a", "is_forced": 1}) == "a"
    out = capsys.readouterr().out
    assert out.endswith("a\n")


def test_ask_is_forced_2_stille_modus(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("b\n"))
    assert ask("Tving", ["a", "b"], {"forced_answer": "a", "is_forced": 2}) == "a"
    assert capsys.readouterr().out == ""


def test_ask_any_key(monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("z\n"))
    assert ask("Trykk en tast") == "z"
