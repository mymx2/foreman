#!/usr/bin/env python3
"""WPS 表格本地 COM 命令行工具（仅 Windows + 已安装 WPS + pywin32）。

子命令:
  ping         探测 COM 是否可用（自报版本、是否已有工作簿）
  sheets       列出工作表与已用区域
  read         按区域读取，输出 JSON 或 TSV
  write        按区域批量写入（默认写副本，写完回读校验）
  pivot        在副本上创建数据透视表
  export-pdf   导出 PDF

退出码:
  0 成功  1 未预期的内部错误  2 用法/参数/格式错误  3 文件被占用  4 无此工作表
  5 COM 调用失败  6 回读校验失败  7 输出冲突或未确认原地写入
  8 备份校验失败（已中止）  130 用户中断

设计约束: 新建 DispatchEx 实例、Visible=False、退出前 Quit、错误只输出单行中文。
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import re
import shutil
import sys
import time

MAX_ROW = 1048576
MAX_COL = 16384
XL_DATABASE = 1
XL_PDF = 0
AGG = {
    "sum": -4157,
    "count": -4112,
    "average": -4106,
    "avg": -4106,
    "max": -4136,
    "min": -4139,
}
SUPPORTED_SUFFIX = {".xlsx", ".xlsm", ".xls", ".et", ".ett"}
CELL_RE = re.compile(r"^([A-Za-z]{1,3})(\d{1,7})$")
NO_BACKUP_WARNING = "[警告] 本次未生成备份（--no-backup），原文件可能处于部分写入状态，请人工检查\n"
BLANK_SCAN_LIMIT = 200_000


class CliError(Exception):
    def __init__(self, message: str, code: int = 2) -> None:
        super().__init__(message)
        self.message = message
        self.code = code


def fail(message: str, code: int = 2):
    raise CliError(message, code)


# ---------------------------------------------------------------- 脱敏

_SCHEME_RE = re.compile(r"^([A-Za-z][A-Za-z0-9+.-]*):/*(.*)$")


def _is_download_url(s: str) -> bool:
    """与 parse_workbook.py 同款：前导空格、引号、单斜杠、签名查询串都算地址。"""
    t = s.strip().strip("'\"<>").lower()
    if "://" in t or t.startswith(("http:/", "https:/")):
        return True
    return "signature=" in t and "?" in t


def _url_host(s: str) -> str:
    """只留域名（含端口），路径、查询与签名参数一律不回显。"""
    t = s.strip().strip("'\"<>")
    m = _SCHEME_RE.match(t)
    rest = m.group(2) if m else t
    return rest.split("/", 1)[0].split("?", 1)[0].rsplit("@", 1)[-1]


def _redact(value: str) -> str:
    """报错回显脱敏：URL 形态截到第一个 ? 之前，只留域名。"""
    t = value.strip().strip("'\"<>")
    if not (_is_download_url(value) or ("?" in t and ("/" in t or "=" in t))):
        return value
    head, sep, _ = t.partition("?")
    if sep:
        return head
    host = _url_host(t)
    return f"{host}/…" if host else "[下载地址]"


class _Parser(argparse.ArgumentParser):
    """argparse 的 error() 原样回显入参，这里过一遍脱敏，退出码仍是 2。"""

    def error(self, message):
        self.print_usage(sys.stderr)
        sys.stderr.write(f"{self.prog}: error: {_redact(message)}\n")
        raise SystemExit(2)


# ---------------------------------------------------------------- 地址解析


def col_to_num(letters: str) -> int:
    n = 0
    for ch in letters.upper():
        n = n * 26 + (ord(ch) - 64)
    return n


def num_to_col(n: int) -> str:
    out = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        out = chr(65 + rem) + out
    return out


def parse_cell(text: str):
    m = CELL_RE.match(text.strip())
    if not m:
        fail(f"单元格地址无效：{text}，应形如 A1")
    row, col = int(m.group(2)), col_to_num(m.group(1))
    if row < 1 or row > MAX_ROW or col < 1 or col > MAX_COL:
        fail(f"区域越界：{text} 超出工作表上限（{MAX_ROW} 行 × {MAX_COL} 列）")
    return row, col


def parse_range(text: str):
    """返回 (sheet_or_None, r1, c1, r2, c2)。"""
    sheet = None
    body = text.strip()
    if "!" in body:
        sheet, body = body.rsplit("!", 1)
        sheet = sheet.strip("'\"")
    if ":" in body:
        left, right = body.split(":", 1)
        r1, c1 = parse_cell(left)
        r2, c2 = parse_cell(right)
    else:
        r1, c1 = parse_cell(body)
        r2, c2 = r1, c1
    return sheet, min(r1, r2), min(c1, c2), max(r1, r2), max(c1, c2)


def addr(r1: int, c1: int, r2: int, c2: int) -> str:
    if r1 == r2 and c1 == c2:
        return f"{num_to_col(c1)}{r1}"
    return f"{num_to_col(c1)}{r1}:{num_to_col(c2)}{r2}"


def safe_address(rng) -> str:
    """WPS 里部分对象的 Address 是属性而非方法，两种都兼容。"""
    try:
        value = rng.Address
        return str(value(False, False)) if callable(value) else str(value)
    except Exception:  # noqa: BLE001
        return ""


# ---------------------------------------------------------------- 文件检查


def check_local(path_text: str) -> str:
    t = path_text.strip().strip("'\"<>")
    lower = t.lower()
    if lower.startswith(("http://", "https://", "kdocs://", "wps://")) or _is_download_url(t):
        fail("云文档不支持：COM 只能打开本机磁盘上的文件，请先另存到本地")
    p = os.path.abspath(os.path.expanduser(path_text))
    if not os.path.isfile(p):
        fail(f"文件不存在：{p}")
    suffix = os.path.splitext(p)[1].lower()
    if suffix not in SUPPORTED_SUFFIX:
        fail(f"不支持的本地格式：{suffix or '无扩展名'}；支持 .xlsx/.xlsm/.xls/.et/.ett")
    return p


def lock_files(path: str):
    """返回同目录下疑似指向该文件的 WPS/Excel 锁文件。

    锁文件名是 `~$` + 原文件名；文件名过长时 WPS/Excel 会截掉原名开头的字符，
    所以只认两种严格关系：完全同名，或 tail 恰好等于原名去掉前两个字符。
    裸 endswith/子串匹配会让 `~$报表.xlsx` 命中 `旧报表.xlsx` 这类无关文件。
    Windows 文件系统不区分大小写，只在 nt 上折叠大小写，其它平台保持严格比较。
    """
    folder, name = os.path.split(path)
    fold = str.lower if os.name == "nt" else (lambda s: s)
    want = fold(name)
    truncated = fold(name[2:])
    hits = []
    try:
        # 不用 glob：目录名里的 [ ] 会被当成通配符字符类，导致锁文件漏检
        entries = list(os.scandir(folder))
    except OSError:  # 目录读不到按无锁处理
        return hits
    for entry in entries:
        if not entry.name.startswith("~$"):
            continue
        tail = entry.name[2:]
        if not tail:
            continue
        cmp_tail = fold(tail)
        if cmp_tail == want or (len(tail) < len(name) and cmp_tail == truncated):
            hits.append(entry.path)
    return hits


def guard_occupied(path: str, mutating: bool) -> None:
    hits = lock_files(path)
    if not hits:
        return
    lock_name = os.path.basename(hits[0])
    if mutating:
        fail(f"文件正被占用（检测到锁文件 {lock_name}），请先在 WPS 中关闭该文件", 3)
    print(f"提示：检测到锁文件 {lock_name}，按只读方式读取", file=sys.stderr)


def resolve_out(src: str, out: str | None) -> str:
    if out:
        return os.path.abspath(os.path.expanduser(out))
    stem, suffix = os.path.splitext(src)
    return f"{stem}_edited{suffix}"


def guard_out(out_path: str, force: bool) -> None:
    if os.path.exists(out_path) and not force:
        fail(f"输出文件已存在：{out_path}；加 --force 覆盖或用 --out 指定新路径", 7)


def same_file(a: str, b: str) -> bool:
    """判断两个路径是否指向同一个文件。

    先比规范化后的字符串（挡住大小写、相对路径、sub/.. 三种写法），
    再在两边都存在时用 samefile 兜硬链接；判不了就当不同文件。
    """
    if os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b)):
        return True
    try:
        return os.path.samefile(a, b)
    except OSError:  # noqa: BLE001 - 文件不存在或平台不支持时按不同文件处理
        return False


def file_digest(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def restore_backup(backup, target: str, reason: str = "校验未通过") -> None:
    """用备份覆盖目标并报告结果；调用点必须在目标工作簿 Close 之后。

    reason 写进提示，区分触发点（回读校验不一致 / 保存失败）。
    """
    if not backup:
        return
    try:
        shutil.copy2(backup, target)
        sys.stderr.write(f"[已恢复] {reason}，已用备份覆盖：{backup}\n")
    except OSError as exc:
        sys.stderr.write(f"[恢复失败] 备份保留在 {backup}，请手工还原（{_short(exc)}）\n")


def discard_failed_copy(target: str, created: bool, saved: bool = False) -> None:
    """副本模式下写入失败时删掉刚生成的副本，避免留下看着像成功产物的文件。

    已经 Save 成功过的产物一律保留：那已经是 WPS 真实写出的文件，删掉等于毁掉成果。
    """
    if not created or saved or not os.path.exists(target):
        return
    try:
        os.remove(target)
        sys.stderr.write(f"[已清理] 未完成写入的副本已删除：{target}\n")
    except OSError as exc:
        sys.stderr.write(f"[清理失败] 无法删除未完成写入的副本 {target}：{_short(exc)}\n")


# ---------------------------------------------------------------- COM 会话


def _com():
    try:
        import pythoncom  # noqa: F401
        import win32com.client  # noqa: F401
        from win32com.client import VARIANT  # noqa: F401
    except ImportError:
        fail("缺少 pywin32：请先执行 pip install pywin32")
    import pythoncom
    import win32com.client

    return pythoncom, win32com.client


class Session:
    """新建静默实例，退出时关闭工作簿并 Quit。"""

    def __init__(self) -> None:
        self.pythoncom, self.win32 = _com()
        self.app = None
        self.dirty = False

    def __enter__(self):
        self.pythoncom.CoInitialize()
        last = None
        for progid in ("Ket.Application", "ET.Application"):
            try:
                self.app = self.win32.DispatchEx(progid)
                break
            except Exception as exc:  # noqa: BLE001 - 回退到下一个 ProgID
                last = exc
        if self.app is None:
            self.pythoncom.CoUninitialize()
            fail(f"无法启动 WPS 表格 COM 实例（已试 Ket.Application / ET.Application）：{_short(last)}", 5)
        for prop, value in (
            ("Visible", False),
            ("DisplayAlerts", False),
            ("EnableEvents", False),
            ("AskToUpdateLinks", False),
            ("ScreenUpdating", False),
        ):
            try:
                setattr(self.app, prop, value)
            except Exception:  # noqa: BLE001 - 属性缺失不致命
                pass
        return self

    def quit(self) -> None:
        if self.app is None:
            return
        for _ in range(10):  # Close 静默无效时不能无限循环
            try:
                if self.app.Workbooks.Count <= 0:
                    break
                self.app.Workbooks.Item(1).Close(SaveChanges=False)
            except Exception:  # noqa: BLE001 - 关不掉就退出循环，交给残留检查
                break
        leftover = 0
        try:
            leftover = int(self.app.Workbooks.Count)
        except Exception:  # noqa: BLE001 - 取不到数量就不做残留判断
            pass
        quit_failed = False
        try:
            self.app.Quit()
        except Exception:  # noqa: BLE001
            quit_failed = True
        self.app = None
        try:
            self.pythoncom.CoUninitialize()
        except Exception:  # noqa: BLE001
            pass
        if leftover > 0 or quit_failed:
            sys.stderr.write("[警告] WPS 实例未能正常退出，请检查残留 et.exe\n")

    def __exit__(self, exc_type, exc, tb):
        self.quit()
        return False

    def open(self, path: str, read_only: bool):
        try:
            return self.app.Workbooks.Open(path, 0, bool(read_only))
        except Exception as exc:  # noqa: BLE001
            raise CliError(_map_com_error(exc, path), 5) from None


def _short(exc) -> str:
    if exc is None:
        return "未知原因"
    try:
        text = exc.strerror  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        text = None
    if not text:
        text = str(exc)
    return " ".join(str(text).split())[:180]


def _map_com_error(exc, path: str | None = None) -> str:
    text = _short(exc)
    low = text.lower()
    if "0x800a03ec" in low or "不能取得类" in text or "无法获取" in text:
        return f"COM 调用失败：对象或区域无效（{text}）"
    if "0x80070020" in low or "另一个程序" in text or "正由另一" in text:
        return "文件正被占用：请关闭 WPS 中已打开的同名文件后重试"
    if "密码" in text or "password" in low:
        return "文件已加密：需要密码的表格无法自动打开，请先解密再试"
    if "格式" in text and ("无效" in text or "不匹配" in text):
        return f"文件格式无法被 WPS 打开：{path or ''}".strip()
    return f"COM 调用失败：{text}"


def get_sheet(wb, name: str | None):
    if not name:
        try:
            return wb.Worksheets(1)
        except Exception as exc:  # noqa: BLE001
            raise CliError(_map_com_error(exc), 5) from None
    try:
        return wb.Worksheets(name)
    except Exception:  # noqa: BLE001
        names = list_sheets(wb)
        raise CliError(f"无此工作表：{name}；现有工作表：{'、'.join(names) or '无'}", 4) from None


def list_sheets(wb):
    names = []
    try:
        for i in range(1, wb.Worksheets.Count + 1):
            names.append(str(wb.Worksheets.Item(i).Name))
    except Exception:  # noqa: BLE001
        pass
    return names


def used_bounds(ws):
    try:
        ur = ws.UsedRange
        r1 = int(ur.Row)
        c1 = int(ur.Column)
        r2 = r1 + int(ur.Rows.Count) - 1
        c2 = c1 + int(ur.Columns.Count) - 1
        return max(r1, 1), max(c1, 1), r2, c2
    except Exception:  # noqa: BLE001
        return 1, 1, 1, 1


def _range_is_blank(ur) -> bool:
    """已用区域是否全是空格子：单格取标量判，多格取二维元组摊平后判。

    值读不出来时返回 False（按非空保守处理，追加到末行+1）：把「值读失败」当成空表
    会退到 A1 并覆盖表头，比多留一行危险得多。
    超过 BLANK_SCAN_LIMIT 个格子同样按非空处理：那种体量几乎不可能是「只有格式」。
    """
    if int(ur.Rows.Count) * int(ur.Columns.Count) > BLANK_SCAN_LIMIT:
        return False
    try:
        value = ur.Value2
        if not isinstance(value, (list, tuple)):
            return value in (None, "")
        for row in value:
            if isinstance(row, (list, tuple)):
                for cell in row:
                    if cell not in (None, ""):
                        return False
            elif row not in (None, ""):
                return False
        return True
    except Exception:  # noqa: BLE001 - 值读不出来按非空处理，绝不退 A1
        return False


def append_anchor(ws):
    """追加写入的落点：全空的已用区域落 A1，否则落末行+1。

    WPS 对空表把 UsedRange 报成 A1；设过列宽/边框、或填过又删的表可能报成 A1:C3 而全空。
    两种形状都按空表处理，否则首条数据会落在 A2/A4，上方永久留空。
    只有 UsedRange / Row / Rows.Count 这些结构属性本身取不到时才退 A1。
    """
    try:
        ur = ws.UsedRange
        if _range_is_blank(ur):
            return 1, 1
        return int(ur.Row) + int(ur.Rows.Count), int(ur.Column)
    except Exception:  # noqa: BLE001 - 结构信息取不到时按空表落 A1，不从第 2 行猜
        return 1, 1


def norm_value(v):
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        if isinstance(v, float):
            if v != v or v in (float("inf"), float("-inf")):
                return str(v)
            if v.is_integer() and abs(v) < 1e15:
                return int(v)
        return v
    if isinstance(v, _dt.datetime):
        return v.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(v, _dt.date):
        return v.isoformat()
    return str(v)


def read_grid(rng, rows: int, cols: int):
    try:
        raw = rng.Value2
    except Exception as exc:  # noqa: BLE001
        raise CliError(_map_com_error(exc), 5) from None
    if rows == 1 and cols == 1:
        return [[norm_value(raw)]]
    grid = None
    if isinstance(raw, (list, tuple)) and len(raw) > 0:
        if rows == 1:
            values = list(raw)
            if len(values) == cols:
                grid = [[norm_value(x) for x in values]]
        else:
            if len(raw) == rows:
                grid = []
                for row in raw:
                    if isinstance(row, (list, tuple)) and len(row) == cols:
                        grid.append([norm_value(x) for x in row])
                    else:
                        grid = None
                        break
    if grid is None:  # 形状不符合预期时退回逐格读取
        try:
            grid = [
                [norm_value(rng.Cells(r, c).Value2) for c in range(1, cols + 1)]
                for r in range(1, rows + 1)
            ]
        except Exception as exc:  # noqa: BLE001
            raise CliError(_map_com_error(exc), 5) from None
    return grid


_DATE_LIKE = re.compile(r"^\d{4}[-/.]\d{1,2}[-/.]\d{1,2}([ T]\d{1,2}:\d{2}(:\d{2})?)?$")
_NUM_LIKE = re.compile(r"^[+-]?(\d+(\.\d+)?|\.\d+)$")
_SCI_LIKE = re.compile(r"^[+-]?\d+(\.\d+)?[eE][+-]?\d+$")
# WPS 对这些形状的字符串也会自动转型：日期、时间、百分比、货币、布尔。
# 漏掉任何一种，回读都拿不到原文：布尔更隐蔽——"FALSE" 变 False 后值比对必然失败，
# "TRUE" 变 True 后 bool 比较却能骗过校验。
_TEXT_LIKE = (
    re.compile(r"^\d{1,4}[-/.]\d{1,2}([-/.]\d{1,2})?$"),
    re.compile(r"^\d{1,2}:\d{2}(:\d{2})?$"),
    re.compile(r"^[+-]?\d+(\.\d+)?%$"),
    re.compile(r"^[+-]?[¥$]?[\d,]+(\.\d+)?$"),
    re.compile(r"^(TRUE|FALSE|true|false)$"),
)


def _as_text(v, text_only: bool = False):
    """强制写入为文本：WPS 会把 '2021-12-16' 与 '7' 自动转成日期序列号/数字，破坏来源类型。

    text_only 打开时 `=` 开头的字符串同样前置单引号，避免文本被当成活公式执行；
    默认关闭，保留写入公式的能力。
    """
    if not isinstance(v, str):
        return v
    if v.startswith("="):
        return "'" + v if text_only else v
    if text_only and v.startswith(("+", "-", "@")):
        # Excel/WPS 家族里 + - @ 同样按公式解析，--text-only 下必须一并强制文本
        return "'" + v
    if (
        _DATE_LIKE.match(v)
        or _NUM_LIKE.match(v)
        or _SCI_LIKE.match(v)
        or any(p.match(v) for p in _TEXT_LIKE)
    ):
        return "'" + v
    return v


def write_grid(rng, data, text_only: bool = False):
    rows, cols = len(data), len(data[0])
    if rows == 1 and cols == 1:
        try:
            rng.Value2 = _as_text(data[0][0], text_only)
        except Exception as exc:  # noqa: BLE001 - 写盘失败必须落 COM 码并交给恢复逻辑
            raise CliError(_map_com_error(exc), 5) from None
        return
    pythoncom, _ = _com()
    from win32com.client import VARIANT

    payload = [["" if v is None else _as_text(v, text_only) for v in row] for row in data]
    try:
        rng.Value2 = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_VARIANT, payload)
    except Exception as exc:  # noqa: BLE001
        raise CliError(_map_com_error(exc), 5) from None


def values_equal(expected, actual) -> bool:
    if expected is None or expected == "":
        return actual is None or actual == ""
    if isinstance(expected, bool) or isinstance(actual, bool):
        return bool(expected) == bool(actual)
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        return abs(float(expected) - float(actual)) <= 1e-9 * max(1.0, abs(float(expected)))
    return str(expected) == str(actual)


def _grid_shape_ok(grid, rows: int, cols: int) -> bool:
    if not isinstance(grid, (list, tuple)) or len(grid) != rows:
        return False
    return all(isinstance(row, (list, tuple)) and len(row) == cols for row in grid)


def verify_grid(grid, actual, formulas=None, text_only: bool = False) -> None:
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    if formulas is not None and not _grid_shape_ok(formulas, rows, cols):
        # 公式矩阵形状不对就当没读到，绝不能拿它去索引而抛 IndexError
        formulas = None
    problems = []
    for r, row in enumerate(grid):
        for c, expected in enumerate(row):
            if not text_only and isinstance(expected, str) and expected.strip().startswith("="):
                if formulas is None:
                    continue  # 公式读不到就没法比对，只校验值，不判失败
                got_formula = formulas[r][c]
                left = expected.strip().lstrip("=").casefold()
                right = str(got_formula).strip().lstrip("=").casefold()
                if left != right:
                    problems.append(f"{addr(r + 1, c + 1, r + 1, c + 1)} 公式未写入")
            else:
                got = actual[r][c]
                # 写入时 _as_text 会给部分值加前导单引号强制文本；WPS 回读可能保留也可能剥掉，
                # 校验侧统一按剥掉后的值比，避免两种呈现方式下结果不一致。
                if (isinstance(got, str) and got.startswith("'")
                        and not (isinstance(expected, str) and expected.startswith("'"))):
                    got = got[1:]
                if not values_equal(expected, got):
                    problems.append(f"{addr(r + 1, c + 1, r + 1, c + 1)} 期望 {expected!r} 实际 {got!r}")
            if len(problems) >= 5:
                break
        if len(problems) >= 5:
            break
    if problems:
        fail("回读校验失败：" + "；".join(problems), 6)


# ---------------------------------------------------------------- 数据输入


def load_matrix(args):
    text = None
    explicit_json = False
    source_path = None
    if args.json:
        text = args.json
        explicit_json = True
    elif args.data in (None, "-"):
        if args.data is None:
            fail("缺少写入数据：用 --data <json|tsv 文件>、--data - 读标准输入，或 --json '<二维数组>'")
        try:
            text = sys.stdin.read()
        except UnicodeDecodeError as exc:  # 二进制内容不能带着 traceback 逃出去
            fail(f"标准输入不是 UTF-8 文本：{_short(exc)}", 2)
    else:
        source_path = os.path.abspath(os.path.expanduser(args.data))
        if not os.path.isfile(source_path):
            fail(f"数据文件不存在：{source_path}")
        try:
            with open(source_path, "r", encoding="utf-8-sig", newline="") as fh:
                text = fh.read()
        except UnicodeDecodeError as exc:
            fail(f"数据文件不是 UTF-8 文本：{source_path}（{_short(exc)}）；二进制内容请改用 --json 二维数组", 2)
        except OSError as exc:
            fail(f"数据文件读取失败：{source_path}（{_short(exc)}）", 2)

    stripped = text.lstrip("\ufeff \r\n\t")
    if stripped.startswith("["):
        try:
            data = json.loads(stripped)
        except json.JSONDecodeError as exc:
            fail(f"写入数据不是合法 JSON：{exc.msg}（行 {exc.lineno} 列 {exc.colno}）")
        if not isinstance(data, list) or not data or not all(isinstance(r, list) for r in data):
            fail("写入数据必须是二维数组，如 [[\"姓名\",\"金额\"],[\"张三\",100]]")
        width = len(data[0])
        if width == 0:
            fail("写入数据首行为空，无法确定列数")
        for i, row in enumerate(data, start=1):
            if len(row) != width:
                fail(f"写入数据第 {i} 行有 {len(row)} 列，与首行的 {width} 列不一致")
        return data

    if stripped.startswith("{"):
        fail("写入数据是 JSON 对象，不是二维数组；需要形如 [[\"姓名\",\"金额\"],[\"张三\",100]]", 2)
    if explicit_json:
        fail("--json 只接受二维数组，如 [[\"姓名\",\"金额\"],[\"张三\",100]]", 2)
    suffix = os.path.splitext(source_path)[1].lower() if source_path else ""
    if source_path and suffix not in (".tsv", ".txt"):
        fail(
            f"看起来是 CSV 或指纹文件，不是二维数组：{source_path}；"
            "TSV 请用 .tsv/.txt 后缀，或改用 --json 传入二维数组",
            2,
        )

    lines = stripped.splitlines()
    while lines and lines[-1].strip() == "":
        lines.pop()  # 只裁末尾空行；中间空行会成为宽度不符的行，必须报错而不是静默丢掉
    if not lines:
        fail("写入数据为空")
    rows = [ln.split("\t") for ln in lines]
    width = len(rows[0])
    for i, row in enumerate(rows, start=1):
        if len(row) != width:
            fail(f"TSV 第 {i} 行有 {len(row)} 列，与首行的 {width} 列不一致")
    return rows


# ---------------------------------------------------------------- 子命令


def cmd_ping(args) -> int:
    with Session() as s:
        info = {
            "ok": True,
            "version": str(getattr(s.app, "Version", "")),
            "name": str(getattr(s.app, "Name", "")),
            "workbooks": int(s.app.Workbooks.Count),
            "note": "Name 报 Microsoft Excel 属正常：WPS 的对象模型与 Excel 兼容",
        }
    print(json.dumps(info, ensure_ascii=False, indent=2))
    return 0


def cmd_sheets(args) -> int:
    src = check_local(args.file)
    guard_occupied(src, mutating=False)
    with Session() as s:
        wb = s.open(src, read_only=True)
        items = []
        try:
            for i in range(1, wb.Worksheets.Count + 1):
                ws = wb.Worksheets.Item(i)
                r1, c1, r2, c2 = used_bounds(ws)
                items.append(
                    {
                        "name": str(ws.Name),
                        "index": i,
                        "visible": int(ws.Visible) == -1,
                        "usedRange": addr(r1, c1, r2, c2),
                        "rows": r2 - r1 + 1,
                        "cols": c2 - c1 + 1,
                    }
                )
        except Exception as exc:  # noqa: BLE001 - 枚举失败按 COM 调用失败处理
            raise CliError(_map_com_error(exc, src), 5) from None
        result = {"ok": True, "file": src, "sheets": items}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_read(args) -> int:
    src = check_local(args.file)
    guard_occupied(src, mutating=False)

    want_sheet, r1, c1, r2, c2 = parse_range(args.range) if args.range else (None, None, None, None, None)
    sheet_arg = args.sheet
    if sheet_arg and "!" in sheet_arg:
        # 帮助文本承诺 --sheet 也可写成 表名!A1:D10
        name_part, body = sheet_arg.rsplit("!", 1)
        sheet_arg = name_part.strip("'\"") or None
        if r1 is None and body.strip():
            _, r1, c1, r2, c2 = parse_range(body)
    sheet_arg = sheet_arg or want_sheet

    with Session() as s:
        wb = s.open(src, read_only=True)
        ws = get_sheet(wb, sheet_arg)
        ur1, uc1, ur2, uc2 = used_bounds(ws)
        used_text = addr(ur1, uc1, ur2, uc2)
        if r1 is None:
            r1, c1, r2, c2 = ur1, uc1, ur2, uc2
        elif not args.allow_blank and (r1 < ur1 or c1 < uc1 or r2 > ur2 or c2 > uc2):
            fail(
                f"区域越界：{addr(r1, c1, r2, c2)} 超出已用区域 {used_text}；"
                "读取空白填充请加 --allow-blank",
                2,
            )
        try:
            rng = ws.Range(addr(r1, c1, r2, c2))
        except Exception as exc:  # noqa: BLE001
            raise CliError(_map_com_error(exc), 5) from None
        rows, cols = r2 - r1 + 1, c2 - c1 + 1
        grid = read_grid(rng, rows, cols)
        payload = {
            "ok": True,
            "file": src,
            "sheet": str(ws.Name),
            "range": addr(r1, c1, r2, c2),
            "rows": rows,
            "cols": cols,
            "values": grid,
        }
        if args.formulas:
            fgrid = read_formulas(rng, rows, cols)
            payload["formulas"] = fgrid
            if fgrid is None:
                payload["warnings"] = ["公式未读到，未校验"]

    if args.format == "tsv":
        for row in payload["values"]:
            print("\t".join("" if v is None else str(v) for v in row))
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def read_formulas(rng, rows: int, cols: int):
    """读取公式矩阵；整体读不到时返回 None，调用方须跳过公式比对而不是判失败。"""
    try:
        raw = rng.Formula
    except Exception:  # noqa: BLE001
        return None
    if raw is None:
        return None
    if rows == 1 and cols == 1:
        return [[str(raw)]]
    if isinstance(raw, (list, tuple)) and len(raw) > 0:
        if rows == 1:
            # WPS 对单行区域返回扁平元组，逐行迭代会把字符串拆成单个字符
            values = list(raw)
            if len(values) == cols:
                return None if any(v is None for v in values) else [[str(x) for x in values]]
            if len(values) == 1 and isinstance(values[0], (list, tuple)) and len(values[0]) == cols:
                inner = list(values[0])
                return None if any(v is None for v in inner) else [[str(x) for x in inner]]
        elif len(raw) == rows:
            grid = []
            for row in raw:
                if isinstance(row, (list, tuple)) and len(row) == cols:
                    cells = list(row)
                    if any(v is None for v in cells):
                        return None
                    grid.append([str(x) for x in cells])
                else:
                    grid = None
                    break
            if grid is not None:
                return grid
    try:
        grid = []
        for r in range(1, rows + 1):
            line = []
            for c in range(1, cols + 1):
                value = rng.Cells(r, c).Formula
                if value is None:
                    return None
                line.append(str(value))
            grid.append(line)
        return grid
    except Exception:  # noqa: BLE001
        return None


def cmd_write(args) -> int:
    args.dry_run = not getattr(args, "apply", False)
    src = check_local(args.file)
    data = load_matrix(args)
    rows, cols = len(data), len(data[0])

    guard_occupied(src, mutating=True)
    if args.in_place:
        if args.out:
            fail("--in-place 会忽略 --out，两者不能同时给；去掉 --out 或改回副本模式", 7)
        if not args.i_know_this_modifies_original:
            fail(
                "原地写入需要显式确认：加 --in-place --i-know-this-modifies-original；"
                "或去掉 --in-place 使用默认副本输出",
                7,
            )
        target = src
    else:
        target = resolve_out(src, args.out)
        if same_file(target, src):
            fail(
                "输出路径与 --file 相同；要改原件请用 --in-place --i-know-this-modifies-original",
                7,
            )

    sheet_arg, r1, c1, r2, c2 = parse_range(args.range) if args.range else (None, None, None, None, None)
    sheet_arg = args.sheet or sheet_arg

    backup = None
    warnings = []
    with Session() as s:
        # 先定位目标区域：dry-run 也要给出真实落点
        probe = s.open(src, read_only=True)
        try:
            pws = get_sheet(probe, sheet_arg)
            try:
                sheet_name = str(pws.Name)
                if r1 is None:
                    r1, c1 = append_anchor(pws)  # 全空落 A1，否则末行 + 1，追加而非覆盖
                    r2, c2 = r1, c1
            except Exception as exc:  # noqa: BLE001
                raise CliError(_map_com_error(exc), 5) from None
        finally:
            try:
                probe.Close(SaveChanges=False)
            except Exception:  # noqa: BLE001 - 只读探针，关不掉只告警，不升级成失败
                sys.stderr.write("[警告] 探测工作簿未能关闭，请检查残留 et.exe\n")

        given_rows, given_cols = r2 - r1 + 1, c2 - c1 + 1
        if given_rows == 1 and given_cols == 1:
            r2, c2 = r1 + rows - 1, c1 + cols - 1
        elif (given_rows, given_cols) != (rows, cols):
            fail(
                f"数据形状不符：区域 {addr(r1, c1, r2, c2)} 为 {given_rows}×{given_cols}，"
                f"数据为 {rows}×{cols}；只给左上角单元格可自动扩展",
                2,
            )
        if r2 > MAX_ROW or c2 > MAX_COL:
            fail(f"区域越界：写入后需到 {addr(r1, c1, r2, c2)}，超出工作表上限", 2)
        target_addr = addr(r1, c1, r2, c2)

        if args.dry_run:
            print(
                json.dumps(
                    {
                        "ok": True,
                        "dryRun": True,
                        "file": target,
                        "sheet": sheet_name,
                        "range": target_addr,
                        "cells": rows * cols,
                        "inPlace": bool(args.in_place),
                        "note": "未写入任何内容；确认落点后加 --apply 执行",
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0

        target_created = False
        saved = False
        recovered = False
        wb = None
        if args.in_place:
            if not args.no_backup:
                stem, suffix = os.path.splitext(src)
                stamp = _dt.datetime.now().strftime("%Y%m%d%H%M%S")
                backup = f"{stem}.{stamp}.bak{suffix}"
                seq = 2
                while os.path.exists(backup):  # 同一秒内多次写入不能顶掉上一份备份
                    backup = f"{stem}.{stamp}-{seq}.bak{suffix}"
                    seq += 1
                try:
                    shutil.copy2(src, backup)
                except OSError as exc:
                    try:
                        if os.path.exists(backup):
                            os.remove(backup)  # 删掉写了一半的备份，不留残骸
                    except OSError:
                        pass
                    fail(f"备份失败：无法写入 {backup}（{_short(exc)}），已中止，原文件未改动", 8)
                if file_digest(backup) != file_digest(src):
                    fail(f"备份校验失败：{backup} 与原文件哈希不一致，已中止", 8)
        else:
            guard_out(target, args.force)
            os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
            target_created = not os.path.exists(target)
            try:
                shutil.copy2(src, target)
            except OSError:
                discard_failed_copy(target, target_created, saved=False)
                raise

        try:
            wb = s.open(target, read_only=False)
            ws = get_sheet(wb, sheet_name)
            try:
                rng = ws.Range(target_addr)
            except Exception as exc:  # noqa: BLE001
                raise CliError(_map_com_error(exc, target), 5) from None
            write_grid(rng, data, bool(getattr(args, "text_only", False)))
            try:
                wb.Save()
            except Exception as exc:  # noqa: BLE001
                # 原文件可能已被写坏，先把文件从 WPS 手里放出来，覆盖才有机会成功
                try:
                    wb.Close(SaveChanges=False)
                except Exception:  # noqa: BLE001 - 关不掉也不能阻断恢复
                    pass
                if args.in_place and not backup:
                    sys.stderr.write(NO_BACKUP_WARNING)
                restore_backup(backup, target, "保存失败")
                recovered = True
                raise CliError(_map_com_error(exc, target), 5) from None
            saved = True
            try:
                wb.Close(SaveChanges=True)
            except Exception as exc:  # noqa: BLE001
                # 原地模式必须给「文件没变」的保证：Close 失败说明落盘状态不确定，
                # 用备份盖回写入前的内容；副本模式相反——Save 已把成果写进文件，删掉才是毁数据
                if args.in_place:
                    restore_backup(backup, target, "保存后关闭失败")
                    recovered = True
                raise CliError(_map_com_error(exc, target), 5) from None

            failed = None
            check = s.open(target, read_only=True)
            try:
                vws = get_sheet(check, sheet_name)
                try:
                    vrange = vws.Range(target_addr)
                except Exception as exc:  # noqa: BLE001
                    raise CliError(_map_com_error(exc, target), 5) from None
                actual = read_grid(vrange, rows, cols)
                formulas = read_formulas(vrange, rows, cols)
                if formulas is None:
                    warnings.append("公式未读到，未校验")
                try:
                    verify_grid(data, actual, formulas, bool(getattr(args, "text_only", False)))
                except CliError as exc:
                    failed = exc
            finally:
                # 目标文件必须先在 WPS 里关掉，之后才可能被覆盖，否则 copy2 抛 PermissionError
                try:
                    check.Close(SaveChanges=False)
                except Exception:  # noqa: BLE001 - 关不掉只告警，不能把 6 号错误顶成 1
                    sys.stderr.write("[警告] 校验工作簿未能关闭，请检查残留 et.exe\n")
            if failed is not None:
                if args.in_place and not backup:
                    sys.stderr.write(NO_BACKUP_WARNING)
                if not args.in_place and saved:
                    # 副本保留就必须出声，否则它会被当成成功产物
                    sys.stderr.write(f"[保留] 校验未通过，副本保留在 {target}，请勿直接使用\n")
                restore_backup(backup, target)
                recovered = True
                raise failed
        except BaseException:
            if not recovered:
                if args.in_place:
                    if not saved:
                        # 写盘/其他步骤中断：文件可能已被改了一半，先松开句柄再回滚
                        if wb is not None:
                            try:
                                wb.Close(SaveChanges=False)
                            except Exception:  # noqa: BLE001 - 关不掉也要尝试恢复
                                pass
                        if not backup:
                            sys.stderr.write(NO_BACKUP_WARNING)
                        restore_backup(backup, target, "写入中断")
                    elif backup:
                        # 已保存但后续步骤出错：不擅自回滚，至少把备份位置交代清楚
                        sys.stderr.write(f"[备份] 原文件已保存，备份保留在 {backup}，如需回滚请手工覆盖\n")
                    else:
                        sys.stderr.write(NO_BACKUP_WARNING)
                elif saved:
                    sys.stderr.write(f"[保留] 已保存但后续步骤失败，副本保留在 {target}，请人工确认\n")
            discard_failed_copy(target, target_created, saved)
            raise

    payload = {
        "ok": True,
        "file": target,
        "sheet": sheet_name,
        "range": target_addr,
        "cells": rows * cols,
        "verified": True,
        "inPlace": bool(args.in_place),
        "backup": backup,
    }
    if warnings:
        payload["warnings"] = warnings
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def parse_values(text: str):
    items = []
    for part in [p.strip() for p in text.split(",") if p.strip()]:
        if ":" in part:
            field, agg = part.rsplit(":", 1)
        else:
            field, agg = part, "sum"
        field, agg = field.strip(), agg.strip().lower()
        if agg not in AGG:
            fail(f"不支持的聚合方式：{agg}；可用 sum/count/average/max/min")
        items.append((field, AGG[agg]))
    if not items:
        fail("--values 不能为空，形如 金额:sum,数量:count")
    return items


def cmd_pivot(args) -> int:
    src = check_local(args.file)
    guard_occupied(src, mutating=True)
    target = resolve_out(src, args.out)
    if same_file(target, src):
        fail("输出路径与 --file 相同，换一个 --out", 7)
    guard_out(target, args.force)
    os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
    try:
        shutil.copy2(src, target)
    except OSError:
        discard_failed_copy(target, True, saved=False)
        raise

    src_sheet, r1, c1, r2, c2 = parse_range(args.source) if "!" in args.source else (None,) + parse_range(args.source)[1:]
    value_fields = parse_values(args.values)
    row_fields = [x.strip() for x in args.rows.split(",") if x.strip()]
    if not row_fields:
        fail("--rows 不能为空，形如 地区,月份")
    col_fields = [x.strip() for x in (args.columns or "").split(",") if x.strip()]
    filter_fields = [x.strip() for x in (args.filters or "").split(",") if x.strip()]
    dest_sheet_name = args.dest_sheet or "透视表"
    dest_cell = args.dest_cell or "A3"
    pivot_name = args.name or f"PT{int(time.time() * 1000) % 100000000}"

    with Session() as s:
        wb = s.open(target, read_only=False)
        src_ws = get_sheet(wb, src_sheet)
        try:
            src_range = src_ws.Range(addr(r1, c1, r2, c2))
            src_rows = int(src_range.Rows.Count)
        except Exception as exc:  # noqa: BLE001 - 源区域非法也是 COM 失败，不能落 exit 1
            raise CliError(_map_com_error(exc, target), 5) from None
        if src_rows < 2:
            fail("透视源区域至少需要表头行加一行数据", 2)

        try:
            dest_ws = wb.Worksheets(dest_sheet_name)
        except Exception:  # noqa: BLE001 - 不存在则新建
            dest_ws = None
        try:
            if dest_ws is None:
                dest_ws = wb.Worksheets.Add(After=wb.Worksheets.Item(wb.Worksheets.Count))
                dest_ws.Name = dest_sheet_name
            dest = dest_ws.Range(dest_cell)
        except Exception as exc:  # noqa: BLE001 - 表名/位置非法也是 COM 失败，统一码 5
            raise CliError(_map_com_error(exc, target), 5) from None

        try:
            cache = wb.PivotCaches().Create(XL_DATABASE, src_range)
            table = cache.CreatePivotTable(dest, pivot_name)
            for field in row_fields:
                pf = table.PivotFields(field)
                pf.Orientation = 1
                pf.Position = len(row_fields)
            for field in col_fields:
                pf = table.PivotFields(field)
                pf.Orientation = 2
            for field in filter_fields:
                pf = table.PivotFields(field)
                pf.Orientation = 3
            for field, func in value_fields:
                table.AddDataField(table.PivotFields(field), f"{field}", func)
            try:
                table.RefreshTable()
            except Exception:  # noqa: BLE001 - 个别版本不支持刷新，建表已成功
                pass
        except Exception as exc:  # noqa: BLE001
            text = _short(exc)
            if "无法找到" in text or "不能取得类 PivotField" in text or "0x800a03ec" in text.lower():
                fail(f"透视表字段无效：请确认源区域首行为表头且字段名拼写一致（{text}）", 5)
            fail(_map_com_error(exc, target), 5)

        try:
            table_range = safe_address(table.TableRange1)
            saved_name = str(table.Name)
        except Exception as exc:  # noqa: BLE001
            raise CliError(_map_com_error(exc, target), 5) from None
        try:
            wb.Save()
            wb.Close(SaveChanges=True)
        except Exception as exc:  # noqa: BLE001 - 保存或关闭失败都算 COM 调用失败
            raise CliError(_map_com_error(exc, target), 5) from None

        if not table_range:
            # 文档把 tableRange 非空当验收条件，取不到就不能报 verified
            fail(f"透视表已建但取不到 TableRange1.Address，请人工确认：{target}", 5)

        check_wb = s.open(target, read_only=True)
        try:
            try:
                chk = get_sheet(check_wb, dest_sheet_name)
                found = 0
                for i in range(1, chk.PivotTables().Count + 1):
                    if str(chk.PivotTables().Item(i).Name) == saved_name:
                        found = i
            except CliError:
                raise
            except Exception as exc:  # noqa: BLE001 - 枚举透视表失败也是 COM 失败
                raise CliError(_map_com_error(exc, target), 5) from None
            if found == 0:
                fail("回读校验失败：副本中找不到刚创建的透视表", 6)
        finally:
            try:
                check_wb.Close(SaveChanges=False)
            except Exception:  # noqa: BLE001 - 关不掉只告警，不能把 6 号错误顶成 1
                sys.stderr.write("[警告] 校验工作簿未能关闭，请检查残留 et.exe\n")

    print(
        json.dumps(
            {
                "ok": True,
                "file": target,
                "pivot": saved_name,
                "sheet": dest_sheet_name,
                "tableRange": table_range,
                "verified": True,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def cmd_export_pdf(args) -> int:
    src = check_local(args.file)
    guard_occupied(src, mutating=False)
    out = args.out or (os.path.splitext(src)[0] + ".pdf")
    out = os.path.abspath(os.path.expanduser(out))
    if same_file(out, src):
        # 不加这道闸，--force 会让 WPS 把 PDF 写进源工作簿，源文件当场报废
        fail("输出路径与 --file 相同，换一个 --out", 7)
    if os.path.splitext(out)[1].lower() in SUPPORTED_SUFFIX:
        fail("--out 不能是表格文件：PDF 字节会覆盖工作簿，换 .pdf 后缀", 2)
    guard_out(out, args.force)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)

    with Session() as s:
        wb = s.open(src, read_only=True)
        try:
            if args.sheet:
                ws = get_sheet(wb, args.sheet)
                ws.ExportAsFixedFormat(XL_PDF, out)
                scope = str(ws.Name)
            else:
                wb.ExportAsFixedFormat(XL_PDF, out)
                scope = "whole"
        except CliError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise CliError(_map_com_error(exc, out), 5) from None

    if not os.path.isfile(out):
        fail(f"导出失败：未生成 {out}", 5)
    size = os.path.getsize(out)
    with open(out, "rb") as fh:
        magic = fh.read(5)
    if magic != b"%PDF-" or size == 0:
        fail(f"导出失败：{out} 不是有效 PDF（大小 {size} 字节）", 5)

    print(json.dumps({"ok": True, "file": out, "bytes": size, "scope": scope}, ensure_ascii=False, indent=2))
    return 0


# ---------------------------------------------------------------- 入口


def build_parser():
    p = _Parser(
        prog="wps_com.py",
        description="WPS 表格本地 COM 工具：读、批量写、透视、导出 PDF。只处理本机文件。",
    )
    sub = p.add_subparsers(dest="command", required=True)

    ping = sub.add_parser("ping", help="探测 COM 是否可用")
    ping.set_defaults(func=cmd_ping)

    sheets = sub.add_parser("sheets", help="列出工作表与已用区域")
    sheets.add_argument("--file", required=True, help="本地表格路径")
    sheets.set_defaults(func=cmd_sheets)

    read = sub.add_parser("read", help="按区域读取为 JSON 或 TSV")
    read.add_argument("--file", required=True)
    read.add_argument("--sheet", help="工作表名，缺省为第一张；也可写成 表名!A1:D10")
    read.add_argument("--range", help="区域，如 A1:D10；缺省为已用区域")
    read.add_argument("--format", choices=["json", "tsv"], default="json")
    read.add_argument("--formulas", action="store_true", help="附带公式矩阵")
    read.add_argument("--allow-blank", dest="allow_blank", action="store_true", help="允许区域超出已用范围，越界部分补空")
    read.set_defaults(func=cmd_read)

    write = sub.add_parser("write", help="按区域批量写入（默认 dry-run，确认落点后加 --apply）")
    write.add_argument("--file", required=True)
    write.add_argument("--sheet")
    write.add_argument("--range", help="锚点 A1 或等尺寸区域 A1:D10；缺省追加到已用区域末行+1")
    write.add_argument("--data", help="JSON/TSV 文件路径，或 - 表示标准输入")
    write.add_argument("--json", help="内联二维数组")
    write.add_argument("--out", help="副本输出路径，缺省 <原名>_edited")
    write.add_argument("--force", action="store_true", help="覆盖已存在的输出文件")
    write.add_argument("--apply", action="store_true", help="真正写入；不加则只报落点（dry-run）")
    write.add_argument("--in-place", action="store_true", help="改原文件（需配套确认开关）")
    write.add_argument("--no-backup", action="store_true", help="原地写入时不生成时间戳备份（不建议）")
    write.add_argument(
        "--text-only",
        dest="text_only",
        action="store_true",
        help="把 = 开头的文本也按文本写入（默认按公式写入）",
    )
    write.add_argument(
        "--i-know-this-modifies-original",
        dest="i_know_this_modifies_original",
        action="store_true",
        help="确认承担修改原文件的风险",
    )
    write.set_defaults(func=cmd_write)

    pivot = sub.add_parser("pivot", help="在副本上创建数据透视表")
    pivot.add_argument("--file", required=True)
    pivot.add_argument("--source", required=True, help="源区域，如 Sheet1!A1:D100，首行须为表头")
    pivot.add_argument("--rows", required=True, help="行字段，逗号分隔")
    pivot.add_argument("--values", required=True, help="值字段，形如 金额:sum,数量:count")
    pivot.add_argument("--columns", help="列字段，逗号分隔")
    pivot.add_argument("--filters", help="筛选字段，逗号分隔")
    pivot.add_argument("--dest-sheet", help="目标工作表，缺省 透视表（不存在则新建）")
    pivot.add_argument("--dest-cell", help="放置位置，缺省 A3")
    pivot.add_argument("--name", help="透视表名，缺省自动生成")
    pivot.add_argument("--out", help="副本输出路径，缺省 <原名>_edited")
    pivot.add_argument("--force", action="store_true")
    pivot.set_defaults(func=cmd_pivot)

    pdf = sub.add_parser("export-pdf", help="导出 PDF")
    pdf.add_argument("--file", required=True)
    pdf.add_argument("--out", help="输出 PDF 路径，缺省与源文件同名")
    pdf.add_argument("--sheet", help="只导出指定工作表；缺省导出整个工作簿")
    pdf.add_argument("--force", action="store_true")
    pdf.set_defaults(func=cmd_export_pdf)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except CliError as exc:
        print(f"错误：{_redact(exc.message)}", file=sys.stderr)
        return exc.code
    except KeyboardInterrupt:
        print("错误：已中断，副本可能不完整", file=sys.stderr)
        return 130
    except Exception as exc:  # noqa: BLE001
        if os.environ.get("WPS_COM_DEBUG") == "1":
            raise
        print(f"错误：{type(exc).__name__}: {_redact(_short(exc))}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
