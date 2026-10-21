import io
import time

import pytest

from utilities_perl.passcode import PassCodeFile
from utilities_perl.transform.exporters import PassCodeExporter

FAKE_PASSWORD = "gammelt_passord"


def test_lastpass_entry_grunnleggende():
    row = {
        "grouping": "privat",
        "name": "konto",
        "password": "p",
        "username": "u",
        "url": "https://x",
        "totp": "123456",
        "fav": 1,
        "extra": "notat",
    }
    entry = PassCodeExporter()._lastpass_entry(row, {})
    assert entry == {
        "filepath": "privat/konto",
        "password": "p",
        "username": "u",
        "url": "https://x",
        "changed": time.strftime("%Y-%m-%d"),
        "comment": "notat,totp:123456,fav:1",
    }


def test_lastpass_entry_uten_grouping_og_med_dir():
    entry = PassCodeExporter()._lastpass_entry({"name": "konto"}, {"dir": "/butikk"})
    assert entry["filepath"] == "konto"
    assert entry["dir"] == "/butikk"
    assert entry["comment"] is None


def test_lastpass_entry_jobb_mappe_omskrives():
    entry = PassCodeExporter()._lastpass_entry({"grouping": "Min Jobb mappe", "name": "konto"}, {})
    assert entry["filepath"] == "jobb/konto"


def test_lastpass_entry_jobb_mappe_med_sluttende_skrastrek():
    entry = PassCodeExporter()._lastpass_entry({"grouping": "Min Jobb", "name": ""}, {})
    assert entry["filepath"] == "jobb/"


def test_lastpass_entry_mangler_filnavn():
    assert PassCodeExporter()._lastpass_entry({"name": ""}, {}) is None
    with pytest.raises(ValueError, match="Missing file path"):
        PassCodeExporter()._lastpass_entry({"name": "", "password": "p"}, {})


def test_format_lastpass_rows_filtrerer_ut_tomme_rader():
    rader = PassCodeExporter()._format_lastpass_rows([{"name": "a"}, {"name": ""}], {})
    assert [rad["filepath"] for rad in rader] == ["a"]


def test_format_lastpass_rows_feiler_paa_ukjent_nokkel():
    with pytest.raises(ValueError, match="Unknown key: bogus in Last Pass format"):
        PassCodeExporter()._format_lastpass_rows([{"name": "a", "bogus": 1}], {})


def test_passordfil_entry_grunnleggende():
    row = {
        "SYSTEM": "https://example.com/min side",
        "GRUPPERING": "jobb",
        "DOMENE": "eksempel",
        "PASSORD": "p",
        "BRUKER": "u",
        "URL": "https://example.com",
        "BESKRIVELSE": "b",
        "BYTTE": "2020-01-01",
    }
    entry = PassCodeExporter()._passordfil_entry(row, {})
    assert entry == {
        "filepath": "jobb/example.com",
        "password": "p",
        "username": "u",
        "url": "https://example.com",
        "changed": "2020-01-01",
        "comment": "b",
    }


def test_passordfil_entry_bruker_domene_uten_gruppering():
    entry = PassCodeExporter()._passordfil_entry({"SYSTEM": "navn", "DOMENE": "eksempel"}, {})
    assert entry["filepath"] == "eksempel/navn"


def test_passordfil_entry_mangler_kildenavn():
    with pytest.raises(ValueError, match="missing filename source"):
        PassCodeExporter()._passordfil_entry({"DOMENE": "d"}, {})


def test_passordfil_entry_tomt_filnavn_hoppes_over():
    assert PassCodeExporter()._passordfil_entry({"SYSTEM": "///"}, {}) is None
    with pytest.raises(ValueError, match="No filename"):
        PassCodeExporter()._passordfil_entry({"SYSTEM": "///", "password": "p"}, {})


def test_format_passordfil_rows_filtrerer_og_feiler_paa_ukjent_nokkel():
    rader = PassCodeExporter()._format_passordfil_rows(
        [{"SYSTEM": "a", "DOMENE": "d"}, {"SYSTEM": "///"}], {}
    )
    assert [rad["filepath"] for rad in rader] == ["d/a"]
    with pytest.raises(ValueError, match="Unknown key: bogus in passordfil format"):
        PassCodeExporter()._format_passordfil_rows([{"SYSTEM": "a", "bogus": 1}], {})


def _monkeypatch_passcodefil(monkeypatch, existing, lagret):
    def fake_from_file(_cls, _filepath, _args=None):
        return existing

    def fake_to_file(self, _args=None):
        lagret.append(self)
        return self

    monkeypatch.setattr(PassCodeFile, "from_file", classmethod(fake_from_file))
    monkeypatch.setattr(PassCodeFile, "to_file", fake_to_file)


def test_export_lagrer_ny_rad(monkeypatch):
    lagret: list = []
    _monkeypatch_passcodefil(monkeypatch, None, lagret)
    PassCodeExporter().export({}, [{"name": "konto", "password": "p"}])
    assert [f.filepath for f in lagret] == ["konto"]


def test_keep_edit_file_2_skriver_nytt_filnavn(monkeypatch):
    existing = PassCodeFile(filepath="mappe/gammelt", password=FAKE_PASSWORD)
    lagret: list = []
    _monkeypatch_passcodefil(monkeypatch, existing, lagret)
    monkeypatch.setattr("sys.stdin", io.StringIO("e\nnytt navn\n"))

    f = {"filepath": "mappe/gammelt", "password": "nytt_passord"}
    PassCodeExporter()._check_duplicate_and_store_file(f, {})
    assert f["filepath"] == "mappe/nytt navn"
    assert existing.filepath == "mappe/nytt navn"
    assert existing.password == "nytt_passord"
    assert lagret == [existing]


def test_keep_edit_file_2_absolutt_navn_blir_under_mappen(monkeypatch):
    existing = PassCodeFile(filepath="mappe/gammelt", password=FAKE_PASSWORD)
    lagret: list = []
    _monkeypatch_passcodefil(monkeypatch, existing, lagret)
    monkeypatch.setattr("sys.stdin", io.StringIO("e\n/etc/passwd\n"))

    f = {"filepath": "mappe/gammelt", "password": "nytt_passord"}
    PassCodeExporter()._check_duplicate_and_store_file(f, {})
    assert f["filepath"] == "mappe//etc/passwd"
