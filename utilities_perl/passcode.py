"""Interface to the ``pass code`` password store.

Python port of the Perl ``SH::PassCode`` and ``SH::PassCode::File`` modules.
These wrap the external `pass <https://www.passwordstore.org/>`_ tool together
with the `pass-code <https://github.com/alpernebbi/pass-code>`_ extension, so a
working ``pass``/``pass code`` installation is required at runtime.
"""

from __future__ import annotations

import os
import re
import subprocess
from typing import Any

OKEYS = ("filepath", "password", "changed", "username", "url", "comment", "extra")


def _password_dir() -> str:
    return os.environ.get("PASSWORD_STORE_DIR") or os.path.join(
        os.environ.get("HOME", ""), ".password-store"
    )


class PassCode:
    """Read-side interface to the pass code store."""

    def __init__(self, password_dir: str | None = None) -> None:
        self.password_dir = password_dir or _password_dir()

    def xsystem(self, command, stdin: str | None = None, config: dict | None = None):
        """Run an OS command, returning ``(stdout, stderr)``."""
        config = config or {}
        cmd = command if isinstance(command, (list, tuple)) else command.split(" ")
        proc = subprocess.run(
            cmd, input=stdin, capture_output=True, text=True
        )
        stdout, stderr = proc.stdout, proc.stderr.rstrip("\n")
        if stderr:
            if "is not in the password store." in stderr:
                stdout = None
            elif re.match(r"^gpg: (kryptert med|encrypted with)", stderr):
                stderr = ""
            elif re.search(r"bash: warning: setlocale", stderr):
                pass
            elif config.get("continue_on_error"):
                pass
            else:
                raise RuntimeError(f"OS command error: {' '.join(cmd)}\n{stderr}")
        return stdout, stderr

    def get_files(self, regex: str | None = None) -> dict[str, str]:
        """Return ``{friendly_name: real_name}`` from the passcode index."""
        out, _ = self.xsystem(
            ["gpg", "--decrypt", self.password_dir + "/.passcode.gpg"]
        )
        ret: dict[str, str] = {}
        for line in (out or "").split("\n"):
            if not line:
                continue
            real, _, friendly = line.partition(":")
            if not friendly:
                raise ValueError(f"Missing : in {line}")
            if regex and not re.search(regex, friendly):
                continue
            ret[friendly] = real
        return ret

    def list(self, path: str, sopts: dict | None = None) -> list[str]:
        """List friendly filenames and catalogs directly under ``path``."""
        sopts = sopts or {}
        files: dict[str, int] = {}
        for name in self.get_files():
            if name.startswith(path):
                tmp = name[len(path):].lstrip("/")
                if "/" in tmp:
                    tmp = tmp.split("/", 1)[0]
                elif sopts.get("dir_only"):
                    continue
                files[tmp] = files.get(tmp, 0) + 1
        return sorted(files)


class PassCodeFile:
    """A single password entry in the store."""

    def __init__(self, **kwargs: Any) -> None:
        for key in ("filepath", "password", "changed", "username", "url", "comment", "extra", "dir"):
            setattr(self, key, kwargs.get(key))

    @classmethod
    def okeys(cls) -> tuple[str, ...]:
        return OKEYS

    @property
    def pc(self) -> PassCode:
        return PassCode(password_dir=self.dir)

    @classmethod
    def from_file(cls, filepath: str, args: dict | None = None):
        """Return a :class:`PassCodeFile` for ``filepath`` or ``None`` if absent."""
        args = args or {}
        env = os.environ.copy()
        if args.get("dir"):
            env["PASSWORD_STORE_DIR"] = args["dir"]
        proc = subprocess.run(
            ["pass", "code", "show", filepath],
            capture_output=True, text=True, env=env,
        )
        stdout = proc.stdout
        if "is not in the password store." in (proc.stderr or ""):
            return None
        if not stdout:
            return None

        hash_: dict[str, Any] = {"filepath": filepath}
        key = None
        for line in stdout.split("\n"):
            if list(hash_.keys()) == ["filepath"]:
                hash_["password"] = line
                continue
            m = re.match(r"^(\w+):\s*(.*)", line)
            if m:
                key, value = m.group(1), m.group(2)
            else:
                value = line
            if key == "comment":
                hash_["comment"] = (hash_.get("comment") + "\n" if hash_.get("comment") else "") + value
            elif key in ("filepath", "username", "url", "changed"):
                hash_[key] = value.rstrip()
            else:
                extra = hash_.setdefault("extra", {})
                extra[key] = (extra.get(key) + "\n" if extra.get(key) else "") + value
        if args.get("dir"):
            hash_["dir"] = args["dir"]
        return cls(**hash_)

    def to_file(self, args: dict | None = None):
        """Write this entry back to the store (replacing any existing file)."""
        args = args or {}
        if self.password is None and self.url != "http://sn":
            raise ValueError("Missing password")
        cont = (self.password or "") + "\n"
        for key in ("filepath", "changed", "username", "url", "comment"):
            value = getattr(self, key)
            if value:
                cont += f"{key}: {value}\n"
        if self.extra:
            for key, value in self.extra.items():
                cont += f"{key}: {value}\n"
        env = os.environ.copy()
        dir_ = args.get("dir") or self.dir
        if dir_:
            env["PASSWORD_STORE_DIR"] = dir_
        subprocess.run(
            ["pass", "code", "insert", "-m", "-f", self.filepath],
            input=cont, capture_output=True, text=True, env=env,
        )
        return self

    def delete(self):
        """Remove this entry from the store."""
        if self.filepath is None:
            raise ValueError("filepath is undef")
        env = os.environ.copy()
        if self.dir:
            env["PASSWORD_STORE_DIR"] = self.dir
        subprocess.run(
            ["pass", "code", "rm", "-f", self.filepath],
            capture_output=True, text=True, env=env,
        )
        return PassCodeFile()
