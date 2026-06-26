"""Ask the user questions on the terminal.

Python port of the Perl ``SH::Ask`` module. The public entry point is
:func:`ask`. Input is read from stdin; supports a list of valid choices or a
compiled regular expression, an optional default/forced answer and a "remember
last answer" mode.
"""

from __future__ import annotations

import getpass
import re
import sys
from typing import Pattern, Sequence

_answer_defaults: dict[str, str] = {}


def ask(question: str, choices=None, options: dict | None = None) -> str | None:
    """Ask ``question`` and return the user's answer.

    Args:
        question: Text to show the user.
        choices: A sequence of acceptable answers, or a compiled regex the
            answer must fully match. ``None`` means "press any key to continue".
        options: Optional dict with keys ``exit_on_nochoice`` (0 repeat, 1 stop,
            2 continue), ``forced_answer``, ``is_forced`` (0 user, 1 auto,
            2 auto+quiet), ``remember`` and ``secret``.
    """
    options = options if isinstance(options, dict) else None
    default = None
    if options:
        if "forced_answer" in options:
            default = options["forced_answer"]
        elif options.get("remember") and question in _answer_defaults:
            default = _answer_defaults[question]

    answer: str | None = None

    if choices is None and options is None:
        # "Press any key to continue" style question.
        sys.stdout.write(question)
        sys.stdout.flush()
        answer = _read_single_key()
        sys.stdout.write("\n")
    elif choices is not None:
        is_regex = isinstance(choices, (re.Pattern,))
        while True:
            quiet = options and options.get("is_forced") == 2
            if not quiet:
                sys.stdout.write(f"{question} ")
                if is_regex:
                    sys.stdout.write(choices.pattern)
                else:
                    sys.stdout.write("(" + ",".join(str(c) for c in choices) + ")")
                if default:
                    sys.stdout.write(f"[{default}]")
                sys.stdout.write("? ")
                sys.stdout.flush()

            user_in_control = not (options and options.get("is_forced"))
            if user_in_control:
                answer = _ask_stdin(options.get("secret") if options else None)
                if is_regex:
                    if re.match(f"^{choices.pattern}$", answer.lower()):
                        break
                    matched = False
                else:
                    matched = any(answer.lower() == str(c).lower() for c in choices)
                    if matched:
                        break
                if not matched:
                    if options and options.get("exit_on_nochoice") == 1:
                        raise RuntimeError("Execution stopped by user.")
                    if default and not answer:
                        answer = default
                        break
                    if (options or {}).get("exit_on_nochoice", 0) == 2:
                        answer = None
                        break
            else:
                if options.get("is_forced") != 2:
                    sys.stdout.write(f"{default}\n")
                answer = default
                break
    else:
        raise ValueError("Must either have choices and options or none")

    if options and options.get("remember"):
        _answer_defaults[question] = answer
    return answer


def _ask_stdin(hidden: bool | None = None) -> str:
    if hidden:
        return getpass.getpass("")
    line = sys.stdin.readline()
    return line.rstrip("\n")


def _read_single_key() -> str:
    """Read a single keypress without requiring Enter (best effort)."""
    try:
        import termios
        import tty

        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            return sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
    except Exception:
        return sys.stdin.readline().rstrip("\n")
