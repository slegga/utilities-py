import sqlite3

from utilities_perl.transform import Transform
from utilities_perl.transform.importers import SQLiteTableImporter


def test_json_to_yaml(tmp_path, data_dir):
    out = tmp_path / "test.yaml"
    Transform().transform({"file": str(data_dir / "test.json")}, {"file": str(out)})
    assert out.exists()
    assert out.stat().st_size > 0


def test_csv_to_yaml(tmp_path, data_dir):
    out = tmp_path / "test2.yaml"
    Transform().transform(
        {"file": str(data_dir / "testdata.csv"), "sep_char": ","},
        {"file": str(out)},
    )
    assert out.exists()


def test_sqlitetable_to_yaml(tmp_path, data_dir):
    out = tmp_path / "test3.yaml"
    Transform().transform(
        {
            "type": "SQLiteTable",
            "file": str(data_dir / "testdata.db"),
            "table": "unittest",
        },
        {"file": str(out)},
    )
    assert out.exists()
    assert out.stat().st_size > 20


def test_sqlitetable_tabellnavn_med_unicode_og_sitatstegn(tmp_path):
    db = tmp_path / "spesial.db"
    tabell = 'tåbbel "æøå"'
    sitert = tabell.replace('"', '""')
    conn = sqlite3.connect(db)
    try:
        conn.execute(f'create table "{sitert}" (id integer, navn text)')
        conn.execute(f'insert into "{sitert}" values (1, ?)', ["ole"])  # noqa: S608
        conn.commit()
    finally:
        conn.close()
    rader = SQLiteTableImporter().importx({"file": str(db), "table": tabell})
    assert rader == [{"id": 1, "navn": "ole"}]


def test_sqlitetable_skjemakvalifisert_tabellnavn(tmp_path):
    db = tmp_path / "sikker.db"
    conn = sqlite3.connect(db)
    try:
        conn.execute("create table t (id integer)")
        conn.execute("insert into t values (7)")
        conn.commit()
    finally:
        conn.close()
    rader = SQLiteTableImporter().importx({"file": str(db), "table": "main.t"})
    assert rader == [{"id": 7}]
    assert SQLiteTableImporter().importx({"file": str(db), "table": "main . t"}) == [{"id": 7}]
