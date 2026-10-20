"""python -m plc_st run file.st --cycles N --set x=1 --at 3:y=0 --trace out.csv
python -m plc_st tags points.csv   # 輸出 VAR 宣告"""
import argparse
import csv
import sys

from .interpreter import VirtualPLC, STError
from .tags import tags_to_var_blocks


def parse_value(s):
    low = s.lower()
    if low in ("true", "false"):
        return low == "true"
    try:
        return int(s)
    except ValueError:
        return float(s)


def parse_assign(s, with_cycle=False):
    cycle = 0
    if with_cycle:
        c, _, s = s.partition(":")
        cycle = int(c)
    name, eq, val = s.partition("=")
    if not eq:
        raise STError(f"bad assignment {s!r}, expected name=value")
    return cycle, name.strip(), parse_value(val.strip())


def run(args):
    with open(args.file, encoding="utf-8") as f:
        plc = VirtualPLC(f.read(), scan_ms=args.scan_ms)
    events = [parse_assign(a) for a in args.set] + [parse_assign(a, True) for a in args.at]
    cols = list(plc.snapshot())
    rows = []
    for cyc in range(args.cycles):
        for c, n, v in events:
            if c == cyc:
                plc.set_input(n, v)
        plc.scan(1)
        rows.append([plc.cycles, plc.time_ms] + [plc.snapshot()[k] for k in cols])
    out = open(args.trace, "w", newline="", encoding="utf-8") if args.trace else sys.stdout
    w = csv.writer(out)
    w.writerow(["cycle", "time_ms"] + cols)
    w.writerows(rows)
    if args.trace:
        out.close()
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="plc_st")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="在虛擬 PLC 執行 ST 並輸出每週期 trace(CSV)")
    r.add_argument("file")
    r.add_argument("--cycles", type=int, default=10)
    r.add_argument("--scan-ms", type=int, default=10)
    r.add_argument("--set", action="append", default=[], metavar="NAME=VALUE", help="第 0 週期前設定")
    r.add_argument("--at", action="append", default=[], metavar="CYCLE:NAME=VALUE", help="指定週期前設定")
    r.add_argument("--trace", help="寫入 CSV 檔(預設 stdout)")
    t = sub.add_parser("tags", help="CSV 點位表 → VAR 宣告")
    t.add_argument("file")
    a = p.parse_args(argv)
    try:
        if a.cmd == "run":
            return run(a)
        with open(a.file, encoding="utf-8") as f:
            sys.stdout.write(tags_to_var_blocks(f.read()))
        return 0
    except (STError, ValueError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
