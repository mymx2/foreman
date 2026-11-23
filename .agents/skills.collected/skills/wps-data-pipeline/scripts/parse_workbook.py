#!/usr/bin/env python3
"""parse_workbook.py — 云表格只读解析：结构探查、条件导出、行哈希快照。

由执行者运行（execute），不是供阅读的参考材料。
只依赖 python-calamine；缺依赖时给安装提示并以退出码 2 结束，不抛堆栈。

用法:
  python parse_workbook.py BOOK.xlsx --list [--json]
  python parse_workbook.py BOOK.xlsx --sheet <表名> --where "列=值" --out out.csv
  python parse_workbook.py BOOK.xlsx --sheet <表名> --where "出库时间=空" --out 空.csv
  python parse_workbook.py BOOK.xlsx --fingerprint --out snap.json

筛选语法（--where 可重复，多个条件为「与」）:
  列=值     归一化后相等；值为 空 / (空) 时匹配空单元格
  列!=值    归一化后不等
  列~子串   归一化文本包含子串
  列^前缀   归一化文本以该前缀开头
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
import traceback
import unicodedata
from collections import Counter
from datetime import date, datetime

DEP_HINT = (
    "[错误] 缺少依赖 python-calamine，本脚本只用它读表。\n"
    "       安装：python -m pip install python-calamine\n"
    "       已装仍报错，多半是装到了别的解释器：\n"
    "       python -c \"import sys; print(sys.executable)\"\n"
    "       不要改用 openpyxl——混合日期列会让它整本失败。\n"
)

try:
    from python_calamine import CalamineWorkbook
except ImportError:
    # 守卫挪到 main()：缺依赖时 --help 仍要能看参数，提示与退出码不变
    CalamineWorkbook = None
    _DEP_MISSING = True
else:
    _DEP_MISSING = False

EMPTY_TOKENS = {"空", "(空)", "（空）", "EMPTY", "empty", "NULL", "null", "None"}
TEXT_DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%Y.%m.%d",
    "%Y年%m月%d日",
    "%Y-%m-%d %H:%M:%S",
    "%Y/%m/%d %H:%M:%S",
)


class UsageError(Exception):
    """可预期的使用错误：只打印一行中文说明，不打印堆栈。"""


# --------------------------------------------------------------------------- 归一化


def _yyyymmdd(n: int):
    """19211216 / 20211216 这类 8 位整数 → ISO 日期；不合法返回 None。"""
    if not 19000101 <= n <= 29991231:
        return None
    try:
        return date(n // 10000, (n // 100) % 100, n % 100).isoformat()
    except ValueError:
        return None


def _date_from_text(s: str):
    if len(s) == 8 and s.isdigit():
        return _yyyymmdd(int(s))
    for fmt in TEXT_DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def normalize(value, coerce_dates: bool = True):
    """任意单元格值 → (kind, text)，kind ∈ {date, number, text, empty}。

    四类输入分别落到:
      date/datetime   → ("date", "YYYY-MM-DD")
      8 位整数/浮点     → ("date", "YYYY-MM-DD")（不像日期的仍归 number）
      文本            → ("text", 原文去首尾空白) 或可解析时归 date
      空值/空串       → ("empty", "")
    """
    if value is None:
        return "empty", ""
    if isinstance(value, float) and value != value:  # NaN
        return "empty", ""
    if isinstance(value, bool):
        return "text", "TRUE" if value else "FALSE"
    if isinstance(value, (datetime, date)):
        return "date", value.strftime("%Y-%m-%d")
    if isinstance(value, (int, float)):
        if float(value).is_integer():
            n = int(value)
            if coerce_dates:
                iso = _yyyymmdd(n)
                if iso:
                    return "date", iso
            return "number", str(n)
        return "number", repr(float(value))
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return "empty", ""
        if coerce_dates:
            iso = _date_from_text(s)
            if iso:
                return "date", iso
        return "text", s
    return "text", str(value).strip()


def _blank(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    return False


# --------------------------------------------------------------------------- 读表


def open_workbook(path: str):
    try:
        return CalamineWorkbook.from_path(path)
    except Exception as exc:  # 损坏、密码保护、扩展名不符
        raise UsageError(
            f"打不开 {_redact_path(os.path.basename(path))}：{_redact_path(str(exc))}"
            "（确认是 xlsx/xls 且未被密码保护）"
        ) from exc


def load_rows(wb, name: str):
    """返回 (rows, ncols)：去掉尾部空行、按最右非空列裁齐，行号从表头行所在 0 开始。"""
    try:
        sheet = wb.get_sheet_by_name(name)
    except Exception as exc:
        raise UsageError(
            f"没有工作表 {_redact(name)!r}。可用：{', '.join(wb.sheet_names)}"
        ) from exc
    rows = [list(r) for r in sheet.to_python(skip_empty_area=False)]
    while rows and all(_blank(v) for v in rows[-1]):
        rows.pop()
    ncols = 0
    for r in rows:
        for i in range(len(r) - 1, -1, -1):
            if not _blank(r[i]):
                ncols = max(ncols, i + 1)
                break
    return [r[:ncols] for r in rows], ncols


def header_of(rows, header_row: int):
    if header_row < 0 or header_row >= len(rows):
        raise UsageError(f"表头行 {header_row} 超出范围（该表共 {len(rows)} 行）")
    names = []
    for j, v in enumerate(rows[header_row]):
        raw = "" if v is None else str(v).strip()
        names.append(raw or f"列{j + 1}")
    dup = [n for n, c in Counter(names).items() if c > 1]
    if dup:
        sys.stderr.write(f"[提示] 表头重名，按第一个同名列筛选：{', '.join(dup)}\n")
    return names


# --------------------------------------------------------------------------- 筛选


WHERE_OPS = ("!=", "~", "^", "=")


def _where_splits(expr: str):
    """所有可能的切分点，按位置升序；同一位置 != 优先于 =（元组顺序即优先级）。"""
    out = []
    for i in range(len(expr)):
        for op in WHERE_OPS:
            if expr.startswith(op, i):
                out.append((i, op))
                break
    return out


def parse_where(expr: str, headers):
    """把 列名<运算符>值 切成三元组，列名必须在 headers 里。

    取最左出现的运算符；该切分点得到的列名不在表头时，继续试右侧切分点，
    这样列名本身含 = ~ ^ 也能解析，且 "列=A~B" 不会被 "~" 抢走切分权。
    """
    splits = [(i, op) for i, op in _where_splits(expr) if expr[:i].strip()]
    for i, op in splits:
        name = expr[:i].strip()
        if name in headers:
            want = expr[i + len(op):].strip()
            if not want and op in ("~", "^"):
                raise UsageError(
                    f"筛选条件 {_redact(expr)!r} 的 {op} 后不能为空；要匹配空值请写 列=空"
                )
            return name, op, want
    if splits:
        name = expr[:splits[0][0]].strip()
        raise UsageError(
            f"找不到列 {_redact(name)!r}。该表前 20 列：{', '.join(list(headers)[:20])}"
        )
    raise UsageError(
        f"筛选条件 {_redact(expr)!r} 格式不对，应为 列名=值 / 列名!=值 / 列名~子串 / 列名^前缀"
    )


_DATE_FRAGMENT = re.compile(r"^\d{4}[-/.]\d{1,2}(?:[-/.]\d{1,2})?$")


def _fold_date_fragment(s: str) -> str:
    """2026/1、2026.1.2 这类日期片段折成与单元格一致的 2026-01、2026-01-02。

    不补零 1 到 9 月会静默 0 命中：单元格归一化后是 2026-01，
    needle 却是 2026-1，子串匹配永远对不上。
    """
    if not _DATE_FRAGMENT.match(s):
        return s
    parts = re.split(r"[-/.]", s)
    return "-".join([f"{int(parts[0]):04d}"] + [f"{int(p):02d}" for p in parts[1:]])


def make_matcher(col: int, op: str, want: str, coerce_dates: bool):
    want_empty = want == "" or want in EMPTY_TOKENS
    _, wnorm = normalize(want, coerce_dates) if not want_empty else ("empty", "")
    # ~ / ^ 是子串匹配，空值令牌没意义（「库位号~空」是找含「空」字的单元格），
    # 所以这里不用 want_empty 分支：want 正经归一化，日期片段再折一次分隔符。
    needle = _fold_date_fragment(normalize(want, coerce_dates)[1])
    raw = want.strip()

    def test(row) -> bool:
        kind, text = normalize(row[col] if col < len(row) else None, coerce_dates)
        if op == "=":
            return kind == "empty" if want_empty else text == wnorm
        if op == "!=":
            return kind != "empty" if want_empty else text != wnorm
        if kind != "date":
            # 文本格不折：1000.5、20260115 按原样比，别被日期形态的 needle 吃掉
            return raw in text if op == "~" else text.startswith(raw)
        return needle in text if op == "~" else text.startswith(needle)

    return test


def _cell_out(value, coerce_dates: bool, raw: bool) -> str:
    if raw:
        return "" if value is None else str(value)
    return normalize(value, coerce_dates)[1]


def _cell_typed(value, coerce_dates: bool, raw: bool):
    """JSON 专用：保留数值类型，避免下游把 100 当字符串 "100" 而算成 0。"""
    if raw:
        # datetime 是 date 的子类，先判 datetime，否则时间会被 strftime 砍成纯日期
        if isinstance(value, datetime):
            return value.isoformat(sep=" ")
        if isinstance(value, date):
            return value.isoformat()
        return value
    kind, text = normalize(value, coerce_dates)
    if kind == "empty":
        return None
    if kind == "number":
        try:
            return int(text)
        except ValueError:
            pass
        # repr(1e-05) 不含小数点，只能按 float 解析；is_integer 再退成 int
        try:
            numeric = float(text)
        except ValueError:
            return text
        return int(numeric) if numeric.is_integer() else numeric
    return text


# --------------------------------------------------------------------------- 参数守卫与脱敏


_SCHEME_RE = re.compile(r"^([A-Za-z][A-Za-z0-9+.\-]*):/*(.*)$")


def _is_download_url(s: str) -> bool:
    """不只看位置 0：前导空格、带引号、单斜杠、无协议但带 ?Signature= 都要认出来。

    signature= 只在带 ? 时才算：预签名地址必然有查询串，而任何绝对路径都带 /，
    用 / 做条件会把 C:/x/signature=1.xlsx 这种合法文件一起误杀。
    """
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
    """名称类回显脱敏：URL 形态截到第一个 ? 之前；汇总?2026 这种名字原样保留。

    除 _is_download_url 外，「/ 与 ? 同时出现」也算 URL 形态——?token= 这类
    不带 signature 的查询串走的就是这条路，否则表名/列名回显会漏。
    """
    t = value.strip().strip("'\"<>")
    if not (_is_download_url(value) or ("?" in t and ("/" in t or "=" in t))):
        return value
    head, sep, _ = t.partition("?")
    if sep:
        return head
    host = _url_host(t)
    return f"{host}/…" if host else "[下载地址]"


def _redact_path(value: str) -> str:
    """路径类回显无条件截到第一个 ? 之前。

    Windows 路径不允许 ?，截断不会误伤；POSIX 下真带 ? 的文件名只影响报错可读性，
    不影响任何数据。表名/列名走 _redact，那边保留 ?。
    """
    return value.split("?", 1)[0]


def _same_file_path(a: str, b: str) -> bool:
    """realpath 消掉 ./.. 与符号链接，normcase 兜住 Windows 大小写。"""
    if os.path.normcase(os.path.realpath(a)) == os.path.normcase(os.path.realpath(b)):
        return True
    try:
        return os.path.samefile(a, b)  # 硬链接：路径不同、inode 相同
    except OSError:
        return False


_SPREADSHEET_EXTS = {".xlsx", ".xlsm", ".xls", ".et", ".ett"}


def guard_out_path(args) -> None:
    """--out 既不能是下载地址（会漏签名），也不能落到输入工作簿上（会就地截断源表）。"""
    if not args.out:
        return
    if _is_download_url(args.out):
        host = _url_host(args.out)
        raise UsageError(
            "--out 是输出路径，不能是下载地址；先 curl 落盘再解析"
            + (f"（地址域名：{host}）" if host else "")
        )
    if _same_file_path(args.out, args.book):
        raise UsageError("--out 不能指向输入文件：会就地截断源表，换个输出路径")
    if os.path.splitext(args.out)[1].lower() in _SPREADSHEET_EXTS:
        # 导出的是 CSV 内的 JSON 文本，写进表格后缀等于把工作簿当文本覆盖
        raise UsageError("--out 不能是表格文件，导出的不是工作簿")


class _AtomicOut:
    """写 <path>.tmp，序列化全部成功后才 os.replace 到目标；异常删掉 tmp。

    直接以 "w" 打开目标路径会立刻截断已有文件：--raw 遇 time/timedelta 时
    json.dump 抛 TypeError，失败产物正好落在承诺路径上，exit 1 是唯一信号。
    临时文件与目标同目录，保证同卷，os.replace 才是原子换名。
    """

    def __init__(self, path: str, bom: bool = True):
        self.path = path
        self.tmp = path + ".tmp"
        d = os.path.dirname(os.path.abspath(path))
        os.makedirs(d, exist_ok=True)
        if os.path.exists(path):
            sys.stderr.write(f"[提示] 覆盖已存在文件：{path}\n")
        self._fh = open(self.tmp, "w", encoding="utf-8-sig" if bom else "utf-8", newline="")

    def __getattr__(self, name):
        return getattr(self._fh, name)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            self._fh.close()
        except BaseException:
            self._discard()
            raise
        if exc_type is not None:
            self._discard()
            return False
        try:
            os.replace(self.tmp, self.path)
        except BaseException:
            self._discard()
            raise
        return False

    def _discard(self):
        try:
            os.unlink(self.tmp)
        except OSError:
            pass


def _open_out(path, bom: bool = True) -> _AtomicOut:
    return _AtomicOut(path, bom)


# --------------------------------------------------------------------------- 命令


def _width(s: str) -> int:
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in s)


def _pad(s: str, w: int, right: bool = False) -> str:
    fill = " " * max(0, w - _width(s))
    return fill + s if right else s + fill


def cmd_list(wb, args) -> int:
    info = []
    for name in wb.sheet_names:
        rows, ncols = load_rows(wb, name)
        info.append({"sheet": name, "rows": len(rows), "cols": ncols})
    if args.json:
        print(json.dumps(info, ensure_ascii=False, indent=2))
        return 0
    w = max([_width("工作表")] + [_width(i["sheet"]) for i in info])
    print(f"{_pad('工作表', w)}  {_pad('行数', 8, True)}  {_pad('列数', 5, True)}")
    for i in info:
        print(f"{_pad(i['sheet'], w)}  {_pad(str(i['rows']), 8, True)}  {_pad(str(i['cols']), 5, True)}")
    print(f"{_pad('合计', w)}  {_pad(str(sum(i['rows'] for i in info)), 8, True)}"
          f"  {_pad(str(len(info)) + ' 张表', 5, True)}")
    sys.stderr.write("[说明] 行数含表头行；列数按最右非空列计算。\n")
    return 0


def cmd_query(wb, args) -> int:
    rows, _ = load_rows(wb, args.sheet)
    if not rows:
        raise UsageError(f"工作表 {args.sheet!r} 为空")
    hdr = header_of(rows, args.header_row)
    checks = []
    for expr in args.where:
        col_name, op, want = parse_where(expr, hdr)
        checks.append(make_matcher(hdr.index(col_name), op, want, args.coerce_dates))

    body = rows[args.header_row + 1:]
    hits = []
    for r in body:
        if all(c(r) for c in checks):
            hits.append(r)
            if args.limit and len(hits) >= args.limit:
                break

    def emit(fh):
        if args.format == "json":
            # 只输出数据行（不含表头），保留数值类型，可直接作为 wps_com.py write --data 的输入
            payload = [
                [_cell_typed(r[j] if j < len(r) else None, args.coerce_dates, args.raw)
                 for j in range(len(hdr))]
                for r in hits
            ]
            json.dump(payload, fh, ensure_ascii=False)
            fh.write("\n")
        else:
            writer = csv.writer(fh)
            writer.writerow(hdr)
            for r in hits:
                writer.writerow([_cell_out(r[j] if j < len(r) else None, args.coerce_dates, args.raw)
                                 for j in range(len(hdr))])

    if args.out:
        # 先写 .tmp 再换名：写入期异常不会毁掉上一份好文件
        with _open_out(args.out, bom=(args.format != "json")) as fh:
            emit(fh)
    else:
        emit(sys.stdout)

    sys.stderr.write(
        f"[完成] {args.sheet}：命中 {len(hits)} / 共 {len(body)} 行"
        f"（表头行 {args.header_row}，{len(hdr)} 列）"
        f"{'，已按 --limit 截断' if args.limit and len(hits) >= args.limit else ''}\n"
    )
    if args.out:
        sys.stderr.write(f"[输出] {os.path.abspath(args.out)}\n")
    return 0


def cmd_fingerprint(wb, args) -> int:
    names = list(wb.sheet_names)
    if args.only:
        want = [s.strip() for s in args.only.split(",") if s.strip()]
        missing = [s for s in want if s not in names]
        if missing:
            raise UsageError(
                f"--only 里有不存在的表：{', '.join(_redact(m) for m in missing)}"
            )
        names = want

    payload = {
        "workbook": os.path.basename(args.book),
        "hash_len": args.hash_len,
        "coerce_dates": args.coerce_dates,
        "sheets": [],
    }
    for name in names:
        rows, ncols = load_rows(wb, name)
        digs = []
        for r in rows:
            parts = []
            for j in range(ncols):
                kind, text = normalize(r[j] if j < len(r) else None, args.coerce_dates)
                parts.append(kind + ":" + text)
            digs.append(hashlib.sha256("\x1f".join(parts).encode("utf-8"))
                        .hexdigest()[:args.hash_len])
        payload["sheets"].append({
            "name": name,
            "rows": len(rows),
            "cols": ncols,
            "digest": hashlib.sha256("\n".join(digs).encode("utf-8")).hexdigest()[:32],
            "row_hashes": digs,
        })
        sys.stderr.write(f"[指纹] {name}: {len(rows)} 行 × {ncols} 列\n")

    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    if args.out:
        with _open_out(args.out, bom=False) as fh:
            fh.write(text + "\n")
        sys.stderr.write(f"[输出] {os.path.abspath(args.out)}\n")
    else:
        print(text)
    return 0


# --------------------------------------------------------------------------- 入口


EXAMPLES = """\
示例:
  python parse_workbook.py 导出.xlsx --list
  python parse_workbook.py 导出.xlsx --sheet <表名> --where "库位号~杂" --out 杂.csv
  python parse_workbook.py 导出.xlsx --sheet <表名> --where "出库时间=空" --where "库位号~杂" --out q.csv
  python parse_workbook.py 导出.xlsx --fingerprint --out snap-2026-11-23.json
