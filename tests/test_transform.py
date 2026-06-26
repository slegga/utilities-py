import os

from utilities_perl.transform import Transform


def test_json_to_yaml(tmp_path, data_dir):
    out = tmp_path / "test.yaml"
    Transform().transform({"file": os.path.join(data_dir, "test.json")}, {"file": str(out)})
    assert out.exists()
    assert out.stat().st_size > 0


def test_csv_to_yaml(tmp_path, data_dir):
    out = tmp_path / "test2.yaml"
    Transform().transform(
        {"file": os.path.join(data_dir, "testdata.csv"), "sep_char": ","},
        {"file": str(out)},
    )
    assert out.exists()


def test_sqlitetable_to_yaml(tmp_path, data_dir):
    out = tmp_path / "test3.yaml"
    Transform().transform(
        {"type": "SQLiteTable", "file": os.path.join(data_dir, "testdata.db"), "table": "unittest"},
        {"file": str(out)},
    )
    assert out.exists()
    assert out.stat().st_size > 20
