"""Read common (Mojolicious app) configuration files.

Python port of the Perl ``Model::GetCommonConfig`` module. Reads YAML config
from the directory in ``COMMON_CONFIG_DIR`` (default ``~/etc``) and assembles
the runtime config for a named app, including the hypnotoad section.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

import yaml


def _load_yaml(path: Path) -> Any:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


class GetCommonConfig:
    """Assemble per-app configuration from the common config directory."""

    def __init__(self, config_dir: str | os.PathLike | None = None, debug: bool = False) -> None:
        if config_dir is None:
            config_dir = (
                os.environ["COMMON_CONFIG_DIR"]
                if os.environ.get("COMMON_CONFIG_DIR")
                else os.path.join(os.environ.get("HOME", ""), "etc")
            )
        self.config_dir = Path(config_dir)
        self.debug = debug

    def get_mojoapp_config(self, filename: str, cfg: dict | None = None) -> dict[str, Any]:
        """Return the merged app config for the moniker derived from ``filename``."""
        cfg = cfg or {}
        moniker = Path(filename).name
        if moniker.endswith(".pl"):
            moniker = moniker[: -len(".pl")]
        file = self.config_dir / "mojoapp.yml"
        if not file.exists():
            raise FileNotFoundError(f"Common config file {file} does not exists")
        if cfg.get("debug") or self.debug:
            print(f"Configfile: {file}", file=os.sys.stderr)

        raw = _load_yaml(file)
        if not isinstance(raw, dict):
            raise ValueError(f"Empty config file in {file}")
        ret = dict(raw.get("common_config") or {})
        if "mojo_log_path" not in ret:
            raise ValueError(f"Missing mojo_log_path in common_config file {file}")

        if moniker in (raw.get("web_services") or {}):
            for key, value in raw["web_services"][moniker].items():
                ret[key] = value

        ret["moniker"] = moniker
        ret["mojo_log_path"] = str(
            Path(raw["common_config"]["mojo_log_path"]) / f"{moniker}.log"
        )
        secrets_dir = os.environ.get("COMMON_CONFIG_DIR") or os.path.join(
            os.environ.get("HOME", ""), "etc"
        )
        secrets_text = Path(secrets_dir, "secrets.txt").read_text(encoding="utf-8")
        ret["secrets"] = [s for s in secrets_text.split() if s]
        ret["hypnotoad"] = self._get_hypnotoad_config(moniker, cfg)

        oauth_google_fp = self.config_dir / "oauth2-google.yml"
        if oauth_google_fp.is_file():
            ret.setdefault("oauth2", {})["google"] = _load_yaml(oauth_google_fp)

        return ret

    def _get_hypnotoad_config(self, script: str, cfg: dict) -> dict[str, Any]:
        cfile = self.config_dir / "hypnotoad.yml"
        if cfg.get("debug"):
            print(f"hypnotoad Configfile: {cfile}", file=os.sys.stderr)
        raw = _load_yaml(cfile)
        ret = dict(raw.get("common_config") or {})
        web_services = raw.get("web_services") or {}
        if script in web_services:
            for key, value in web_services[script].items():
                if key == "port":
                    ret.setdefault("listen", []).append(f"http://127.0.0.1:{value}")
                else:
                    ret[key] = value
        else:
            raise ValueError(
                f"Missing config in file {cfile}:  web_services:->{script}:"
            )
        rundir = Path(os.environ.get("HOME", "")) / "run"
        rundir.mkdir(parents=True, exist_ok=True)
        ret["pid_file"] = str(rundir / f"{script}.pid")
        return ret
