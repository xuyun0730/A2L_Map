from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from . import __version__
from .core import build_index, export_rows, parse_a2l, query_address, query_name


def _resolve_inputs(a2l: str | None, map_file: str | None) -> tuple[Path, Path]:
    if map_file:
        map_path = Path(map_file)
    else:
        candidates = sorted(Path.cwd().glob("*.map"))
        if len(candidates) != 1:
            raise ValueError(f"请用 --map 指定 MAP 文件（当前目录找到 {len(candidates)} 个）")
        map_path = candidates[0]
    if a2l:
        a2l_path = Path(a2l)
    else:
        candidates: list[tuple[int, Path]] = []
        for path in Path.cwd().rglob("*.a2l"):
            objects, _ = parse_a2l(path)
            if objects:
                candidates.append((len(objects), path))
        if not candidates:
            raise ValueError("没有找到包含有效 A2L 对象的文件；请用 --a2l 指定")
        max_count = max(count for count, _ in candidates)
        best = [path for count, path in candidates if count == max_count]
        if len(best) != 1:
            names = ", ".join(str(x) for x in best)
            raise ValueError(f"存在 {len(best)} 个同规模 A2L 候选，请显式指定 --a2l：{names}")
        a2l_path = best[0]
    for path in (a2l_path, map_path):
        if not path.is_file():
            raise ValueError(f"输入文件不存在：{path}")
    return a2l_path, map_path


def _address(value: str) -> int:
    normalized = value.strip().lower()
    return int(normalized, 16 if normalized.startswith("0x") or re.search(r"[a-f]", normalized) else 10)


def _print_json(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="map-a2l", description="离线 MAP/A2L 符号与地址查询")
    parser.add_argument("--version", action="version", version=f"map-a2l {__version__}")
    parser.add_argument("--a2l", help="ASAP2/A2L 输入文件；省略时扫描并选取对象数最多的候选")
    parser.add_argument("--map", dest="map_file", help="链接 MAP 输入文件；目录中只有一个 .map 时可省略")
    sub = parser.add_subparsers(dest="command", required=True)
    def add_inputs(command_parser: argparse.ArgumentParser) -> None:
        command_parser.add_argument("--a2l", default=argparse.SUPPRESS,
                                    help="ASAP2/A2L 输入文件")
        command_parser.add_argument("--map", dest="map_file", default=argparse.SUPPRESS,
                                    help="链接 MAP 输入文件")

    summary = sub.add_parser("summary", help="显示索引与匹配统计")
    add_inputs(summary)
    q = sub.add_parser("query", help="按变量名精确查询")
    add_inputs(q)
    q.add_argument("name")
    q.add_argument("--fuzzy", action="store_true", help="启用模糊匹配并按相似度排序")
    q.add_argument("--limit", type=int, default=50, help="模糊匹配最多返回的结果数")
    addr = sub.add_parser("address", help="按十六进制地址反查 A2L/MAP")
    add_inputs(addr)
    addr.add_argument("value")
    batch = sub.add_parser("batch", help="按名称清单批量查询并导出")
    add_inputs(batch)
    batch.add_argument("names", help="变量名文本文件，每行一个名字")
    batch.add_argument("-o", "--output", required=True)
    batch.add_argument("--format", choices=("json", "csv"), help="省略时根据扩展名推断")
    report = sub.add_parser("report", help="导出完整索引结果")
    add_inputs(report)
    report.add_argument("-o", "--output", required=True)
    report.add_argument("--format", choices=("json", "csv"), help="省略时根据扩展名推断")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = make_parser()
    args = parser.parse_args(argv)
    try:
        a2l_path, map_path = _resolve_inputs(args.a2l, args.map_file)
        index = build_index(a2l_path, map_path)
        if args.command == "summary":
            _print_json({"version_status": index["version_status"], "a2l": index["a2l"],
                         "map": index["map"], "fingerprints": index["fingerprints"], "summary": index["summary"]})
        elif args.command == "query":
            rows = query_name(index, args.name, fuzzy=args.fuzzy, limit=args.limit)
            if not rows:
                print(f"未找到 A2L 变量：{args.name}")
                return 1
            _print_json(rows)
        elif args.command == "address":
            rows = query_address(index, _address(args.value))
            if not rows:
                print(f"地址 {args.value} 未找到匹配")
                return 1
            _print_json(rows)
        else:
            output = Path(args.output)
            fmt = args.format or ("json" if output.suffix.lower() == ".json" else "csv")
            names = None
            if args.command == "batch":
                names = [line.strip() for line in Path(args.names).read_text(encoding="utf-8-sig").splitlines()
                         if line.strip() and not line.lstrip().startswith("#")]
            count = export_rows(index, output, fmt, names)
            print(f"已导出 {count} 个 A2L 对象到 {output.resolve()}；包含未命中和歧义项。")
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
