"""Command-line entry points.

Python ports of the Perl ``bin/*`` scripts. Each ``cmd_*`` function is wired to
a console script in ``pyproject.toml``.
"""

from __future__ import annotations

import argparse
import base64
import os
import shutil
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from .alert import Alert
from .email_to_hash import EmailToHash
from .prettyprint import print_hashes
from .transform import Transform


def cmd_alert(argv: list[str] | None = None) -> int:
    """alert - pipe text into stdin to send a GroupMe message."""
    parser = argparse.ArgumentParser(
        prog="alert", description="Notify with a GroupMe account bot."
    )
    parser.add_argument("--dryrun", action="store_true", help="Print to screen instead of doing changes")
    parser.add_argument("--ignore", help="Ignore alerting if regexp match")
    args = parser.parse_args(argv)

    text = ""
    for i, line in enumerate(sys.stdin):
        text += line
        if i >= 50:
            break
    import re

    if not text or not re.search(r"\w", text):
        return 0
    if args.ignore and re.search(args.ignore, text):
        return 0
    if args.dryrun:
        print("DRYRUN: alert will report this text")
        print(text)
        return 0
    Alert(dryrun=args.dryrun).groupme(text)
    return 0


def cmd_transform(argv: list[str] | None = None) -> int:
    """transform - read from a source and write to a destination/format."""
    parser = argparse.ArgumentParser(
        prog="transform",
        description="Read from source write to destination. Transform data to another format.",
    )
    parser.add_argument("--dryrun", action="store_true", help="Print to screen instead of doing changes")
    parser.add_argument("--source_file", help="Give the source file")
    parser.add_argument("--source_type", help="Give the source type")
    parser.add_argument("--source_table", help="Give the source table")
    parser.add_argument("--destination_file", help="Give the destination file")
    parser.add_argument("--destination_type", help="Give the destination type")
    args = parser.parse_args(argv)

    source: dict = {}
    if args.source_file:
        source["file"] = args.source_file
    if args.source_type:
        source["type"] = args.source_type
    if args.source_table:
        source["table"] = args.source_table
    destination: dict = {}
    if args.destination_file:
        destination["file"] = args.destination_file
    if args.destination_type:
        destination["type"] = args.destination_type
    Transform().transform(source, destination)
    return 0


def cmd_dump_email_hash(argv: list[str] | None = None) -> int:
    """dump-email-hash - dump the parsed structure of an email file."""
    parser = argparse.ArgumentParser(prog="dump-email-hash", description="Dump email hash text")
    parser.add_argument("file", help="Email file to parse")
    args = parser.parse_args(argv)

    path = Path(args.file)
    if not path.is_file():
        raise SystemExit(f"Can't open file {args.file}, file does not exists")
    import pprint

    dump = EmailToHash().msgtext2hash(path.read_text(encoding="utf-8", errors="replace"))
    pprint.pprint(dump)
    return 0


