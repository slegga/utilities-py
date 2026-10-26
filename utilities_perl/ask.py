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
    default = _default_answer(question, options)

    if choices is None and options is None:
        answer = _ask_any_key(question)
    elif choices is not None:
        answer = _ask_choice(question, choices, options, default)
    else:
        raise ValueError("Must either have choices and options or none")

    if options and options.get("remember"):
        _answer_defaults[question] = answer
    return answer


def _default_answer(question: str, options: dict | None) -> str | None:
    """Default/forced answer for ``question``, or None."""
    if not options:
        return None
    if "forced_answer" in options:
        return options["forced_answer"]
    if options.get("remember") and question in _answer_defaults:
        return _answer_defaults[question]
    return None


def _ask_any_key(question: str) -> str:
    """Ask a "press any key" question and return the single key."""
    sys.stdout.write(question)
    sys.stdout.flush()
    answer = _read_single_key()
    sys.stdout.write("\n")
    return answer


def _ask_choice(
    question: str, choices, options: dict | None, default: str | None
) -> str | None:
    """Ask until an acceptable answer is given, and return it."""
    is_regex = isinstance(choices, (re.Pattern,))
    while True:
        if not (options and options.get("is_forced") == 2):
            _print_prompt(question, choices, default, is_regex)
        if options and options.get("is_forced"):
            if options.get("is_forced") != 2:
                sys.stdout.write(f"{default}\n")
            return default
        answer = _ask_stdin(options.get("secret") if options else None)
        if _matches(answer, choices, is_regex):
            return answer
        done, result = _unmatched_answer(answer, default, options)
        if done:
            return result


def _print_prompt(question: str, choices, default: str | None, is_regex: bool) -> None:
    sys.stdout.write(f"{question} ")
    if is_regex:
        sys.stdout.write(choices.pattern)
    else:
        sys.stdout.write("(" + ",".join(str(c) for c in choices) + ")")
    if default:
        sys.stdout.write(f"[{default}]")
    sys.stdout.write("? ")
    sys.stdout.flush()


def _matches(answer: str, choices, is_regex: bool) -> bool:
    if is_regex:
        return bool(re.match(f"^{choices.pattern}$", answer.lower()))
    return any(answer.lower() == str(c).lower() for c in choices)


def _unmatched_answer(answer: str | None, default: str | None, options: dict | None):
    """Håndter et svar som ikke traff. Returnerer (ferdig, svar); ferdig=False gir ny runde."""
    if options and options.get("exit_on_nochoice") == 1:
        raise RuntimeError("Execution stopped by user.")
    if default and not answer:
        return True, default
    if (options or {}).get("exit_on_nochoice", 0) == 2:
        return True, None
    return False, None


def _ask_stdin(hidden: bool | None = None) -> str:
    if hidden:
        return getpass.getpass("")
    line = sys.stdin.readline()
    return line.rstrip("\n")


def _read_single_key() -> str:
    """Read a single keypress without requiring Enter (best effort)."""
    try:
        # Lazy med vilje: termios/tty finnes ikke overalt, og importfeil skal
        # falle stille tilbake til readline.
        import termios
        import tty

        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            return sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
    except Exception:  # noqa: BLE001 -- bevisst best-effort-fallback til readline
        return sys.stdin.readline().rstrip("\n")
