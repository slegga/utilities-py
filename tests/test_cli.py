import base64
import io

import pytest
import yaml

from utilities_perl import cli


def test_alert_dryrun(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("server is on fire\n"))
    rc = cli.cmd_alert(["--dryrun"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "DRYRUN" in out
    assert "server is on fire" in out


def test_alert_ignore(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("noise to ignore\n"))
    rc = cli.cmd_alert(["--dryrun", "--ignore", "ignore"])
    out = capsys.readouterr().out
    assert rc == 0
    assert out == ""


def test_b64d(capsysbinary):
    cli.cmd_b64d([base64.b64encode(b"hello").decode()])
    out = capsysbinary.readouterr().out
    assert out.startswith(b"hello")


def test_unixtid_epoch(capsys):
    cli.cmd_unixtid(["0"])
    out = capsys.readouterr().out.strip()
    assert out == "1970-01-01 00:00:00"


def test_unixtid_now(capsys):
    cli.cmd_unixtid([])
    out = capsys.readouterr().out.strip()
    assert out.isdigit()


def test_dump_email_hash(capsys, data_dir):
    cli.cmd_dump_email_hash([str(data_dir / "heisan.txt")])
    out = capsys.readouterr().out
    assert "header" in out


def test_should_follow_link_beholder_gammel_oppforsel():
    assert cli._should_follow_link(".", "mappe/lenke", False) is True
    assert cli._should_follow_link("", "mappe/lenke", False) is False
    assert cli._should_follow_link(".", "mappe/lenke", True) is False
    assert cli._should_follow_link("mappe/lenke", "mappe/lenke", False) is False
    assert cli._should_follow_link("mappe", "mappe/lenke", False) is True


def test_file_rights_debug_symlink_til_punktum(tmp_path, capsys):
    lenke = tmp_path / "lenke"
    lenke.symlink_to(".")
    rc = cli.cmd_file_rights_debug([str(lenke)])
    out = capsys.readouterr().out
    assert rc == 0
    assert str(lenke) in out


def test_ensure_destination_eksisterende_katalog(tmp_path):
    cli._ensure_destination(str(tmp_path), None)


def test_ensure_destination_mangler_uten_mount_cmd(tmp_path):
    with pytest.raises(SystemExit, match="is not a directory"):
        cli._ensure_destination(str(tmp_path / "mangler"), {"uten": "mount_cmd"})


def test_ensure_destination_kjorer_mount_cmd(tmp_path, monkeypatch):
    dest = tmp_path / "mnt"

    def fake_run(*_args, **_kwargs):
        dest.mkdir()

    monkeypatch.setattr(cli.subprocess, "run", fake_run)
    cli._ensure_destination(str(dest), {"mount_cmd": "mount eksempel"})
    assert dest.is_dir()


def test_ensure_destination_mount_mislykkes(tmp_path, monkeypatch):
    monkeypatch.setattr(cli.subprocess, "run", lambda *_args, **_kwargs: None)
    with pytest.raises(SystemExit, match="did not mount"):
        cli._ensure_destination(str(tmp_path / "mnt"), {"mount_cmd": "mount eksempel"})


def test_forward_file_oppretter_katalog(tmp_path):
    src = tmp_path / "kilde"
    src.mkdir()
    dst = tmp_path / "maal"
    cli._forward_file(str(src), str(dst), "kilde")
    assert dst.is_dir()


def test_forward_file_kopierer_fil(tmp_path, capsys):
    src = tmp_path / "f.txt"
    src.write_text("innhold", encoding="utf-8")
    dst = tmp_path / "kopi.txt"
    cli._forward_file(str(src), str(dst), "f.txt")
    out = capsys.readouterr().out
    assert dst.read_text(encoding="utf-8") == "innhold"
    assert "has been copied" in out


def test_forward_file_hopper_over_ulaskbar_like_fil(tmp_path, capsys, monkeypatch):
    src = tmp_path / "f.txt"
    src.write_text("innhold", encoding="utf-8")
    dst = tmp_path / "kopi.txt"
    dst.write_text("gammelt", encoding="utf-8")
    monkeypatch.setattr(cli.os, "access", lambda *_args, **_kwargs: False)
    cli._forward_file(str(src), str(dst), "f.txt")
    out = capsys.readouterr().out
    assert "Do notthing" in out
    assert dst.read_text(encoding="utf-8") == "gammelt"


def test_cmd_file_forwarder(tmp_path, capsys):
    srcdir = tmp_path / "kilde"
    (srcdir / "under").mkdir(parents=True)
    (srcdir / "a.txt").write_text("a", encoding="utf-8")
    (srcdir / "under" / "b.txt").write_text("b", encoding="utf-8")
    dstdir = tmp_path / "maal"
    dstdir.mkdir()
    etc = tmp_path / "etc"
    etc.mkdir()
    cfg = {str(srcdir): {str(dstdir): None}}
    (etc / "file-forwarder.cfg.yml").write_text(yaml.safe_dump(cfg), encoding="utf-8")

    rc = cli.cmd_file_forwarder(["--homedir", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 0
    assert (dstdir / "a.txt").read_text(encoding="utf-8") == "a"
    assert (dstdir / "under" / "b.txt").read_text(encoding="utf-8") == "b"
    assert "has been copied" in out

    rc = cli.cmd_file_forwarder(["--homedir", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "has been copied" not in out
