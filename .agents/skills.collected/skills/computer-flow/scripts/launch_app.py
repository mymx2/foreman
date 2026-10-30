"""Find an installed application and start it, then wait for its window.

Discovery is read-only. Launching is a real side effect, so callers must gate it
behind an explicit plan step or flag; nothing here starts a process implicitly.

Lookup order (most to least authoritative):
  1. App Paths registry  (HKLM/HKCU, incl. WOW6432Node)
  2. Uninstall registry  (DisplayIcon / InstallLocation)
  3. Start Menu shortcuts (.lnk)
  4. Common install roots (Program Files, Program Files (x86), LOCALAPPDATA)

The first hit whose target actually exists on disk wins; a registry entry that
points at a missing file is skipped rather than launched.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def _clean(path):
    """Strip quotes and trailing comma/args from registry values like '"C:\\a b\\x.exe",-1'."""
    if not path:
        return ""
    path = path.strip()
    if path.startswith('"'):
        end = path.find('"', 1)
        if end > 0:
            return path[1:end]
    if "," in path:
        path = path.split(",", 1)[0]
    return path.strip().strip('"')


def _from_app_paths(names):
    import winreg

    roots = (
        (winreg.HKEY_LOCAL_MACHINE, "HKLM"),
        (winreg.HKEY_CURRENT_USER, "HKCU"),
    )
    subkeys = (
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths",
        r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths",
    )
    hits = []
    for hive, hive_label in roots:
        for sub in subkeys:
            try:
                with winreg.OpenKey(hive, sub) as key:
                    count = winreg.QueryInfoKey(key)[0]
                    for index in range(count):
                        try:
                            name = winreg.EnumKey(key, index)
                        except OSError:
                            continue
                        lowered = name.lower()
                        if not any(token in lowered for token in names):
                            continue
                        try:
                            with winreg.OpenKey(key, name) as entry:
                                value = _clean(winreg.QueryValue(entry, ""))
                        except OSError:
                            continue
                        if value:
                            hits.append({"source": f"{hive_label}:AppPaths:{name}", "path": value})
            except OSError:
                continue
    return hits


def _from_uninstall(names):
    import winreg

    roots = (
        (winreg.HKEY_LOCAL_MACHINE, "HKLM"),
        (winreg.HKEY_CURRENT_USER, "HKCU"),
    )
    subkeys = (
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
        r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
    )
    hits = []
    for hive, hive_label in roots:
        for sub in subkeys:
            try:
                with winreg.OpenKey(hive, sub) as key:
                    count = winreg.QueryInfoKey(key)[0]
                    for index in range(count):
                        try:
                            name = winreg.EnumKey(key, index)
                        except OSError:
                            continue
                        try:
                            with winreg.OpenKey(key, name) as entry:
                                display = str(winreg.QueryValueEx(entry, "DisplayName")[0])
                                if not any(token in display.lower() for token in names):
                                    continue
                                for field in ("DisplayIcon", "InstallLocation"):
                                    try:
                                        raw = _clean(str(winreg.QueryValueEx(entry, field)[0]))
                                    except OSError:
                                        continue
                                    if raw:
                                        hits.append({
                                            "source": f"{hive_label}:Uninstall:{display}:{field}",
                                            "path": raw,
                                        })
                        except OSError:
                            continue
            except OSError:
                continue
    return hits


def _from_start_menu(names):
    hits = []
    roots = [
        os.path.expandvars(r"%ProgramData%\Microsoft\Windows\Start Menu\Programs"),
        os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"),
    ]
    for root in roots:
        if not os.path.isdir(root):
            continue
        for dirpath, _dirnames, filenames in os.walk(root):
            for filename in filenames:
                if not filename.lower().endswith(".lnk"):
                    continue
                lowered = filename.lower()
                if any(token in lowered for token in names):
                    hits.append({
                        "source": f"StartMenu:{filename}",
                        "path": os.path.join(dirpath, filename),
                    })
    return hits


def _from_common_dirs(names):
    hits = []
    roots = [
        os.environ.get("ProgramFiles(x86)"),
        os.environ.get("ProgramFiles"),
        os.environ.get("LOCALAPPDATA"),
        os.environ.get("APPDATA"),
    ]
    for root in roots:
        if not root or not os.path.isdir(root):
            continue
        try:
            entries = os.listdir(root)
        except OSError:
            continue
        for entry in entries:
            lowered = entry.lower()
            if not any(token in lowered for token in names):
                continue
            base = os.path.join(root, entry)
            if not os.path.isdir(base):
                continue
            for pattern_root in (base, os.path.join(base, "main", "current")):
                if not os.path.isdir(pattern_root):
                    continue
                try:
                    for filename in os.listdir(pattern_root):
                        if filename.lower().endswith(".exe"):
                            hits.append({
                                "source": f"Dir:{entry}",
                                "path": os.path.join(pattern_root, filename),
                            })
                except OSError:
                    continue
    return hits


# Programs that sit next to the real entry point but do something else entirely:
# starting one launches an updater, an uninstaller, or an elevation shim instead
# of the application the plan means.
AUX_TOKENS = ("updater", "update", "uninstall", "unins", "elevate", "scheme", "crashpad", "helper", "reporter")


def _rank(path, exe_hint):
    """Lower is better. Real entry points outrank auxiliary executables."""
    base = os.path.basename(path).lower()
    if not base.endswith(".exe"):
        return 3
    if any(token in base for token in AUX_TOKENS):
        return 4
    if exe_hint and exe_hint.lower() in base:
        return 1
    return 2


def find_app(names, exe_hint=None, extra_roots=()):
    """Locate an installed executable by product-name tokens.

    `names` are lowercase substrings matched against registry keys, shortcut
    filenames and install-directory names. `exe_hint` narrows which .exe inside
    a directory is the real entry point (launchers often sit next to the app).
    """
    tokens = tuple(token.lower() for token in names)
    candidates = []
    candidates += _from_app_paths(tokens)
    candidates += _from_uninstall(tokens)
    candidates += _from_start_menu(tokens)
    candidates += _from_common_dirs(tokens)

    resolved = []
    seen = set()
    for candidate in candidates:
        path = candidate["path"]
        if path in seen:
            continue
        seen.add(path)
        resolved.append({
            **candidate,
            "exists": os.path.exists(path),
            "rank": _rank(path, exe_hint),
        })

    resolved.sort(key=lambda item: (not item["exists"], item["rank"]))
    return resolved


def launch(path, args=(), wait_seconds=0.0):
    """Start an executable detached from this process.

    Detached so that the automation script exiting does not kill the app.
    Returns the spawned pid; the window handle is discovered separately by
    title/process once the app finishes starting up.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"executable not found: {path}")
    creationflags = 0
    if sys.platform == "win32":
        # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        creationflags = 0x00000008 | 0x00000200
    process = subprocess.Popen(
        [path, *args],
        creationflags=creationflags,
        close_fds=True,
        cwd=os.path.dirname(path) or None,
    )
    if wait_seconds > 0:
        time.sleep(wait_seconds)
    return process.pid


