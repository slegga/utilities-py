"""Tester for rpg_common.template -- ctable, clist, mytextsort, myrowsort, gterning."""

import pytest

from rpg_common.template import (
    clist,
    ctable,
    gterning,
    load_rekkefoelge,
    myrowsort,
    mytextsort,
)

REKKEFOELGE = ["styrke", "sanse", "kroppsbeherskelse", "kjempe", "mana"]


class TestMytextsort:
    def test_sorterer_etter_rekkefoelge(self):
        result = mytextsort(["mana", "styrke", "sanse"], REKKEFOELGE)
        assert result == ["styrke", "sanse", "mana"]

    def test_ukjente_elementer_plasseres_sist(self):
        result = mytextsort(["ukjent", "styrke", "zulu"], REKKEFOELGE)
        assert result[0] == "styrke"
        assert "ukjent" in result[1:]
        assert "zulu" in result[1:]

    def test_tom_liste(self):
        assert mytextsort([], REKKEFOELGE) == []

    def test_ett_element(self):
        assert mytextsort(["mana"], REKKEFOELGE) == ["mana"]


class TestMyrowsort:
    def test_sorterer_etter_rekkefoelge(self):
        data = {
            "b": {"navn": "B"},
            "a": {"navn": "A"},
        }
        result = myrowsort(data, ["a", "b"])
        assert result == ["a", "b"]

    def test_sorterer_etter_kolonne(self):
        data = {
            "rolle1": {"styrke": "3"},
            "rolle2": {"styrke": "1"},
            "rolle3": {"styrke": "2"},
        }
        result = myrowsort(data, REKKEFOELGE, sort_columns=["styrke"])
        assert result == ["rolle2", "rolle3", "rolle1"]

    def test_fallback_til_rekkefoelge(self):
        data = {
            "mana": {"navn": "Mana"},
            "styrke": {"navn": "Styrke"},
        }
        result = myrowsort(data, REKKEFOELGE)
        assert result == ["styrke", "mana"]


class TestCtable:
    def test_enkel_tabell(self):
        data = [
            {"navn": "Styrke", "verdi": "3"},
            {"navn": "Sanse", "verdi": "2"},
        ]
        result = ctable(data, "evner")
        assert "|evner|" in result
        assert "|Styrke|" in result
        assert "|Sanse|" in result
        assert "-|-" in result

    def test_tom_data(self):
        assert ctable([], "evner") == ""

    def test_kolonne_rekkefoelge(self):
        data = [{"mana": "5", "styrke": "3", "sanse": "2"}]
        result = ctable(data, "evner", columns=["styrke", "sanse", "mana"])
        lines = result.split("\n")
        header = lines[0]
        cols = [c.strip() for c in header.split("|") if c.strip()]
        assert cols == ["styrke", "sanse", "mana"]

    def test_beregnede_kolonner(self):
        data = [{"navn": "A", "pris": 2, "antall": 3}]
        calculated = {"sum": lambda cat, row: row["pris"] * row["antall"]}
        result = ctable(data, "evner", columns=["navn", "pris", "antall", "sum"], calculated=calculated)
        assert "|6|" in result


class TestClist:
    def test_enkel_liste(self):
        data = [{"navn": "A"}, {"navn": "B"}, {"navn": "C"}]
        result = clist(data, "evner")
        assert result == "A, B og C"

    def test_ett_element(self):
        data = [{"navn": "Alene"}]
        result = clist(data, "evner")
        assert result == "Alene"

    def test_to_elementer(self):
        data = [{"navn": "A"}, {"navn": "B"}]
        result = clist(data, "evner")
        assert result == "A og B"

    def test_bruker_rekkefoelge(self):
        data = [{"navn": "mana"}, {"navn": "styrke"}, {"navn": "sanse"}]
        result = clist(data, "evner", rekkefoelge=REKKEFOELGE)
        assert result == "styrke, sanse og mana"

    def test_annet_bindord(self):
        data = [{"navn": "A"}, {"navn": "B"}, {"navn": "C"}]
        result = clist(data, "evner", bindword="eller")
        assert result == "A, B eller C"


class TestGterning:
    def test_enkelttall(self):
        offset, text = gterning(1, 1, 1)
        assert offset == 2
        assert text == "1"

    def test_omraade(self):
        offset, text = gterning(1, 1, 3)
        assert offset == 4
        assert text == "1-3"

    def test_fortsetter_fra_offset(self):
        offset1, text1 = gterning(1, 1, 2)
        offset2, text2 = gterning(1, offset1, 1)
        assert offset1 == 3
        assert text1 == "1-2"
        assert offset2 == 4
        assert text2 == "3"

    def test_feil_ved_range_mindre_enn_1(self):
        with pytest.raises(ValueError, match="range is less than 1"):
            gterning(1, 1, 0)


class TestLoadRekkefoelge:
    def test_laster_fil(self, tmp_path):
        yml = tmp_path / "rekkefoelge.list.yml"
        yml.write_text("- alpha\n- beta\n- gamma\n", encoding="utf-8")
        result = load_rekkefoelge(yml)
        assert result == ["alpha", "beta", "gamma"]

    def test_mangler_fil(self, tmp_path):
        result = load_rekkefoelge(tmp_path / "finnes_ikke.yml")
        assert result == []

    def test_ugyldig_yaml_dict_i_stedet_for_liste(self, tmp_path):
        yml = tmp_path / "rekkefoelge.list.yml"
        yml.write_text("key: value\nother: data\n", encoding="utf-8")
        result = load_rekkefoelge(yml)
        assert result == []

    def test_ikke_streng_elementer_konverteres_til_streng(self, tmp_path):
        yml = tmp_path / "rekkefoelge.list.yml"
        yml.write_text("- 1\n- 2\n- 3\n", encoding="utf-8")
        result = load_rekkefoelge(yml)
        assert result == ["1", "2", "3"]
