"""Tester for rpg_common.yaml_walk -- speiler Perl-testene i get_tablename_keys_data.t."""

import pytest

from rpg_common.yaml_walk import get_tablename_keys_data


class TestGetTablenameKeysData:
    """Tester for get_tablename_keys_data-funksjonen."""

    def test_single_hash_with_scalar_values(self):
        """Enkelt HASH med skalare verdier."""
        r: dict = {}
        get_tablename_keys_data(
            "sesjon", r, {"tittel": "Atlantis", "tidsalder": "Gresk oldtid"}
        )

        assert "sesjon" in r
        assert sorted(r["sesjon"]["fields"]) == [
            "id",
            "id_root",
            "tidsalder",
            "tittel",
        ]
        assert r["sesjon"]["data"] == [
            {
                "id": 0,
                "id_root": 1,
                "tittel": "Atlantis",
                "tidsalder": "Gresk oldtid",
            }
        ]

    def test_nested_hash_becomes_child_table(self):
        """Nøstet HASH blir en barntabell med FK tilbake."""
        r: dict = {}
        get_tablename_keys_data(
            "sesjon",
            r,
            {"tittel": "Pirater", "info": {"var": "natt", "status": "ferdig"}},
        )

        assert "sesjon" in r
        assert "info" in r
        assert sorted(r["info"]["fields"]) == [
            "id",
            "id_sesjon",
            "status",
            "var",
        ]
        assert r["info"]["data"] == [
            {"id": 0, "id_sesjon": 0, "var": "natt", "status": "ferdig"}
        ]
        assert r["sesjon"]["data"][0]["id"] == 0
        assert r["sesjon"]["data"][0]["id_root"] == 1

    def test_array_of_hashes_becomes_child_table(self):
        """Array av HASHer blir en barntabell med en rad per element."""
        r: dict = {}
        get_tablename_keys_data(
            "sesjon",
            r,
            {
                "tittel": "Atlantis",
                "spill": [
                    {"spillernavn": "Anders"},
                    {"spillernavn": "Steinar"},
                    {"spillernavn": "Bjorn"},
                ],
            },
        )

        assert len(r["spill"]["data"]) == 3
        assert [row["spillernavn"] for row in r["spill"]["data"]] == [
            "Anders",
            "Steinar",
            "Bjorn",
        ]
        assert [row["id_sesjon"] for row in r["spill"]["data"]] == [0, 0, 0]

    def test_array_of_scalars_comma_joined(self):
        """Array av skalarer blir komma-slått sammen til ett felt."""
        r: dict = {}
        get_tablename_keys_data(
            "sesjon",
            r,
            {
                "tittel": "Pirater",
                "spilledere": ["Stein", "Icy"],
                "hjelpemidler": ["sverd", "skjold", "mat"],
            },
        )

        assert r["sesjon"]["data"][0]["spilledere"] == "Stein,Icy"
        assert r["sesjon"]["data"][0]["hjelpemidler"] == "sverd,skjold,mat"
        assert sorted(r["sesjon"]["fields"]) == [
            "hjelpemidler",
            "id",
            "id_root",
            "spilledere",
            "tittel",
        ]
        assert "spilledere" not in r
        assert "hjelpemidler" not in r

    def test_top_level_array_of_hashes(self):
        """Top-level array av HASHer -- det faktiske bruksområdet."""
        ds = [
            {"tittel": "Atlantis", "tidsalder": "Gresk oldtid"},
            {"tittel": "Pirater", "tidsalder": "Sjørøvertiden"},
        ]
        r: dict = {}
        get_tablename_keys_data("sesjon", r, ds)

        assert len(r["sesjon"]["data"]) == 2
        assert [row["tittel"] for row in r["sesjon"]["data"]] == [
            "Atlantis",
            "Pirater",
        ]
        assert [row["id"] for row in r["sesjon"]["data"]] == [0, 1]
        assert [row["id_root"] for row in r["sesjon"]["data"]] == [1, 1]

    def test_real_world_shape(self):
        """Realistisk form: sesjon -> spill -> scener."""
        ds = [
            {
                "tittel": "Atlantis",
                "tidsalder": "Gresk oldtid",
                "spill": [
                    {
                        "spillernavn": "Anders",
                        "scener": [
                            {"navn": "Arm som veiver", "omgivelse": "hav"},
                            {"navn": "Kjempekrabber", "omgivelse": "strand"},
                        ],
                    }
                ],
            }
        ]
        r: dict = {}
        get_tablename_keys_data("sesjon", r, ds)

        assert len(r["sesjon"]["data"]) == 1
        assert len(r["spill"]["data"]) == 1
        assert len(r["scener"]["data"]) == 2
        assert r["spill"]["data"][0]["id_sesjon"] == 0
        assert r["scener"]["data"][0]["id_spill"] == 0
        assert r["scener"]["data"][1]["id_spill"] == 0
        assert [row["navn"] for row in r["scener"]["data"]] == [
            "Arm som veiver",
            "Kjempekrabber",
        ]

    def test_fields_deduplicated_across_calls(self):
        """Felt deduperes på tvers av kall."""
        r: dict = {}
        get_tablename_keys_data(
            "sesjon", r, {"tittel": "A", "tidsalder": "x"}, "root", 1
        )
        get_tablename_keys_data(
            "sesjon", r, {"tittel": "B", "tidsalder": "y"}, "root", 1
        )

        assert len(r["sesjon"]["data"]) == 2
        seen: dict[str, int] = {}
        for field in r["sesjon"]["fields"]:
            seen[field] = seen.get(field, 0) + 1
        assert all(count == 1 for count in seen.values())

    def test_errors_invalid_return_ref(self):
        """TypeError når $return ikke er en dict."""
        with pytest.raises(TypeError, match="\\$return is not a HASH"):
            get_tablename_keys_data("t", [], {"x": 1}, "root", 1)

    def test_errors_unsupported_data(self):
        """TypeError når data er en streng (ikke dict/list)."""
        with pytest.raises(TypeError, match="Unsupported data ref"):
            get_tablename_keys_data("t", {}, "a bare string", "root", 1)

    def test_errors_array_of_array(self):
        """TypeError når data inneholder array-av-array."""
        with pytest.raises(TypeError, match="Unsupported ARRAY value"):
            get_tablename_keys_data(
                "t", {}, {"weird": [[1, 2], [3, 4]]}, "root", 1
            )
