"""Tile/arrange windows on Linux using ``wmctrl``.

Python port of the Perl ``bin/winord`` script. Linux/X11 only — requires the
``wmctrl`` command. Reads the current windows, computes new geometry depending
on how many there are (or ``--split``/``--horizontal``), then moves them.
"""

from __future__ import annotations

import argparse
import math
import re
import subprocess


class WinOrd:
    def __init__(self, split: int | None = None, horizontal: bool = False, info: bool = False) -> None:
        self.split = split
        self.horizontal = horizontal
        self.info = info
        self.x_min = 0
        self.y_min = 0
        self.x_max = 0
        self.y_max = 0
        self.windows: list[dict] = []

    def get_info(self):
        resraw = subprocess.run(
            "wmctrl -d", shell=True, capture_output=True, text=True
        ).stdout
        active = next((l for l in resraw.splitlines() if "*" in l), "")
        m = re.search(r"WA:.+?(\d+)x(\d+)", active)
        x_res, y_res = (int(m.group(1)), int(m.group(2))) if m else (0, 0)
        self.x_min = 0
        self.y_min = 0
        self.x_max = x_res
        self.y_max = y_res - 36

        wmctrl = subprocess.run(
            "wmctrl -Gl", shell=True, capture_output=True, text=True
        ).stdout
        rows = [re.split(r"\s+", line, 7) for line in wmctrl.splitlines()]
        screens: list[dict] = []
        for r in sorted(rows, key=lambda r: r[7] if len(r) > 7 else "", reverse=True):
            if len(r) < 8 or int(r[1]) == -1:
                continue
            desk = int(r[1])
            while len(screens) <= desk:
                screens.append({})
            screens[desk][r[0]] = {"x_pos": int(r[2]), "y_pos": int(r[3])}
        self.windows = screens
        return self

    def do_resize(self):
        i = 0
        for screen in self.windows:
            if not screen:
                continue
            for key, value in screen.items():
                resize = (
                    f'wmctrl -r "{key}" -b remove,above,fullscreen,sticky,'
                    f"maximized_vert,maximized_horz -e {i},"
                    f"{value['x_pos']},{value['y_pos']},{value['x_size']},{value['y_size']}"
                )
                print(resize)
                subprocess.run(resize, shell=True)
            i += 1

    def main(self):
        self.get_info()
        for screen in self.windows:
            if not screen:
                continue
            win = screen
            num_win = len(win)
            if self.split and self.split > 0:
                num_win = self.split
            if self.horizontal:
                tot = self.split or len(win)
                for i, key in enumerate(sorted(win)):
                    win[key]["x_pos"] = (tot - 1 - i) * int((self.x_min + self.x_max) / tot)
                    win[key]["y_pos"] = self.y_min
                    win[key]["x_size"] = int((self.x_max - self.x_min) / num_win)
                    win[key]["y_size"] = self.y_max - self.y_min
            else:
                for i, key in enumerate(sorted(win)):
                    win[key]["x_pos"] = self.x_min + (i % num_win) * int(
                        (self.x_max - self.x_min) / num_win
                    )
                    win[key]["y_pos"] = self.y_min
                    win[key]["x_size"] = int((self.x_max - self.x_min) / max(num_win, 1))
                    win[key]["y_size"] = self.y_max - self.y_min
        self.do_resize()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="winord", description="Order windows in the window manager")
    parser.add_argument("--info", action="store_true", help="Show windows info")
    parser.add_argument("--split", type=int, help="Set number of windows")
    parser.add_argument("--horizontal", action="store_true", help="Only split on a row")
    args = parser.parse_args(argv)
    WinOrd(split=args.split, horizontal=args.horizontal, info=args.info).main()
    return 0
