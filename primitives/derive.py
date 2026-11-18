#!/usr/bin/env python3
"""Derive the primitive composition of a skill from the canonical registry.

Standalone: no harness imports, no third-party dependencies.  The derivation
rule is the one enforced by the harness gate (`primitive-skill-composition/v1`):

  1. the baseline primitive is always present;
  2. explicit `primitives:` / `x-primitives:` frontmatter is authoritative
     (unknown ids are reported and fail closed);
  3. otherwise primitives are matched by token-boundary signal against the
     skill's name, description, dependencies and headings.

Usage:
    python derive.py --registry registry.json SKILL.md [SKILL.md ...]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

LIST_FIELDS = {
    "primitives", "x-primitives", "requires", "dependencies",
    "depends_on", "related_skills", "tools", "capabilities",
}
FRONTMATTER_NAME_RE = re.compile(r"^name\s*:\s*(.*?)\s*$", re.I)
FRONTMATTER_DESCRIPTION_RE = re.compile(r"^description\s*:\s*(.*?)\s*$", re.I)


def unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def parse_inline_list(value: str) -> list[str]:
    value = value.strip()
    if not (value.startswith("[") and value.endswith("]")):
        return []
    body = value[1:-1].strip()
    if not body:
        return []
    return [unquote(part) for part in body.split(",") if unquote(part)]


def parse_frontmatter(text: str) -> dict:
    text = text.lstrip("\ufeff")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {"present": False, "fields": {}, "body": text}
    end = None
    for idx in range(1, min(len(lines), 2000)):
        if lines[idx].strip() in {"---", "..."}:
            end = idx
            break
    if end is None:
        return {"present": False, "fields": {}, "body": text}
    fields: dict = {}
    current_list = None
    for line in lines[1:end]:
        item = re.match(r"^\s+-\s+(.+?)\s*$", line)
        if item and current_list:
            fields.setdefault(current_list, []).append(unquote(item.group(1)))
            continue
        key_match = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*)\s*:\s*(.*?)\s*$", line)
        if not key_match:
            continue
        key = key_match.group(1).lower()
        value = key_match.group(2)
        if key in LIST_FIELDS:
            inline = parse_inline_list(value)
            if inline:
                fields[key] = inline
                current_list = None
            elif value.strip() in {"|", ">"}:
                fields[key] = []
                current_list = key
            else:
                fields[key] = [unquote(value)] if value.strip() else []
                current_list = key
        else:
            fields[key] = unquote(value)
            current_list = None
    return {"present": True, "fields": fields, "body": "\n".join(lines[end + 1:])}


def scalar(fields: dict, key: str) -> str:
    value = fields.get(key)
    if isinstance(value, list):
        return " ".join(str(item) for item in value)
    return str(value or "").strip()


def signal_hit(text: str, signal: str) -> bool:
    return bool(re.search(r"(?<![a-z0-9])" + re.escape(signal.lower()) + r"(?![a-z0-9])", text, re.I))


def read_metadata(path: Path) -> dict:
    raw = path.read_bytes()
    text = raw.decode("utf-8-sig", errors="replace")
    parsed = parse_frontmatter(text)
    fields = parsed.get("fields") or {}
    headings = [m.group(1).strip() for m in re.finditer(r"(?m)^#{1,3}\s+(.+?)\s*$", parsed.get("body") or "")]
    explicit: list[str] = []
    for key in ("primitives", "x-primitives"):
        raw_value = fields.get(key)
        if isinstance(raw_value, list):
            explicit.extend(str(v).strip() for v in raw_value if str(v).strip())
        elif isinstance(raw_value, str) and raw_value.strip():
            explicit.append(raw_value.strip())
    return {
        "path": str(path),
        "name": scalar(fields, "name") or path.parent.name,
        "description": scalar(fields, "description"),
        "dependencies": list(dict.fromkeys(
            str(v).strip()
            for key in ("requires", "dependencies", "depends_on", "related_skills", "tools", "capabilities")
            for v in (fields.get(key) or [])
            if str(v).strip()
        )),
        "headings": headings[:80],
        "explicit_primitives": list(dict.fromkeys(explicit)),
        "frontmatter_present": bool(parsed.get("present")),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size": len(raw),
    }


def derive(metadata: dict, registry: dict) -> dict:
    by_id = {p["id"]: p for p in registry.get("primitives") or []}
    baseline = registry["baseline_primitive"]
    explicit = list(metadata.get("explicit_primitives") or [])
    unknown = [item for item in explicit if item not in by_id]
    selected = [baseline]
    evidence = {baseline: ["mandatory baseline"]}
    if explicit:
        for item in explicit:
            if item in by_id and item not in selected:
                selected.append(item)
                evidence[item] = ["explicit frontmatter"]
    else:
        blob = " ".join([
            metadata.get("name") or "",
            metadata.get("description") or "",
            " ".join(metadata.get("dependencies") or []),
            " ".join(metadata.get("headings") or []),
        ]).lower()
        limit = int((registry.get("derivation") or {}).get("max_signals_per_primitive") or 3)
        for primitive in registry.get("primitives") or []:
            pid = primitive.get("id")
            if not pid or pid == baseline:
                continue
            hits = [s for s in primitive.get("signals") or [] if signal_hit(blob, s)]
            if hits:
                selected.append(pid)
                evidence[pid] = hits[:limit]
    order = {pid: i for i, pid in enumerate(registry.get("primitive_skill_ids") or [])}
    selected.sort(key=lambda pid: order.get(pid, 9999))
    return {
        "primitive_ids": selected,
        "primitive_evidence": evidence,
        "explicit_primitive_ids": explicit,
        "unknown_primitive_ids": unknown,
        "derivation_algorithm": (registry.get("derivation") or {}).get("algorithm"),
        "registry_version": registry.get("version"),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Derive the primitive composition of skills.")
    ap.add_argument("--registry", required=True)
    ap.add_argument("skills", nargs="+")
    args = ap.parse_args()
    registry = json.loads(Path(args.registry).read_text(encoding="utf-8"))
    failed = False
    for item in args.skills:
        path = Path(item)
        metadata = read_metadata(path)
        composition = derive(metadata, registry)
        print(json.dumps({"skill": metadata["name"], "path": metadata["path"], **composition},
                         ensure_ascii=False, indent=2))
        if composition["unknown_primitive_ids"]:
            failed = True
    return 3 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
