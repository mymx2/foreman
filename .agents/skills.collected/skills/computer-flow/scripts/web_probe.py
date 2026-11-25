"""Probe in-page popovers (context menus, dropdowns) in Electron/Chromium apps.

Why this exists: a DOM popover is not a top-level window. When it opens outside
the viewport (e.g. a position:fixed anchor living inside a transformed ancestor),
the screen shows nothing and GW_OWNER/UIA enumeration shows nothing either, which
looks identical to "the menu never opened". This probe answers three different
questions in one call:

  1. was the element created at all?
  2. where is it -- viewport-relative rect vs viewport size?
  3. which ancestor hijacked fixed positioning (transform/filter/contain/...)?

The target must expose a DevTools endpoint, e.g. start it with
    --remote-debugging-port=9333 --remote-allow-origins=*

Windows note: launch it detached (explorer.exe / .lnk). A process started from a
job-managed shell can be killed together with the job.

No third-party dependencies: a minimal RFC6455 client over stdlib sockets.
This is a build-time diagnostic primitive, not a replacement for UIA/OCR in the
frozen script.
"""

import argparse
import base64
import json
import os
import socket
import struct
import sys
import time
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

DEFAULT_PORT = 9333


def list_targets(port=DEFAULT_PORT, timeout=5.0):
    """Return the DevTools target list, or raise with a hint when the port is closed."""
    url = f"http://127.0.0.1:{port}/json/list"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except OSError as exc:
        raise RuntimeError(
            f"cannot reach {url}: {exc}. Start the target with "
            f"--remote-debugging-port={port} --remote-allow-origins=*"
        ) from exc


def pick_page(targets, url_contains=None):
    pages = [t for t in targets if t.get("type") == "page"]
    if url_contains:
        pages = [t for t in pages if url_contains in (t.get("url") or "")]
    return pages[0] if pages else None


class NeedMore(Exception):
    """Raised when the buffer does not hold a complete frame yet."""


def encode_frame(payload, opcode=0x1, mask=True):
    """Encode one client frame. Clients must mask; tests use mask=False."""
    header = bytearray([0x80 | opcode])
    length = len(payload)
    flag = 0x80 if mask else 0
    if length < 126:
        header.append(flag | length)
    elif length < 65536:
        header.append(flag | 126)
        header += struct.pack("!H", length)
    else:
        header.append(flag | 127)
        header += struct.pack("!Q", length)
    if not mask:
        return bytes(header) + payload
    key = os.urandom(4)
    header += key
    return bytes(header) + bytes(b ^ key[i % 4] for i, b in enumerate(payload))


def decode_frame(buffer):
    """Decode one frame from `buffer`; return (fin, opcode, payload, consumed)."""
    if len(buffer) < 2:
        raise NeedMore
    first, second = buffer[0], buffer[1]
    fin = bool(first & 0x80)
    opcode = first & 0x0F
    masked = bool(second & 0x80)
    length = second & 0x7F
    index = 2
    if length == 126:
        if len(buffer) < 4:
            raise NeedMore
        length = struct.unpack("!H", buffer[2:4])[0]
        index = 4
    elif length == 127:
        if len(buffer) < 10:
            raise NeedMore
        length = struct.unpack("!Q", buffer[2:10])[0]
        index = 10
    key = b""
    if masked:
        if len(buffer) < index + 4:
            raise NeedMore
        key = buffer[index:index + 4]
        index += 4
    if len(buffer) < index + length:
        raise NeedMore
    payload = buffer[index:index + length]
    if masked:
        payload = bytes(b ^ key[i % 4] for i, b in enumerate(payload))
    return fin, opcode, payload, index + length


