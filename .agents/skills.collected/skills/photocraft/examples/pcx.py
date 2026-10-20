"""案例公共库（阅读）：所有 `NN-*.py` 场景脚本 import 它。

    from pcx import *
    src = pcx_input(sys.argv[1] if len(sys.argv) > 1 else "", "template.psd", kind="file")
    pcx_init("01-inspect-and-convert")
    pc(...)

两种模式
  演示模式：不带文件参数，输入来自 assets/ 或 fixture 现场生成，质检可以按夹具的已知内容断言。
  用户模式：带了文件参数，只做不依赖夹具几何的质检；只对夹具成立的检查用 demo_only 包起来，
  用户模式下打印 skip 跳过（不算失败，也不冒充通过）。

环境变量
  PHOTOCRAFT_CLI  photocraft-cli 的路径（默认依次找 PATH、Windows 注册表与标准安装目录）
  PCX_WORK        工作根目录（默认 <tmp>/photocraft-examples），夹具在 fixtures/，产出在 out/<场景>/
  PCX_DESKTOP     设为 1 才运行需要真实窗口的案例（否则该案例以退出码 77 跳过）

依赖：Python 3.10+ 标准库。不需要 bash、node。
"""
from __future__ import annotations

import io
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

# 统一的 UTF-8 输出：Windows 控制台默认 GBK/CP936，中文与 ¥ 之类字符会抛 UnicodeEncodeError
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

# 案例目录与技能根目录
EX_DIR = Path(__file__).resolve().parent
SKILL_DIR = EX_DIR.parent
SCRIPTS_DIR = SKILL_DIR / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import pclib  # noqa: E402

PCX_WORK = Path(os.environ.get("PCX_WORK") or (Path(tempfile.gettempdir()) / "photocraft-examples")).resolve()
PCX_WORK_DEFAULT = not os.environ.get("PCX_WORK")
FIX = PCX_WORK / "fixtures"
PCX_USER = False
PC = None
OUT: Path | None = None


def user_mode() -> bool:
    """当前是否在处理用户文件。

    必须用函数读取：案例用 `from pcx import *`，模块级变量的值是导入时的快照，
    `pcx_input` 之后再改 `pcx.PCX_USER`，案例里那份不会变（用户模式会静默走成演示分支）。
    """
    return PCX_USER

# 案例只用显式参数：不继承指向真实控制令牌、授权根目录的环境变量；配置目录默认放进工作目录。
for _var in ("PHOTOCRAFT_CONTROL_PORT", "PHOTOCRAFT_CONTROL_TOKEN", "PHOTOCRAFT_CONTROL_TOKEN_FILE",
             "PHOTOCRAFT_AUTOMATION_READ_ROOT", "PHOTOCRAFT_AUTOMATION_WRITE_ROOT"):
    os.environ.pop(_var, None)
# 案例不读也不写用户真实的配置目录（prefs、动作、最近文件）；永远用工作目录下的隔离副本。
os.environ["PHOTOCRAFT_CONFIG_DIR"] = str(PCX_WORK / "config")
(PCX_WORK / "config").mkdir(parents=True, exist_ok=True)


# --------------------------------------------------------------------------- 输出与失败
def step(text: str) -> None:
    print(f"\n== {text}", flush=True)


def note(text) -> None:
    print(f"   {text}", flush=True)


def fail(text) -> None:
    print(f"   FAIL {text}", file=sys.stderr, flush=True)
    sys.exit(1)


def skip(text) -> None:
    print(f"skip: {text}", flush=True)
    sys.exit(77)


def demo_only(description: str) -> bool:
    """包住只对内置夹具成立的检查；用户模式下打印 skip 并返回 False。"""
    if user_mode():
        note(f"skip {description} (fixture-specific check; user input)")
        return False
    return True


# --------------------------------------------------------------------------- CLI 调用
def init_cli() -> Path:
    global PC
    if PC is None:
        try:
            PC = pclib.find_cli()
        except pclib.CliNotFound as exc:
            print(f"photocraft-cli not found: {exc}", file=sys.stderr)
            sys.exit(2)
    return PC


