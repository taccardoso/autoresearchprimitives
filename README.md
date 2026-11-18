# autoresearchprimitives

The single canonical registry of **primitive skills**, plus the tooling that
*derives* every concrete skill from it.

This repo is the "program.md" idea of [karpathy/autoresearch] applied to a
skill library:

| karpathy/autoresearch              | autoresearchprimitives                          |
| ---------------------------------- | ----------------------------------------------- |
| `prepare.py` (fixed constants)      | `primitives/registry.json` (fixed contracts)   |
| `train.py` (the agent edits it)     | the concrete `SKILL.md` (the agent edits it)   |
| `program.md` (the human edits it)   | `primitives/registry.json` + `skills/INDEX.json` |
| `results.tsv` (keep/discard log)    | `skills/DUPLICATES.csv` (keep/discard log)       |
| `uv run train.py` (fixed budget)    | `python primitives/derive.py` (fixed cost)      |

Measured on 2026-11-17: the upstream repo
[karpathy/autoresearch](https://github.com/karpathy/autoresearch) at commit
`228791fb499afffb54b46200aca536f79142f117` has **no** primitives directory and
**no** primitives concept; its canonical loop lives entirely in `program.md`.
That loop is what this registry encodes.

## Why a registry at all

A skill library duplicated across harnesses drifts: the same skill name ends up
with several byte-different copies, each of them hand-edited, none of them
knowing about the others. The registry makes the *composition* of a skill a
derived fact instead of a copied one:

1. `primitives/registry.json` is the only place a primitive contract is written.
2. Every `SKILL.md` either declares its primitives explicitly in frontmatter
   (`primitives:` / `x-primitives:`) or has them derived from its name,
   description, dependencies and headings.
3. Nothing ever rewrites a `SKILL.md` in place; the composition map is a
   rebuildable index.

## Layout

```
primitives/registry.json   canonical primitive list (schema primitive-skill-registry/v1)
primitives/derive.py       skill -> primitive composition (standalone, no harness deps)
primitives/dedup.py        duplicate / near-duplicate finder over skill roots
skills/INDEX.json          derived index: name -> composition, canonical path, duplicate group
skills/DUPLICATES.csv      ranked duplicate pairs with content sha256 and similarity
DEDUP-REPORT.md            measured state of the library at generation time
```

## Usage

```bash
# composition of one skill
python primitives/derive.py --registry primitives/registry.json /path/to/SKILL.md

# duplicate census over one or more skill roots
python primitives/dedup.py --registry primitives/registry.json     --root ~/.agents/skills --root ~/.codex/skills --csv duplicates.csv
```

`derive.py` and `dedup.py` have no third-party dependencies and run on Python
3.10+.

## Canonical source

The authoritative copy of `primitives/registry.json` lives in the harness
control plane at
`control/PRIMITIVE_SKILL_REGISTRY.json` and is enforced by
`skill_primitive_gate.py`. This repo mirrors it; the mirror is regenerated
from the canonical artifact, never edited by hand.

[karpathy/autoresearch]: https://github.com/karpathy/autoresearch

## The skill manifest

`SKILL.md` is this repo as a loadable skill: it declares the primitives it
uses in its own frontmatter (`primitives:`), exactly the way a consumer
skill should.

## What was actually applied

* **The primitives were declared** in the canonical copy of each family of the
  `autoresearch` skill family (the copy whose frontmatter `name:` matches the
  family and that lives in a root owned by a `harness-canonical` harness).
  Only the frontmatter changed: the body of each `SKILL.md` is byte-identical
  to the dated backup taken before the edit.
* **The duplicates were aliased, not deleted.** Every byte-identical pair in
  the ranked plan had its duplicate replaced by an alias of the canonical
  copy, after a dated `tar` of the replaced file was written. The proof is
  `skills/DEDUP-APPLIED.jsonl`; the census before and after is in
  `DEDUP-REPORT.md`.
