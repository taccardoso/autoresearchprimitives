#!/usr/bin/env python3
"""Find duplicate and near-duplicate skills under one or more skill roots.

Standalone: no harness imports, no third-party dependencies.

A skill root is a directory whose *direct children* that contain a SKILL.md are
active skills (nested examples, reference documents and vendor payloads are not
independently loadable skills and are ignored).

Duplicate kinds reported:
  * ``conteudo_identico``              - identical content sha256 in different roots
  * ``mesmo_nome_conteudo_diferente``  - same skill name, different content

Similarity is the Jaccard index over normalized 5-word shingles, computed on
the same window the registry fingerprint uses (first 256 KiB + last 64 KiB).

Usage:
    python dedup.py --registry registry.json --root ~/.agents/skills \
        --root ~/.codex/skills [--csv duplicates.csv] [--json out.json] [--top 50]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

WINDOW = 256 * 1024
TAIL = 64 * 1024
WORD_RE = re.compile(r"[a-z0-9_]+")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def read_window(path: Path) -> str:
    size = path.stat().st_size
    with path.open("rb") as fh:
        head = fh.read(WINDOW)
        tail = b""
        if size > WINDOW:
            fh.seek(max(0, size - TAIL))
            tail = fh.read(TAIL)
    return (head + b"\n<<TAIL>>\n" + tail).decode("utf-8", errors="replace")


def shingles(text: str, n: int = 5) -> set[bytes]:
    words = WORD_RE.findall(text.lower())
    if len(words) < n:
        return set()
    return {
        hashlib.blake2b(" ".join(words[i:i + n]).encode("utf-8"), digest_size=8).digest()
        for i in range(len(words) - n + 1)
    }


def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / float(len(a) + len(b) - len(a & b))


def skill_name(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return path.parent.name
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        for line in lines[1:200]:
            if line.strip() in {"---", "..."}:
                break
            match = re.match(r"^name\s*:\s*(.*?)\s*$", line, re.I)
            if match:
                return match.group(1).strip().strip("\"'")
    return path.parent.name


def main() -> int:
    ap = argparse.ArgumentParser(description="Duplicate census over skill roots.")
    ap.add_argument("--registry", required=True)
    ap.add_argument("--root", action="append", required=True)
    ap.add_argument("--csv")
    ap.add_argument("--json")
    ap.add_argument("--top", type=int, default=50)
    args = ap.parse_args()

    rows = []
    for raw_root in args.root:
        root = Path(raw_root).expanduser()
        if not root.is_dir():
            continue
        for child in sorted(root.iterdir(), key=lambda p: p.name.lower()):
            skill = child / "SKILL.md"
            if not skill.is_file():
                continue
            rows.append({
                "path": str(skill),
                "root": str(root),
                "dir_name": child.name,
                "name": skill_name(skill),
                "size": skill.stat().st_size,
                "sha256": sha256_file(skill),
            })

    by_name = defaultdict(list)
    by_sha = defaultdict(list)
    for row in rows:
        by_name[row["name"]].append(row)
        by_sha[row["sha256"]].append(row)

    pairs = []
    for members in by_sha.values():
        if len(members) < 2:
            continue
        members = sorted(members, key=lambda m: (-m["size"], m["path"]))
        for i in range(len(members) - 1):
            a, b = members[i], members[i + 1]
            pairs.append({"tipo": "conteudo_identico", "nome": a["name"], "size": a["size"],
                          "a": a, "b": b, "similaridade": 1.0})
    for name, members in by_name.items():
        if len({m["sha256"] for m in members}) < 2:
            continue
        members = sorted(members, key=lambda m: (-m["size"], m["path"]))
        a = members[0]
        for b in members[1:]:
            if b["sha256"] == a["sha256"]:
                continue
            sim = jaccard(shingles(read_window(Path(a["path"]))), shingles(read_window(Path(b["path"]))))
            pairs.append({"tipo": "mesmo_nome_conteudo_diferente", "nome": name, "size": a["size"],
                          "a": a, "b": b, "similaridade": round(sim, 4)})
            break
    pairs.sort(key=lambda p: (-p["size"], p["nome"], p["a"]["path"], p["b"]["path"]))

    fields = ["nome", "caminho_a", "caminho_b", "sha_a", "sha_b", "similaridade",
              "tipo", "tamanho_bytes", "raiz_a", "raiz_b"]
    if args.csv:
        out = Path(args.csv)
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_name(f".{out.name}.tmp-{os.getpid()}")
        with tmp.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            for pair in pairs[:args.top]:
                writer.writerow({
                    "nome": pair["nome"],
                    "caminho_a": pair["a"]["path"], "caminho_b": pair["b"]["path"],
                    "sha_a": pair["a"]["sha256"], "sha_b": pair["b"]["sha256"],
                    "similaridade": pair["similaridade"], "tipo": pair["tipo"],
                    "tamanho_bytes": pair["size"],
                    "raiz_a": pair["a"]["root"], "raiz_b": pair["b"]["root"],
                })
        os.replace(tmp, out)
    if args.json:
        out = Path(args.json)
        tmp = out.with_name(f".{out.name}.tmp-{os.getpid()}")
        tmp.write_text(json.dumps({
            "schema": "autoresearchprimitives-dedup/v1",
            "roots": args.root,
            "occurrence_count": len(rows),
            "unique_names": len(by_name),
            "unique_sha256": len(by_sha),
            "duplicate_group_count": sum(1 for v in by_sha.values() if len(v) > 1),
            "redundant_copies": sum(len(v) - 1 for v in by_sha.values() if len(v) > 1),
            "near_duplicate_name_groups": sum(1 for v in by_name.values() if len({m["sha256"] for m in v}) > 1),
            "pairs": [{k: v for k, v in pair.items() if k not in {"a", "b"}} |
                      {"caminho_a": pair["a"]["path"], "caminho_b": pair["b"]["path"],
                       "sha_a": pair["a"]["sha256"], "sha_b": pair["b"]["sha256"]}
                      for pair in pairs],
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, out)
    print(json.dumps({
        "occurrences": len(rows),
        "unique_names": len(by_name),
        "unique_sha256": len(by_sha),
        "redundant_copies": sum(len(v) - 1 for v in by_sha.values() if len(v) > 1),
        "near_duplicate_name_groups": sum(1 for v in by_name.values() if len({m["sha256"] for m in v}) > 1),
        "pairs": len(pairs),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