def pc(*args, check=False, capture=False, timeout=600):
    """执行 photocraft-cli，返回 CompletedProcess。capture=True 时另外返回 (stdout, stderr)。"""
    init_cli()
    argv = [str(PC), *map(str, args)]
    proc = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=timeout, env=os.environ.copy())
    if check and proc.returncode != 0:
        fail(f"`{' '.join(map(str, args))}` exited {proc.returncode}\n{proc.stderr[-1500:]}")
    if not capture:
        for line in proc.stdout.splitlines():
            print(line, flush=True)
        for line in proc.stderr.splitlines():
            print(line, file=sys.stderr, flush=True)
    return proc


def pc_run(cmds, *, input=None, new=None, out=None, extra=(), check=False):
    """一条 run：cmds 是 [(id, params)] 或 [(id,)]；input 是输入文件，new 是 file.new 参数。返回 RunOutput。"""
    init_cli()
    steps = []
    for item in cmds:
        if isinstance(item, str):
            steps.append((item, None))
        else:
            steps.append((item[0], item[1] if len(item) > 1 else None))
    rows: list[dict] = []
    stderr = ""
    rc = 0
    try:
        target = None if new is not None else str(input)
        res = pclib.run_cmds(target, steps, new=new, out=str(out) if out else None,
                             extra_args=extra, cli=PC, cwd=os.getcwd(), check=False)
        rows, stderr, rc = list(res), res.stderr, res.returncode
    except pclib.CliError as exc:
        rows, stderr, rc = list(exc.rows), exc.stderr, exc.returncode or 1
    for row in rows:
        print(json.dumps(row, ensure_ascii=False), flush=True)
    for line in stderr.splitlines():
        print(line, file=sys.stderr, flush=True)
    if check and rc != 0:
        fail(f"run exited {rc}\n{stderr[-1500:]}")
    return pclib.RunOutput(rows, stderr=stderr, returncode=rc)


def pc_json(stdout_or_path, expr: str = None):
    """把 JSON 文本/路径解析成 D（可写 j.width 也可写 j["width"]）。"""
    data = _wrap(json.loads(_read_json_text(stdout_or_path)))
    return data[expr] if expr is not None else data


def pc_result(run_output, command: str = None):
    """run 输出里最后一条（或指定命令的）result。"""
    return _wrap(run_output.result(command))


class _AttrDict(dict):
    __slots__ = ()

    def __getattr__(self, k):
        if k.startswith("__"):
            raise AttributeError(k)
        return self.get(k)


def _wrap(obj):
    """把嵌套结构整体转成 _AttrDict，让 j.layers[0].kind 这种写法可用。"""
    if isinstance(obj, dict):
        return _AttrDict({k: _wrap(v) for k, v in obj.items()})
    if isinstance(obj, list):
        return [_wrap(v) for v in obj]
    return obj


def _read_json_text(source) -> str:
    if hasattr(source, "read"):
        return source.read()
    p = Path(str(source))
    if p.exists() and p.is_file():
        return p.read_text(encoding="utf-8")
    return str(source)


def info(path) -> _AttrDict:
    """info --compact 的结果。"""
    pc_info = pc("info", str(path), "--compact", capture=True)
    if pc_info.returncode != 0:
        fail(f"info failed on {path}\n{pc_info.stderr[-800:]}")
    return _wrap(json.loads(pc_info.stdout))


def pcx_native(path) -> str:
    """Windows 上 CLI 要 C:/... 形式的路径；POSIX 原样返回。"""
    p = str(Path(path).resolve())
    return p if os.name != "nt" else p.replace("\\", "/")


# --------------------------------------------------------------------------- 输入
INPUTS: list[Path] = []
MARKER = ".pcx-out"


def _is_junction(path: Path) -> bool:
    try:
        return bool(getattr(os.lstat(path), "st_reparse_tag", 0))
    except OSError:
        return False