def cmd_file_forwarder(argv: list[str] | None = None) -> int:
    """file-forwarder - copy not-yet-copied files from source dirs to destinations."""
    parser = argparse.ArgumentParser(
        prog="file-forwarder",
        description="Copy files not yet copied from source to destination.",
    )
    parser.add_argument("--homedir", help="Alternative home dir for configuration")
    args = parser.parse_args(argv)

    homedir = args.homedir or os.environ.get("HOME", "")
    cfg_file = os.path.join(homedir, "etc", "file-forwarder.cfg.yml")
    done_file = os.path.join(homedir, "etc", "file-forwarder.done.yml")

    Path(done_file).touch(exist_ok=True)
    print("Read config file " + cfg_file)
    with open(cfg_file, encoding="utf-8") as fh:
        config = yaml.safe_load(fh) or {}
    with open(done_file, encoding="utf-8") as fh:
        done = yaml.safe_load(fh) or {}

    for source_dir, destinations in config.items():
        if not os.path.isdir(source_dir):
            raise SystemExit(f"Source directory: {source_dir} does not exists")
        for destination, dest_cfg in (destinations or {}).items():
            if not os.path.isdir(destination):
                if not isinstance(dest_cfg, dict) or "mount_cmd" not in dest_cfg:
                    raise SystemExit(f"Destination: {destination} is not a directory.")
                subprocess.run(dest_cfg["mount_cmd"].split(), capture_output=True)
                if not os.path.isdir(destination):
                    raise SystemExit(f"Destination {destination} is not a directory or did not mount.")
            all_files = [
                str(p)[len(source_dir):]
                for p in Path(source_dir).rglob("*")
            ]
            done_files = {name: 1 for name in (done.get(source_dir) or [])}
            candidates = [f for f in all_files if done_files.get(f) != 1]
            for cpfile in candidates:
                src = source_dir + cpfile
                dst = destination + cpfile
                if os.path.isdir(src):
                    if not os.path.isdir(dst):
                        os.mkdir(dst)
                elif (
                    os.path.exists(dst)
                    and not os.access(dst, os.W_OK)
                    and os.path.getsize(src) == os.path.getsize(dst)
                ):
                    print(f"{dst} exists. Do notthing")
                else:
                    print(f"copy({src}, {dst})")
                    shutil.copy(src, dst)
                    print(f"{cpfile} has been copied")
                done.setdefault(source_dir, []).append(cpfile)
                with open(done_file, "w", encoding="utf-8") as fh:
                    yaml.safe_dump(done, fh, allow_unicode=True)
    print("Finished!")
    return 0


def cmd_file_rights_debug(argv: list[str] | None = None) -> int:
    """file-rights-debug - analyse why a file is not readable by a user."""
    import grp
    import pwd

    parser = argparse.ArgumentParser(
        prog="file-rights-debug",
        description="Analyze why a file is not readable for a user.",
    )
    parser.add_argument("--user", help="Analyze based on the view from user")
    parser.add_argument("file", help="File to analyze")
    args = parser.parse_args(argv)

    result: list[dict] = []
    links = [Path(args.file)]
    while links:
        tf = links.pop(0)
        first = True
        while True:
            exists = os.path.lexists(tf)
            user_rwx = group_rwx = other_rwx = None
            st = None
            if exists:
                st = os.lstat(tf)
                mode = st.st_mode
                user_rwx = (mode & stat.S_IRWXU) >> 6
                group_rwx = (mode & stat.S_IRWXG) >> 3
                other_rwx = mode & stat.S_IRWXO
                if os.path.islink(tf):
                    link = os.readlink(tf)
                    if link and not first and link != str(tf):
                        links.append(Path(link))
                        break
            first = False
            result.append({
                "name": str(tf),
                "user": pwd.getpwuid(st.st_uid).pw_name if st else "",
                "group": grp.getgrgid(st.st_gid).gr_name if st else "",
                "user_rwx": user_rwx,
                "group_rwx": group_rwx,
                "other_rwx": other_rwx,
                "exists": int(bool(exists)),
            })
            if str(tf) == "/":
                break
            tf = tf.parent
        print(print_hashes(result, {"columns": ["name", "user", "group", "user_rwx", "group_rwx", "other_rwx"]}))
    return 0


def cmd_unixtid(argv: list[str] | None = None) -> int:
    """unixtid - print current epoch, or convert an epoch to a datetime string."""
    argv = sys.argv[1:] if argv is None else argv
    if argv:
        dt = datetime.fromtimestamp(int(argv[0]), tz=timezone.utc)
        print(dt.strftime("%Y-%m-%d %H:%M:%S"))
    else:
        print(int(datetime.now().timestamp()))
    return 0


def cmd_b64d(argv: list[str] | None = None) -> int:
    """b64d - base64-decode the first argument."""
    argv = sys.argv[1:] if argv is None else argv
    data = argv[0] if argv else ""
    sys.stdout.buffer.write(base64.b64decode(data + "==="))
    sys.stdout.write("\n")
    return 0


def cmd_winord(argv: list[str] | None = None) -> int:
    """winord - tile/arrange windows using wmctrl (Linux/X11 only)."""
    from .winord import main as winord_main

    return winord_main(argv)