"""


def _int_arg(text: str) -> int:
    """自定义整数解析：报错不回显原值，免得把 URL 之类的入参打进 stderr。"""
    try:
        return int(text)
    except (TypeError, ValueError):
        raise argparse.ArgumentTypeError("应为整数")


class _Parser(argparse.ArgumentParser):
    """argparse 的 error() 原样回显入参，这里过一遍脱敏，退出码仍是 2。"""

    def error(self, message):
        self.print_usage(sys.stderr)
        sys.stderr.write(f"{self.prog}: error: {_redact(message)}\n")
        raise SystemExit(2)


def build_parser() -> argparse.ArgumentParser:
    p = _Parser(
        prog="parse_workbook.py",
        description="云表格只读解析：结构探查、条件导出、行哈希快照",
        epilog=EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("book", nargs="?", help="xlsx / xls 路径")
    p.add_argument("--list", action="store_true", help="列出所有工作表与行列数")
    p.add_argument("--json", action="store_true", help="--list 以 JSON 输出")
    p.add_argument("--sheet", help="目标工作表名（查询/导出用）")
    p.add_argument("--where", action="append", default=[],
                   help="筛选条件，可重复；列=值 / 列!=值 / 列~子串 / 列^前缀")
    p.add_argument("--out", help="输出路径（CSV / JSON / 指纹）；缺省写 stdout")
    p.add_argument("--format", choices=("csv", "json"), default="csv",
                   help="查询输出格式：csv 含表头；json 为二维数组（不含表头），可直接作 wps_com.py write --data 的输入")
    p.add_argument("--fingerprint", action="store_true", help="输出每行哈希，供快照对比")
    p.add_argument("--only", help="--fingerprint 限定工作表，逗号分隔")
    p.add_argument("--header-row", type=_int_arg, default=0, help="表头所在行，0 起，默认 0")
    p.add_argument("--limit", type=_int_arg, help="最多导出多少行")
    p.add_argument("--raw", action="store_true", help="导出原始值，不做日期归一化")
    p.add_argument("--hash-len", type=_int_arg, default=16, help="行哈希长度，默认 16")
    p.add_argument("--debug", action="store_true", help="保留完整堆栈")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    # 依赖守卫：--help 在 parse_args 内就以 0 退出了，走不到这里
    if _DEP_MISSING:
        sys.stderr.write(DEP_HINT)
        raise SystemExit(2)
    args.coerce_dates = True

    if not args.book:
        raise UsageError("缺少工作簿路径")
    if _is_download_url(args.book):
        host = _url_host(args.book)
        raise UsageError(
            "这是下载地址，不是本地路径；先 curl 落盘再解析"
            + (f"（地址域名：{host}）" if host else "")
        )
    if not os.path.isfile(args.book):
        raise UsageError(f"文件不存在：{_redact_path(args.book)}")
    guard_out_path(args)

    wb = open_workbook(args.book)
    if args.list:
        return cmd_list(wb, args)
    if args.fingerprint:
        return cmd_fingerprint(wb, args)
    if args.sheet:
        return cmd_query(wb, args)
    raise UsageError("三选一：--list / --sheet <表名> / --fingerprint")


if __name__ == "__main__":
    try:
        for _stream in (sys.stdout, sys.stderr):
            if hasattr(_stream, "reconfigure"):
                try:
                    _stream.reconfigure(errors="replace")
                except Exception:
                    pass
        raise SystemExit(main())
    except UsageError as exc:
        sys.stderr.write(f"[错误] {exc}\n")
        raise SystemExit(2)
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as exc:
        sys.stderr.write(f"[错误] {type(exc).__name__}: {_redact_path(str(exc))}\n")
        if "--debug" in sys.argv:
            # 逐行脱敏：整段截到第一个 ? 会把后半条 traceback 砍掉，没法调试。
            # 裸 raise 会让默认 excepthook 打出原始异常消息，签名就漏了。
            lines = traceback.format_exc().splitlines()
            sys.stderr.write("\n".join(_redact_path(line) for line in lines) + "\n")
            raise SystemExit(1)
        sys.stderr.write("       加 --debug 查看完整堆栈\n")
        raise SystemExit(1)
