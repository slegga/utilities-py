import os
import re

import pytest

from utilities_perl.email_to_hash import EmailToHash

HEADER = """From root  Sun Mar 15 09:32:20 2020
Return-Path: <norwegian@mailgb.custhelp.com>
Content-Type: Multipart/Alternative;
  boundary="------------Boundary-00=_OP78VA40000000000000"
From: "Norwegian Customer Relations"
    <customer.relations@norwegian.com>
Reply-To: "Norwegian Customer Relations"
    <customer.relations@norwegian.com>
To: steihamm@online.no
Date: Sun, 15 Mar 2020 09:32:12 +0100 (CET)
Subject: Cancelled flight claim for booking reference MJGH76 - Flight  DY1817 LPA-OSL 24.02.20 [Incident: 200307-001033]
"""


def test_parameterify_content_type():
    parsed = EmailToHash().parameterify(HEADER)
    assert parsed["Content-Type"] == {
        "a": ["Multipart/Alternative"],
        "h": {"boundary": '"------------Boundary-00=_OP78VA40000000000000"'},
    }


def _txt_files(data_dir):
    return [f for f in os.listdir(data_dir) if f.endswith(".txt")]


def test_msgtext2hash_all_data_files(data_dir):
    parser = EmailToHash()
    files = _txt_files(data_dir)
    assert files, "expected sample email files"
    for fname in files:
        path = os.path.join(data_dir, fname)
        with open(path, encoding="utf-8", errors="replace") as fh:
            content = fh.read()
        cont = parser.msgtext2hash(content)
        assert "Content-Type" in cont["header"], fname
        from_ = cont["header"].get("From")
        froms = from_ if isinstance(from_, list) else [from_]
        for value in froms:
            assert re.search(r"(no|com|shop|net)", value), (fname, value)
