import base64
import io

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
    import os

    cli.cmd_dump_email_hash([os.path.join(data_dir, "heisan.txt")])
    out = capsys.readouterr().out
    assert "header" in out