def pcx_init(name: str) -> Path:
    """新建并进入 $PCX_WORK/out/<名称>，之后一律用相对路径。

    只清空自己上次创建的目录（带 .pcx-out 标记）；默认临时根目录下的旧目录直接清空，
    用户指定的 PCX_WORK 下非空又没标记的目录拒绝删除（确认可弃用后设 PCX_FORCE_CLEAN=1），
    输入文件落在输出目录里、或输入目录包含输出目录时都直接报错；链接/junction 也拒绝。
    """
    global OUT
    OUT = PCX_WORK / "out" / name
    for src in INPUTS:
        if OUT == src or OUT in src.parents:
            fail(f"input {src} is inside the output directory {OUT}; move it out of {OUT.parent} or set PCX_WORK elsewhere")
        if src.is_dir() and OUT.is_relative_to(src):
            fail(f"input directory {src} contains the output directory {OUT}; choose a PCX_WORK outside your inputs")
    if OUT.is_symlink() or _is_junction(OUT):
        fail(f"refusing to use a linked output directory: {OUT}")
    if OUT.exists():
        if not OUT.is_dir():
            fail(f"output path is not a directory: {OUT}")
        marker = OUT / MARKER
        if any(OUT.iterdir()) and not marker.is_file() \
                and not PCX_WORK_DEFAULT and os.environ.get("PCX_FORCE_CLEAN") != "1":
            fail(f"refusing to delete a non-empty directory not created by these examples: {OUT}; "
                 "remove it yourself, set PCX_FORCE_CLEAN=1 if it is disposable, "
                 "or set PCX_WORK elsewhere")
        try:
            shutil.rmtree(OUT)
        except OSError as exc:
            fail(f"cannot clear the previous output directory {OUT}: {exc}")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / MARKER).write_text("created by a photocraft example; safe to delete\n", encoding="utf-8")
    os.chdir(OUT)
    proc = pc("--version", capture=True)
    lines = (proc.stdout or proc.stderr).strip().splitlines()
    if proc.returncode != 0 or not lines:
        fail("photocraft-cli --version failed: " + (proc.stderr or proc.stdout or "")[-400:])
    version = lines[0]
    print(f"# {name} -> {OUT}\n# {version}\n# mode: {'user files' if user_mode() else 'demo (bundled fixtures)'}", flush=True)
    return OUT


def pcx_abs(path) -> Path:
    p = Path(path).expanduser()
    if not p.exists():
        fail(f"input not found: {path}")
    return p.resolve()


def pcx_input(arg: str, fixture_name: str = "", kind: str = "") -> Path | None:
    """参数非空 → 绝对路径 + 用户模式；否则用夹具（为空则返回 None）。"""
    global PCX_USER
    if arg:
        p = pcx_abs(arg)
        if kind == "dir" and not p.is_dir():
            fail(f"expected a directory: {arg}")
        if kind == "file" and not p.is_file():
            fail(f"expected a file: {arg}")
        INPUTS.append(p)
        PCX_USER = True
        return p
    return fixture(fixture_name) if fixture_name else None


def pcx_copy_dir(src: Path, dst: Path) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    for f in Path(src).iterdir():
        if f.is_file():
            shutil.copy2(f, dst / f.name)


# --------------------------------------------------------------------------- 断言
def expect(path, predicate=None, what: str = None) -> None:
    """断言产出文件的文档属性；predicate 接收 D 类型的 j。"""
    p = Path(path)
    if not p.is_file() or p.stat().st_size == 0:
        fail(f"missing output {p}")
    j = info(p)
    ok = predicate(j) if callable(predicate) else True
    if not ok:
        fail(f"{what or 'check failed'}  ({p})")
    note(f"ok  {what or p}")


def expect_size(path, w: int, h: int) -> None:
    j = info(path)
    if (j["width"], j["height"]) != (w, h):
        fail(f"{path} is {j['width']}x{j['height']}, expected {w}x{h}")
    note(f"ok  {path} is {w}x{h}")


def expect_file(path) -> None:
    p = Path(path)
    if not p.is_file() or p.stat().st_size == 0:
        fail(f"missing output {p}")
    note(f"ok  {p} ({p.stat().st_size} bytes)")


def expect_count(directory, pattern: str, count: int) -> None:
    n = len(list(Path(directory).glob(pattern)))
    if n != count:
        fail(f"expected {count} files matching {directory}/{pattern}, found {n}")
    note(f"ok  {n} files {directory}/{pattern}")


def expect_error(proc, needle: str, what: str = "") -> None:
    """断言命令失败且错误文本包含 needle。"""
    text = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode == 0:
        fail(f"expected a failure{': ' + what if what else ''}")
    if needle.lower() not in text.lower():
        fail(f"expected {needle!r} in the error{': ' + what if what else ''}\n{text[-800:]}")
    note(f"ok  {what or needle}")