class WebSocket:
    """Minimal ws:// client: text messages, ping/pong, fragmentation."""

    def __init__(self, url, timeout=10.0):
        if not url.startswith("ws://"):
            raise ValueError(f"only ws:// is supported: {url}")
        host_port, _, path = url[5:].partition("/")
        host, _, port = host_port.partition(":")
        self._sock = socket.create_connection((host, int(port or 80)), timeout=timeout)
        self._sock.settimeout(timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        request = (
            f"GET /{path} HTTP/1.1\r\n"
            f"Host: {host_port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        self._sock.sendall(request.encode("ascii"))
        response = b""
        while b"\r\n\r\n" not in response:
            chunk = self._sock.recv(4096)
            if not chunk:
                raise RuntimeError("handshake closed by peer")
            response += chunk
        head, _, rest = response.partition(b"\r\n\r\n")
        status = head.split(b"\r\n", 1)[0]
        if b" 101 " not in status + b" ":
            raise RuntimeError(f"handshake failed: {status!r}")
        self._buffer = rest

    def _next_frame(self):
        while True:
            try:
                return decode_frame(self._buffer)
            except NeedMore:
                chunk = self._sock.recv(65536)
                if not chunk:
                    raise RuntimeError("socket closed by peer")
                self._buffer += chunk

    def send_text(self, text):
        self._sock.sendall(encode_frame(text.encode("utf-8")))

    def recv_text(self):
        while True:
            fin, opcode, payload, used = self._next_frame()
            self._buffer = self._buffer[used:]
            if opcode == 0x9:  # ping
                self._sock.sendall(encode_frame(payload, opcode=0xA))
                continue
            if opcode == 0xA:  # pong
                continue
            if opcode == 0x8:  # close
                raise RuntimeError("websocket closed by peer")
            if opcode not in (0x1, 0x2):
                continue
            data = payload
            more = not fin
            while more:
                fin2, opcode2, payload2, used2 = self._next_frame()
                self._buffer = self._buffer[used2:]
                if opcode2 == 0x9:
                    self._sock.sendall(encode_frame(payload2, opcode=0xA))
                    continue
                if opcode2 == 0xA:
                    continue
                if opcode2 == 0x8:
                    raise RuntimeError("websocket closed by peer")
                data += payload2
                more = not fin2
            return data.decode("utf-8", "replace")

    def close(self):
        try:
            self._sock.sendall(encode_frame(b"", opcode=0x8))
        except OSError:
            pass
        self._sock.close()


class CDP:
    """Tiny CDP client: send a command, wait for the matching id."""

    def __init__(self, ws_url, timeout=10.0):
        self._ws = WebSocket(ws_url, timeout)
        self._id = 0
        self._timeout = timeout

    def send(self, method, params=None):
        self._id += 1
        deadline = time.monotonic() + self._timeout
        self._ws.send_text(json.dumps({"id": self._id, "method": method, "params": params or {}}))
        while True:
            if time.monotonic() > deadline:
                raise RuntimeError(f"{method}: no response within {self._timeout:.1f}s")
            message = json.loads(self._ws.recv_text())
            if message.get("id") != self._id:
                continue  # events interleaved with responses
            if "error" in message:
                raise RuntimeError(f"{method}: {message['error']}")
            return message.get("result", {})

    def evaluate(self, expression):
        result = self.send(
            "Runtime.evaluate",
            {"expression": expression, "returnByValue": True, "awaitPromise": True},
        )
        if result.get("exceptionDetails"):
            raise RuntimeError(result["exceptionDetails"].get("text") or "evaluate failed")
        return (result.get("result") or {}).get("value")

    def click(self, x, y, button="left"):
        for event_type in ("mousePressed", "mouseReleased"):
            self.send(
                "Input.dispatchMouseEvent",
                {"type": event_type, "x": x, "y": y, "button": button, "clickCount": 1},
            )

    def screenshot(self, path):
        result = self.send("Page.captureScreenshot", {"format": "png"})
        with open(path, "wb") as handle:
            handle.write(base64.b64decode(result["data"]))
        return path

    def close(self):
        self._ws.close()


PROBE_JS = r"""
(() => {
  const rect = el => el ? ((r => [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)])(el.getBoundingClientRect())) : null;
  const menus = [...document.querySelectorAll('[role="menu"]')];
  const menu = menus.find(el => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; }) || menus[0] || null;
  const anchor = [...document.querySelectorAll('button')].find(b => {
    const r = b.getBoundingClientRect();
    return r.width <= 2 && r.height <= 2;
  });
  const fx = [];
  let node = anchor;
  while (node && node !== document.documentElement) {
    const cs = getComputedStyle(node);
    if (cs.transform !== 'none' || cs.filter !== 'none' || cs.contain !== 'none' ||
        cs.willChange !== 'auto' || cs.perspective !== 'none') {
      fx.push({
        tag: node.tagName,
        cls: String(node.className).slice(0, 60),
        transform: cs.transform,
        filter: cs.filter,
        contain: cs.contain,
        willChange: cs.willChange,
        perspective: cs.perspective
      });
    }
    node = node.parentElement;
  }
  const hit = document.elementFromPoint(__X__, __Y__);
  return {
    viewport: [innerWidth, innerHeight],
    menuCount: menus.length,
    menuRect: rect(menu),
    menuItems: [...document.querySelectorAll('[role="menuitem"]')]
      .map(n => n.textContent.trim().replace(/\s+/g, ' ')),
    anchorStyle: anchor ? anchor.getAttribute('style') : null,
    anchorRect: rect(anchor),
    anchorAncestorsWithFx: fx,
    hitAtPoint: hit ? hit.tagName + '.' + String(hit.className).slice(0, 40) : null
  };
})()
"""


def probe(cdp, x, y, button="right", settle=0.45):
    """Click, wait, then report popover geometry and the cause of any displacement."""
    cdp.click(x, y, button)
    time.sleep(settle)
    data = cdp.evaluate(PROBE_JS.replace("__X__", str(float(x))).replace("__Y__", str(float(y))))
    menu = data.get("menuRect")
    width, height = data.get("viewport") or (0, 0)
    if menu is None:
        data["verdict"] = "no-menu"
    elif menu[2] <= 0 or menu[3] <= 0:
        # Mounted but zero-area: hidden or mid-animation. Neither "visible" nor
        # proof that the popover was pushed offscreen.
        data["verdict"] = "no-size"
    elif width <= 0 or height <= 0:
        data["verdict"] = "viewport-unknown"
    elif menu[0] + menu[2] <= 0 or menu[1] + menu[3] <= 0 or menu[0] >= width or menu[1] >= height:
        data["verdict"] = "offscreen"
    elif menu[0] < 0 or menu[1] < 0 or menu[0] + menu[2] > width or menu[1] + menu[3] > height:
        data["verdict"] = "partially-offscreen"
    else:
        data["verdict"] = "visible"
    return data


def main(argv=None):
    parser = argparse.ArgumentParser(description="Probe in-page popovers through the DevTools protocol.")
    commands = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--port", type=int, default=DEFAULT_PORT)
    common.add_argument("--url-contains", default=None, help="pick the page whose URL contains this text")
    common.add_argument("--timeout", type=float, default=10.0)

    commands.add_parser("targets", parents=[common], help="list DevTools targets")

    evaluate_cmd = commands.add_parser("eval", parents=[common], help="evaluate one JS expression")
    evaluate_cmd.add_argument("js")

    probe_cmd = commands.add_parser("probe", parents=[common], help="click a point, then report popover geometry")
    probe_cmd.add_argument("--x", type=float, required=True)
    probe_cmd.add_argument("--y", type=float, required=True)
    probe_cmd.add_argument("--button", default="right", choices=["left", "right", "middle"])
    probe_cmd.add_argument("--settle", type=float, default=0.45)

    shot_cmd = commands.add_parser("shot", parents=[common], help="save a page screenshot")
    shot_cmd.add_argument("path")

    args = parser.parse_args(argv)

    try:
        targets = list_targets(args.port, timeout=args.timeout)
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        return 2
    if args.command == "targets":
        print(json.dumps(targets, indent=2, ensure_ascii=False))
        return 0

    page = pick_page(targets, args.url_contains)
    if not page:
        print("no page target matched; try `targets` first", file=sys.stderr)
        return 2

    cdp = CDP(page["webSocketDebuggerUrl"], timeout=args.timeout)
    try:
        cdp.send("Runtime.enable")
        if args.command == "eval":
            print(json.dumps(cdp.evaluate(args.js), indent=2, ensure_ascii=False))
        elif args.command == "probe":
            print(json.dumps(probe(cdp, args.x, args.y, args.button, args.settle), indent=2, ensure_ascii=False))
        elif args.command == "shot":
            print(cdp.screenshot(args.path))
    finally:
        cdp.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