def wait_for_window(title_contains=None, process_name=None, timeout=60.0, poll=1.0):
    """Poll discovery until exactly one window matches, or time out.

    Returns the matched window handle. More than one match after the timeout is
    an error: the caller must disambiguate rather than pick arbitrarily.
    """
    from discover import find_windows

    deadline = time.monotonic() + timeout
    last_error = None
    while True:
        try:
            matches = find_windows(title_contains=title_contains, process_name=process_name)
        except Exception as exc:  # discovery can fail while the app is initialising
            matches = []
            last_error = exc
        if len(matches) == 1:
            return matches[0].handle
        if time.monotonic() >= deadline:
            if not matches:
                detail = f" (last discovery error: {last_error})" if last_error else ""
                raise TimeoutError(
                    f"no window matched title={title_contains!r} process={process_name!r} "
                    f"within {timeout}s{detail}"
                )
            listing = [{"handle": w.handle, "title": w.title} for w in matches]
            raise RuntimeError(f"{len(matches)} windows matched after {timeout}s: {listing}")
        time.sleep(poll)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Find and optionally launch an installed application.")
    parser.add_argument("--name", required=True, action="append",
                        help="lowercase token matched against registry/shortcuts/dirs; repeatable")
    parser.add_argument("--exe", help="preferred executable filename inside the install dir")
    parser.add_argument("--launch", action="store_true", help="actually start the best candidate")
    parser.add_argument("--wait-window", metavar="TITLE", help="after launching, wait for a window title")
    parser.add_argument("--process", help="process name to match while waiting")
    parser.add_argument("--timeout", type=float, default=60.0)
    args = parser.parse_args()

    hits = find_app(args.name, exe_hint=args.exe)
    payload = {"query": args.name, "candidates": hits}
    if not hits:
        print(json.dumps({**payload, "error": "no candidate found"}, ensure_ascii=False, indent=2))
        raise SystemExit(2)

    best = next((hit for hit in hits if hit["exists"] and hit["rank"] <= 2), None) or next(
        (hit for hit in hits if hit["exists"]), None
    )
    payload["best"] = best
    if args.launch and best:
        payload["pid"] = launch(best["path"])
        if args.wait_window or args.process:
            payload["handle"] = wait_for_window(
                title_contains=args.wait_window,
                process_name=args.process,
                timeout=args.timeout,
            )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
