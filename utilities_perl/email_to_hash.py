"""Convert raw MIME email text into a structured dict.

Python port of the Perl ``SH::Email::ToHash`` module. The entry points are
:meth:`EmailToHash.msgtext2hash` (full message -> ``{header, body}``) and
:meth:`EmailToHash.parameterify` (a header/parameter block -> dict).
"""

from __future__ import annotations

import base64
import copy
import quopri
import re
from typing import Any


def _add(d: dict, key: str, value: Any) -> None:
    if key not in d:
        d[key] = value
    elif isinstance(d[key], list):
        d[key].append(value)
    else:
        d[key] = [d[key], value]


def _decode_qp(text: str, charset: str | None = None) -> str:
    raw = quopri.decodestring(text.encode("latin-1", "replace"))
    if charset and charset.upper() == "UTF-8":
        return raw.decode("utf-8", "replace")
    return raw.decode("latin-1", "replace")


def _decode_b64(text: str, charset: str | None = None) -> str:
    raw = base64.b64decode(text + "===")
    if charset and charset.upper() == "UTF-8":
        return raw.decode("utf-8", "replace")
    return raw.decode("latin-1", "replace")


class EmailToHash:
    """Parse raw email MIME text into nested dicts."""

    def __init__(self, tmpdir: str = "/tmp") -> None:
        self.tmpdir = tmpdir

    # -- header / parameter block parsing -------------------------------------

    def parameterify(self, *args: Any) -> dict | None:
        if not args or args[0] is None:
            return None
        string = "".join(a for a in args if a is not None)
        ret: dict[str, Any] = {}
        multiline = False
        k: str | None = None

        for line in string.split("\n"):
            if multiline:
                ret["content"] = ret.get("content", "") + line + "\n"
            elif re.match(r"^([\w\-]+):\s(.*)$", line):
                m = re.match(r"^([\w\-]+):\s(.*)$", line)
                k = m.group(1)
                _add(ret, k, m.group(2))
            elif re.match(r"^\s+", line):
                if re.match(r"^\s+$", line) and not multiline:
                    multiline = True
                    continue
                if k is None:
                    raise ValueError(f"ERROR LINE: '{line}'")
                if isinstance(ret[k], list):
                    ret[k][-1] = (ret[k][-1] or "") + "\n" + line
                else:
                    ret[k] = (ret[k] or "") + "\n" + line
            elif re.match(r"^([\w\-]+):$", line):
                k = re.match(r"^([\w\-]+):$", line).group(1)
                ret[k] = None
            elif not line:
                k = None
                multiline = True
            elif re.match(r"^\-\-\_.+\_$", line):
                k = None
            else:
                if line.startswith("From ") and len(ret) == 0:
                    ret["heading"] = ret.get("heading", "") + line
                elif re.match(r"^([\w\-]+):(\S.*)$", line):
                    m = re.match(r"^([\w\-]+):(\S.*)$", line)
                    k = m.group(1)
                    _add(ret, k, m.group(2))
                else:
                    multiline = True

        ret = self.hash_traverse(ret, self._split_semicolon)
        ret = self.hash_traverse(ret, self._extract_params)
        return ret

    @staticmethod
    def _split_semicolon(value: Any, key: str | None) -> tuple[Any, str]:
        if key and key == "Subject":
            return value, "continue"
        if (
            value
            and not isinstance(value, (dict, list))
            and key != "content"
            and ";" in value
            and not re.search(r'^[^"]*"[^"]*;.*"', value, re.S)
        ):
            return {"a": value.split(";")}, "next"
        return value, "continue"

    @staticmethod
    def _extract_params(v: Any, key: str | None) -> tuple[Any, str]:
        if isinstance(v, dict) and isinstance(v.get("a"), list):
            keep = []
            for item in v["a"]:
                m = re.match(r"^\s*([\w\-\_\s\(\)]+)\=(.*)\s*", item, re.S)
                if m:
                    v.setdefault("h", {})[m.group(1)] = m.group(2)
                else:
                    keep.append(item)
            if keep:
                v["a"] = keep
            else:
                del v["a"]
            return v, "next"
        return v, "continue"

    # -- full message parsing -------------------------------------------------

    def msgtext2hash(self, msg: str | None) -> dict | None:
        if not msg:
            return None
        ret: dict[str, Any] = {}
        msg = msg.replace("\r", "")
        header, _, body = msg.partition("\n\n")
        ret["header"] = self.parameterify(header)

        body_cont = body.split("\n")
        if body_cont and body_cont[0].startswith("--"):
            body = "".join(body_cont[i] + "\n" for i in range(1, len(body_cont) - 1))

        header_d = ret["header"] or {}
        if "Content-Type" in header_d:
            ctv = header_d["Content-Type"]
            if not isinstance(ctv, (dict, list)):
                body = {"content": body, "Content-Type": ctv}
            elif (
                isinstance(ctv, dict)
                and "a" in ctv
                and re.match(r"^multipart", ctv["a"][0])
            ):
                body = self.multipart(ctv, body)
            elif (
                isinstance(ctv, dict)
                and ctv.get("a", [None])[0]
                and (
                    not isinstance(body, dict)
                    or not body.get("Content-Type")
                )
            ):
                body = {"content": body, "Content-Type": ctv}

        cte = header_d.get("Content-Transfer-Encoding")
        if cte and (not isinstance(body, dict) or not body.get("Content-Transfer-Encoding")):
            if not isinstance(body, dict):
                body = {"content": body}
            body["Content-Transfer-Encoding"] = cte

        if not isinstance(body, dict):
            ret["body"] = self.parameterify(body)
        else:
            ret["body"] = body

        return self.hash_traverse(ret, self._decode_content)

    def _decode_content(self, v: Any, key: str | None) -> tuple[Any, str]:
        if v and not isinstance(v, (dict, list)):
            if re.search(r"^\=.*\?\=", v) or key == "content":
                v = re.sub(
                    r"\=\?iso\-8859\-1\?Q\?(.+?)\?\=",
                    lambda m: _decode_qp(m.group(1)),
                    v,
                    flags=re.I,
                )
                v = re.sub(
                    r"\=\?iso\-8859\-1\?B\?(.+?)\?\=",
                    lambda m: _decode_b64(m.group(1)),
                    v,
                    flags=re.I,
                )
                v = re.sub(
                    r"\=\?UTF-8\?B\?(.+?)\?\=",
                    lambda m: _decode_b64(m.group(1), "UTF-8"),
                    v,
                    flags=re.I,
                )
                v = re.sub(
                    r"\=\?UTF-8\?Q\?(.+?)\?\=",
                    lambda m: _decode_qp(m.group(1), "UTF-8"),
                    v,
                    flags=re.I,
                )
            return v, "next"

        if key == "body" and isinstance(v, dict) and v.get("Content-Type"):
            ct = v["Content-Type"]
            if isinstance(ct, dict) and re.match(r"^multipart", ct.get("a", [""])[0], re.I):
                v["content"] = self.multipart(ct, v.get("body"))
            else:
                charset = ""
                if isinstance(ct, dict) and ct.get("h", {}).get("charset"):
                    charset = ct["h"]["charset"]
                charset = re.sub(r'^["\']|["\']$', "", charset)
                if v.get("Content-Transfer-Encoding"):
                    cte = v["Content-Transfer-Encoding"].lower().strip()
                    cte = re.sub(r"[.;,]+$", "", cte)
                    if cte == "quoted-printable":
                        v["content"] = _decode_qp(v.get("content", ""), charset or None)
                    elif cte == "base64":
                        v["content"] = _decode_b64(v.get("content", ""), charset or None)
                    elif cte in ("7bit",):
                        pass
                    elif cte in ("8bit", "binary"):
                        if charset.upper() == "UTF-8":
                            v["content"] = v.get("content", "")
                elif (
                    isinstance(ct, dict)
                    and ct.get("h", {}).get("charset")
                    and ct["h"]["charset"].upper() == "UTF-8"
                ):
                    pass
                return v, "next"
        return v, "continue"

    # -- helpers --------------------------------------------------------------

    def hash_traverse(self, hash_in: Any, sub, key: str | None = None) -> Any:
        hash_ = copy.deepcopy(hash_in)
        x, status = sub(hash_, key)
        if status == "next":
            return x
        if isinstance(hash_, dict):
            for k in list(hash_.keys()):
                hash_[k] = self.hash_traverse(hash_[k], sub, k)
        elif isinstance(hash_, list):
            for i in range(len(hash_)):
                hash_[i] = self.hash_traverse(hash_[i], sub, "ARRAY")
        return hash_

    def extract_emailaddress(self, from_: Any) -> str | None:
        if not from_:
            return None
        if isinstance(from_, list):
            from_ = next((x for x in from_ if "@" in x), None)
        elif isinstance(from_, dict):
            if len(from_) == 1:
                from_ = next(iter(from_.values()))
            else:
                raise NotImplementedError("Unexpected From structure")
        if not from_ or "@" not in from_:
            raise ValueError("Cant find email address")
        m = re.search(r"\<([\w\.\_\-\+]+\@[\w\.\_\-]+)>", from_)
        if m:
            return m.group(1)
        return from_

    def multipart(self, type_: Any, body: str | None) -> str | None:
        if not isinstance(type_, dict):
            raise ValueError("Content-Type is not a reference")
        if not re.match(r"^multipart", type_["a"][0], re.I):
            raise ValueError("Content-Type not like multipart")
        if "boundary" not in type_.get("h", {}):
            raise ValueError("Missing boundary in Content-Type")

        boundary = re.escape(type_["h"]["boundary"])
        tmptype = type_["a"][0].lower()
        if tmptype in ("multipart/alternative", "multipart/mixed", "multipart/related"):
            if not body:
                return None
            parts = re.split(boundary, body, maxsplit=1)
            body = parts[0]
            rest = parts[1] if len(parts) > 1 else ""
            if not body or not re.search(r"\w", body):
                pieces = re.split(boundary, rest, maxsplit=1)
                body = pieces[1] if len(pieces) > 1 else None
            return body
        if tmptype == "multipart/report":
            return None
        if tmptype in ("multipart/digest", "multipart/parallel"):
            raise NotImplementedError(f"{tmptype} not handled")
        raise NotImplementedError(f"Unhandled multipart {type_['a'][0]}")