# --------------------------------------------------------------------------- 像素
class Img:
    """pcx_ppm 导出的 PPM/PAM（P5/P6/P7，8 或 16 位）。像素值是 0..1 的元组，16 位只取高字节。"""

    def __init__(self, path):
        b = Path(path).read_bytes()
        if b[:2] == b"P7":
            end = b.index(b"ENDHDR\n")
            head = {}
            for line in b[3:end].decode("ascii").splitlines():
                parts = line.split()
                if len(parts) >= 2 and not parts[0].startswith("#"):
                    head[parts[0]] = parts[1]
            w, h, c, maxv = (int(head[k]) for k in ("WIDTH", "HEIGHT", "DEPTH", "MAXVAL"))
            off = end + 7
        elif b[:2] in (b"P5", b"P6"):
            toks, i = [], 2
            while len(toks) < 3:
                while b[i:i + 1].isspace():
                    i += 1
                if b[i:i + 1] == b"#":
                    i = b.index(b"\n", i) + 1
                    continue
                j = i
                while not b[j:j + 1].isspace():
                    j += 1
                toks.append(int(b[i:j]))
                i = j
            w, h, maxv = toks
            c = 1 if b[:2] == b"P5" else 3
            off = i + 1
        else:
            raise ValueError("not a PPM/PAM file: " + str(path))
        data = b[off:]
        if maxv > 255:
            data = data[0::2]
        self.w, self.h, self.c, self.data = w, h, c, data
        self.stride = w * c

    def px(self, x, y):
        i = (y * self.w + x) * self.c
        return tuple(v / 255 for v in self.data[i:i + self.c])

    def clip(self, x, y, w, h):
        x0, y0 = max(0, int(x)), max(0, int(y))
        return x0, y0, min(self.w, int(x + w)), min(self.h, int(y + h))

    def pixels(self, x, y, w, h, step=1):
        x0, y0, x1, y1 = self.clip(x, y, w, h)
        for yy in range(y0, y1, step):
            for xx in range(x0, x1, step):
                yield self.px(xx, yy)

    def stats(self, x, y, w, h, step=1, channels=3):
        n, s, ss = 0, [0.0] * channels, [0.0] * channels
        for p in self.pixels(x, y, w, h, step):
            n += 1
            for k in range(channels):
                s[k] += p[k]
                ss[k] += p[k] * p[k]
        if not n:
            raise ValueError("empty rectangle")
        mean = [v / n for v in s]
        return mean, [math.sqrt(max(0.0, ss[k] / n - mean[k] ** 2)) for k in range(channels)]

    def _table(self, test):
        return bytes(1 if test(v) else 0 for v in range(256))

    def count_ink(self, thr=0.98, x=0, y=0, w=None, h=None):
        table = self._table(lambda v: v < round(thr * 255))
        x0, y0, x1, y1 = self.clip(x, y, self.w if w is None else w, self.h if h is None else h)
        n = 0
        for yy in range(y0, y1):
            row = self.data[yy * self.stride + x0 * self.c:yy * self.stride + x1 * self.c]
            if self.c == 4:
                row = bytes(v for i, v in enumerate(row) if i % 4 != 3)
            n += row.translate(table).count(1)
        return n

    def ink_bbox(self, thr=0.98):
        if self.c == 4:
            raise ValueError("ink_bbox needs an opaque image; use alpha_bbox")
        table = self._table(lambda v: v < round(thr * 255))
        x0, x1, y0, y1 = self.w, -1, None, None
        for yy in range(self.h):
            row = self.data[yy * self.stride:(yy + 1) * self.stride].translate(table)
            i = row.find(1)
            if i < 0:
                continue
            x0, x1 = min(x0, i // self.c), max(x1, row.rfind(1) // self.c)
            y0 = yy if y0 is None else y0
            y1 = yy
        return None if y0 is None else [x0, y0, x1 - x0 + 1, y1 - y0 + 1]

    def alpha_bbox(self, thr=0):
        if self.c not in (2, 4):
            return [0, 0, self.w, self.h]
        a = self.data[self.c - 1::self.c]
        table = self._table(lambda v: v > thr)
        x0, x1, y0, y1 = self.w, -1, None, None
        for yy in range(self.h):
            row = a[yy * self.w:(yy + 1) * self.w].translate(table)
            i = row.find(1)
            if i < 0:
                continue
            x0, x1 = min(x0, i), max(x1, row.rfind(1))
            y0 = yy if y0 is None else y0
            y1 = yy
        return None if y0 is None else [x0, y0, x1 - x0 + 1, y1 - y0 + 1]


def diff(a: Img, b: Img, x=0, y=0, w=None, h=None, step=1):
    if (a.w, a.h) != (b.w, b.h):
        raise ValueError(f"size differs: {a.w}x{a.h} vs {b.w}x{b.h}")
    tot = n = 0
    mx = 0.0
    for p, q in zip(a.pixels(x, y, a.w if w is None else w, a.h if h is None else h, step),
                    b.pixels(x, y, b.w if w is None else w, b.h if h is None else h, step)):
        for k in range(3):
            d = abs(p[k] - q[k])
            tot += d
            n += 1
            mx = max(mx, d)
    return tot / n, mx


def changed_bbox(a: Img, b: Img, tol=0):
    if (a.w, a.h, a.c) != (b.w, b.h, b.c):
        raise ValueError("images differ in size or channels")
    st, c = a.stride, a.c
    x0, x1, y0, y1 = a.w, -1, None, None
    for yy in range(a.h):
        ra, rb = a.data[yy * st:(yy + 1) * st], b.data[yy * st:(yy + 1) * st]
        if ra == rb:
            continue
        hits = [i for i in range(st) if abs(ra[i] - rb[i]) > tol]
        if not hits:
            continue
        x0, x1 = min(x0, hits[0] // c), max(x1, hits[-1] // c)
        y0 = yy if y0 is None else y0
        y1 = yy
    return None if y0 is None else [x0, y0, x1 - x0 + 1, y1 - y0 + 1]


def colours(im: Img, x, y, w, h):
    x0, y0, x1, y1 = im.clip(x, y, w, h)
    seen = set()
    for yy in range(y0, y1):
        row = im.data[yy * im.stride + x0 * im.c:yy * im.stride + x1 * im.c]
        seen.update(row[i:i + im.c] for i in range(0, len(row), im.c))
    return len(seen)


def inside(box, outer):
    return (box[0] >= outer[0] and box[1] >= outer[1] and
            box[0] + box[2] <= outer[0] + outer[2] and box[1] + box[3] <= outer[1] + outer[3])


def rgb255(c):
    return ",".join(str(round(v * 255)) for v in c[:3])


def hexrgb(c):
    return "".join("%02x" % round(v * 255) for v in c[:3])


def luma(c):
    return sum(c[:3]) / 3


def hue_sat(c):
    r, g, b = c[:3]
    mx, mn = max(r, g, b), min(r, g, b)
    d = mx - mn
    if d == 0:
        h = 0.0
    elif mx == r:
        h = ((g - b) / d) % 6
    elif mx == g:
        h = (b - r) / d + 2
    else:
        h = (r - g) / d + 4
    return (h * 60) % 360, (d / mx if mx else 0.0)


def hue_diff(a, b):
    d = abs(a - b) % 360
    return min(d, 360 - d)


def rect(spec):
    v = [int(round(float(t))) for t in str(spec).split(",")]
    if len(v) != 4 or v[2] <= 0 or v[3] <= 0:
        raise ValueError(f"bad rectangle: {spec!r} (want x,y,w,h)")
    return v


def pcx_ppm(image, out) -> None:
    proc = pc("convert", str(image), str(out), capture=True)
    if proc.returncode != 0:
        fail(f"cannot export {image} as {out}\n{proc.stderr[-800:]}")


# --------------------------------------------------------------------------- 夹具
def fixture(name: str) -> Path:
    """首次使用时生成到 $FIX；打印只返回路径，生成日志在 $FIX/.<名字>.log。"""
    path = FIX / name
    if path.exists():
        return path
    FIX.mkdir(parents=True, exist_ok=True)
    log = FIX / f".{name}.log"
    if name in ("portrait.jpg", "landscape.jpg"):
        shutil.copy2(EX_DIR / "assets" / name, path)
        return path
    if name == "product.png":
        _run_fixture(log, lambda: _fx_bottle(path, 1600, 1200, "#3d8b63", "#1d4733", "AURORA"))
    elif name == "products":
        tmp = FIX / "products.tmp"
        shutil.rmtree(tmp, ignore_errors=True)
        tmp.mkdir(parents=True)
        def build():
            _fx_bottle(tmp / "bottle-green.jpg", 1600, 1200, "#3d8b63", "#1d4733", "AURORA")
            _fx_bottle(tmp / "bottle-blue.jpg", 1200, 1600, "#3b6fb6", "#1e3a68", "TIDE")
            _fx_bottle(tmp / "bottle-amber.png", 1500, 1500, "#d08a2e", "#7a4510", "EMBER")
        _run_fixture(log, build)
        if path.exists():
            shutil.rmtree(path)
        tmp.rename(path)
    elif name == "screenshot.png":
        _run_fixture(log, lambda: _fx_screenshot(path))
    elif name == "template.psd":
        _run_fixture(log, lambda: _fx_template(path))
    else:
        raise KeyError(f"unknown fixture: {name}")
    return path


def _run_fixture(log: Path, build) -> None:
    with log.open("w", encoding="utf-8") as fh:
        old = sys.stdout
        try:
            sys.stdout = fh
            build()
        except BaseException:
            sys.stdout = old
            tail = log.read_text(encoding="utf-8", errors="replace").splitlines()[-20:]
            print("\n".join(tail), file=sys.stderr)
            fail(f"could not generate fixture (log: {log})")
        finally:
            sys.stdout = old


def _fx_bottle(out, w, h, c1, c2, label) -> None:
    cx, floor = w // 2, h * 84 // 100
    bw, bh = w * 18 // 100, h * 50 // 100
    if h > w:
        bw, bh = w * 26 // 100, h * 46 // 100
    bx, by = cx - bw // 2, floor - bh
    nw, nh = bw * 38 // 100, bh * 16 // 100
    capw, caph = bw * 46 // 100, bh * 10 // 100
    lh, sw, sh, fs = bh * 30 // 100, bw * 16 // 10, h * 6 // 100, bw // 6
    pc_run([
        ("layer.newFillLayer.gradient", {"from": "#f4efe7", "to": "#d6cdbf", "angle": 90}),
        ("select.rect", {"x": cx - sw // 2, "y": floor - sh // 2, "width": sw, "height": sh,
                         "ellipse": True, "feather": sh // 3}),
        ("layer.new.layer", {"name": "Shadow", "opacity": 0.22}),
        ("edit.fill", {"contents": "color", "color": "#2b2118"}),
        ("select.deselect",),
        ("shape.create", {"kind": "roundedRect", "rect": [bx, by, bw, bh], "radii": bw // 6,
                          "fill": {"gradient": {"stops": [[0, c2], [0.35, c1], [1, c2]], "angle": 0}},
                          "name": "Body"}),
        ("shape.create", {"kind": "rect", "rect": [cx - nw // 2, by - nh, nw, nh + 4], "fill": c2, "name": "Neck"}),
        ("shape.create", {"kind": "roundedRect", "rect": [cx - capw // 2, by - nh - caph, capw, caph],
                          "radii": caph // 4, "fill": "#c9a227", "name": "Cap"}),
        ("shape.create", {"kind": "rect", "rect": [bx, by + bh * 38 // 100, bw, lh], "fill": "#22303c", "name": "Label"}),
        ("type.create", {"x": cx, "y": by + bh * 38 // 100 + lh * 62 // 100, "text": label, "size": fs,
                         "color": "#f3efe6", "align": "center", "name": "Brand"}),
        ("layer.flattenImage",),
        ("filter.noise.addNoise", {"amount": 3, "distribution": "gaussian", "monochromatic": True, "seed": 7}),
        ("layer.newAdjustmentLayer.photoFilter", {"filter": "warming85", "density": 30}),
        ("layer.flattenImage",),
    ], new={"width": w, "height": h, "background": "white", "name": "product"}, out=out, check=True)


def _fx_screenshot(out) -> None:
    pc_run([
        ("shape.create", {"kind": "rect", "rect": [0, 0, 1280, 64], "fill": "#1f2937", "name": "Header"}),
        ("type.create", {"x": 32, "y": 41, "text": "Billing Console", "size": 22, "color": "#ffffff"}),
        ("shape.create", {"kind": "rect", "rect": [0, 64, 240, 736], "fill": "#e5e7eb", "name": "Sidebar"}),
        ("type.create", {"x": 32, "y": 118, "text": "Overview", "size": 18, "color": "#111827"}),
        ("type.create", {"x": 32, "y": 158, "text": "Invoices", "size": 18, "color": "#4b5563"}),
        ("type.create", {"x": 32, "y": 198, "text": "API Keys", "size": 18, "color": "#4b5563"}),
        ("shape.create", {"kind": "roundedRect", "rect": [280, 96, 960, 180], "radii": 12, "fill": "#ffffff",
                          "stroke": {"width": 1, "color": "#d1d5db"}, "name": "ProfileCard"}),
        ("shape.create", {"kind": "ellipse", "rect": [312, 128, 96, 96], "fill": "#c08457", "name": "Avatar"}),
        ("type.create", {"x": 360, "y": 189, "text": "ZW", "size": 36, "color": "#ffffff", "align": "center",
                         "name": "Avatar initials"}),
        ("type.create", {"x": 440, "y": 166, "text": "Zhang Wei", "size": 26, "color": "#111827"}),
        ("type.create", {"x": 440, "y": 204, "text": "zhang.wei@example.com", "size": 20, "color": "#4b5563"}),
        ("shape.create", {"kind": "roundedRect", "rect": [280, 308, 960, 220], "radii": 12, "fill": "#ffffff",
                          "stroke": {"width": 1, "color": "#d1d5db"}, "name": "SecretsCard"}),
        ("type.create", {"x": 312, "y": 356, "text": "API key", "size": 18, "color": "#6b7280"}),
        ("type.create", {"x": 470, "y": 356, "text": "sk-live-4f9a2c7e1b8d55e0a3", "size": 20, "color": "#111827"}),
        ("type.create", {"x": 312, "y": 420, "text": "Card", "size": 18, "color": "#6b7280"}),
        ("type.create", {"x": 470, "y": 420, "text": "4242 4242 4242 4242", "size": 20, "color": "#111827"}),
        ("type.create", {"x": 312, "y": 484, "text": "Plan", "size": 18, "color": "#6b7280"}),
        ("type.create", {"x": 470, "y": 484, "text": "Pro (annual)", "size": 20, "color": "#111827"}),
    ], new={"width": 1280, "height": 800, "background": "#f5f6f8", "name": "screenshot"}, out=out, check=True)


def _fx_template(out) -> None:
    land = pcx_native(fixture("landscape.jpg"))
    pc_run([
        ("file.placeEmbedded", {"path": land, "scale": 110, "center": [540, 430]}),
        ("layer.renameLayer", {"name": "Photo"}),
        ("type.create", {"x": 540, "y": 1000, "text": "SUMMER SALE", "size": 96, "color": "#ffffff",
                         "align": "center", "name": "TITLE"}),
        ("type.create", {"x": 540, "y": 1090, "text": "2026-07-01 — 07-15", "size": 40, "color": "#cbd5e1",
                         "align": "center", "name": "DATE"}),
        ("type.create", {"x": 540, "y": 1230, "text": "¥199 起", "size": 72, "color": "#fbbf24",
                         "align": "center", "name": "PRICE"}),
        ("shape.create", {"kind": "star", "rect": [840, 60, 180, 180], "sides": 12, "starRatio": 0.78,
                          "fill": "#ef4444", "name": "Badge"}),
        ("type.create", {"x": 930, "y": 166, "text": "-30%", "size": 40, "color": "#ffffff",
                         "align": "center", "name": "BADGE_TEXT"}),
    ], new={"width": 1080, "height": 1350, "background": "#0f172a", "name": "promo-template"}, out=out, check=True)


# --------------------------------------------------------------------------- 入口
def run(main) -> None:
    """每个案例文件的入口：捕获异常统一报 FAIL，并保持退出码语义。"""
    try:
        main(sys.argv[1:])
    except SystemExit:
        raise
    except pclib.CliNotFound as exc:
        print(f"photocraft-cli not found: {exc}", file=sys.stderr)
        sys.exit(2)
    except pclib.PcError as exc:
        fail(str(exc))
    except BaseException:
        traceback.print_exc()
        sys.exit(1)
