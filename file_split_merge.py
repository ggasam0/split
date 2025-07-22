#!/usr/bin/env python3
"""
file_split_merge.py
-------------------
切分与合并任意文件的小工具。

用法：
    python file_split_merge.py split <input_file> <chunk_size_mb> [output_dir]
    python file_split_merge.py merge <chunk_prefix> [output_file]

示例：
    python file_split_merge.py split movie.mkv 100 ./parts
    python file_split_merge.py merge ./parts/movie.mkv
"""
import argparse
import hashlib
import math
import os
import sys
from pathlib import Path
from typing import List

CHUNK_SUFFIX_LEN = 3  # 支持最多 999 个分块

def sha256sum(path: Path, buf_size: int = 1 << 20) -> str:
    """计算文件 SHA‑256（用于校验合并结果）"""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(buf_size), b""):
            h.update(chunk)
    return h.hexdigest()

def split_file(input_path: Path, chunk_size_mb: int, output_dir: Path) -> List[Path]:
    """按指定大小（MiB）切分文件，返回生成的分块路径列表"""
    if not input_path.is_file():
        raise FileNotFoundError(input_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    chunk_size = chunk_size_mb * (1 << 20)  # 转换为字节
    total_size = input_path.stat().st_size
    total_parts = math.ceil(total_size / chunk_size)

    chunk_paths = []
    with input_path.open("rb") as src:
        for idx in range(total_parts):
            part_name = f"{input_path.name}.{idx:0{CHUNK_SUFFIX_LEN}d}"
            part_path = output_dir / part_name
            with part_path.open("wb") as dst:
                dst.write(src.read(chunk_size))
            chunk_paths.append(part_path)
            print(f"生成 {part_path} ({part_path.stat().st_size} bytes)")
    # 保存原文件哈希以供校验
    (output_dir / f"{input_path.name}.sha256").write_text(sha256sum(input_path))
    return chunk_paths

def merge_files(chunk_prefix: Path, output_path: Path = None) -> Path:
    if not chunk_prefix.parent.is_dir():
        raise FileNotFoundError(chunk_prefix.parent)

    # 正确的 glob 模式，如 "file.[0-9][0-9][0-9]"
    digit_pattern = ''.join('[0-9]' for _ in range(CHUNK_SUFFIX_LEN))
    chunks = sorted(chunk_prefix.parent.glob(f"{chunk_prefix.name}.{digit_pattern}"))
    if not chunks:
        raise FileNotFoundError("未找到任何分块")

    output_path = output_path or chunk_prefix.parent / chunk_prefix.name

    with output_path.open("wb") as dst:
        for part in chunks:
            with part.open("rb") as src:
                dst.write(src.read())
            print(f"合并 {part} -> {output_path}")

    # 校验……
    sha_file = chunk_prefix.parent / f"{chunk_prefix.name}.sha256"
    if sha_file.exists():
        orig_hash = sha_file.read_text().strip()
        merged_hash = sha256sum(output_path)
        if merged_hash == orig_hash:
            print("✅ 合并成功，哈希校验通过")
        else:
            print("⚠️ 合并完成，但哈希不匹配！")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Split or merge arbitrary files.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # split
    sp = sub.add_parser("split", help="Split a file into chunks")
    sp.add_argument("input_file", type=Path)
    sp.add_argument("chunk_size_mb", type=int, help="chunk size in MiB")
    sp.add_argument("output_dir", nargs="?", default=".", type=Path, help="directory to save chunks")

    # merge
    mp = sub.add_parser("merge", help="Merge chunks back into a file")
    mp.add_argument("chunk_prefix", type=Path, help="prefix of chunks, e.g., ./parts/big.iso")
    mp.add_argument("output_file", nargs="?", type=Path, help="merged output path")

    args = parser.parse_args()

    try:
        if args.cmd == "split":
            split_file(args.input_file, args.chunk_size_mb, args.output_dir)
        elif args.cmd == "merge":
            merge_files(args.chunk_prefix, args.output_file)
    except Exception as e:
        print(f"错误：{e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
