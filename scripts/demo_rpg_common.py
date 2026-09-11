#!/usr/bin/env -S uv run --quiet --script --with utilities-perl-py@file://..
# /// script
# requires-python = ">=3.9"
# dependencies = ["PyYAML>=6.0", "utilities-perl-py"]
# [tool.uv.sources]
# utilities-perl-py = { path = ".." }
# ///
"""Demo av rpg_common-pakken.

Viser bruk av templatehjelpere og yaml_walk fra et eksternt repo
(path-basert installasjon).

Kjøring utenfra repoet:
    uv run --script --with "utilities-perl-py @ file://$PWD/.." scripts/demo_rpg_common.py
"""


from rpg_common import clist, ctable, get_tablename_keys_data, gterning, mytextsort

# Eksempel-data (tilsvarende det som ville kommet fra YAML-filer)
EVNER = [
    {"navn": "styrke", "pris": 2, "beskrivelse": "Fysisk styrke"},
    {"navn": "sanse", "pris": 1, "beskrivelse": "Sanseferdigheter"},
    {"navn": "kroppsbeherskelse", "pris": 1, "beskrivelse": "Kroppskontroll"},
    {"navn": "kjempe", "pris": 3, "beskrivelse": "Kampferdigheter"},
    {"navn": "mana", "pris": 2, "beskrivelse": "Magisk kraft"},
]

Klasser = [
    {"navn": "Kriger", "styrke": 3, "sanse": 1, "kroppsbeherskelse": 2, "kjempe": 3, "mana": 0},
    {"navn": "Trollmann", "styrke": 0, "sanse": 2, "kroppsbeherskelse": 1, "kjempe": 0, "mana": 3},
    {"navn": "Tyv", "styrke": 1, "sanse": 3, "kroppsbeherskelse": 3, "kjempe": 1, "mana": 0},
]


def main() -> None:
    print("=== rpg_common Demo ===\n")

    # 1. mytextsort
    print("--- mytextsort ---")
    sortert = mytextsort(["mana", "styrke", "sanse"], [e["navn"] for e in EVNER])
    print(f"Sortert: {sortert}\n")

    # 2. clist
    print("--- clist ---")
    liste = clist(EVNER, "evner")
    print(f"Liste: {liste}\n")

    # 3. ctable
    print("--- ctable ---")
    tabell = ctable(EVNER, "evner", columns=["navn", "pris", "beskrivelse"])
    print(tabell)
    print()

    # 4. gterning
    print("--- gterning ---")
    offset = 1
    for evne in EVNER:
        offset, text = gterning(1, offset, evne["pris"])
        print(f"  {evne['navn']}: terning {text}")
    print()

    # 5. yaml_walk
    print("--- yaml_walk (get_tablename_keys_data) ---")
    data = [
        {
            "tittel": "Atlantis",
            "tidsalder": "Gresk oldtid",
            "spill": [
                {
                    "spillernavn": "Anders",
                    "scener": [
                        {"navn": "Arm som veiver", "omgivelse": "hav"},
                    ],
                }
            ],
        }
    ]
    result = {}
    get_tablename_keys_data("sesjon", result, data)
    for tabellnavn, tabelldata in result.items():
        print(f"  Tabell: {tabellnavn}")
        print(f"    Felter: {tabelldata['fields']}")
        print(f"    Rader: {len(tabelldata['data'])}")
    print()

    # 6. load_rekkefoelge (eksempel med midlertidig fil)
    print("--- load_rekkefoelge ---")
    print("(Krever en rekkefoelge.list.yml-fil)")


if __name__ == "__main__":
    main()
