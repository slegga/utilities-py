"""Send notifications through a GroupMe bot.

Python port of the Perl ``SH::Alert`` module. Reads a YAML config describing
GroupMe bots and posts a message via the GroupMe bot API.
"""

from __future__ import annotations

import getpass
import json
import os
import socket
import urllib.request
from pathlib import Path
from typing import Any

import yaml

DEFAULT_URL = "https://api.groupme.com/v3/bots/post"


class Alert:
    """GroupMe bot notifier."""

    def __init__(
        self,
        configfile: str | os.PathLike | None = None,
        dryrun: bool = False,
        url: str = DEFAULT_URL,
    ) -> None:
        if configfile is None:
            base = os.environ.get("CONFIG_DIR") or os.path.join(
                os.environ.get("HOME", ""), "etc"
            )
            configfile = os.path.join(base, "groupme-bot.yml")
        self.configfile = Path(configfile)
        self.dryrun = dryrun
        self.url = url
        self._config: dict[str, Any] | None = None

    @property
    def config(self) -> dict[str, Any]:
        if self._config is None:
            with open(self.configfile, encoding="utf-8") as fh:
                self._config = yaml.safe_load(fh)
        return self._config

    def groupme(self, message: str, bot: str | None = None) -> bool | None:
        """Send ``message`` to GroupMe via ``bot`` (defaults to ``default_bot``)."""
        import re

        if not re.search(r"\w", message or ""):
            return None
        bot = bot or self.config.get("default_bot")
        bot_id = self.config["bots"][bot]["bot_id"]
        short_hostname = socket.gethostname().split(".")[0]
        identity = f"{getpass.getuser()}@{short_hostname}: "
        payload = {"bot_id": bot_id, "text": identity + message}

        if self.dryrun:
            print("DryRun no communication with api.groupme.com")
            print(json.dumps(payload) + self.url)
            return None

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.url, data=data, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as resp:
            code = resp.getcode()
            if 200 <= code < 300:
                return True
            if code == 404:
                raise RuntimeError(f"404 Path not found '{self.url}'")
            raise RuntimeError(f"Error: HTTP {code}")
