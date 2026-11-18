---
name: autoresearchprimitives
description: Canonical primitive-skill registry plus the tooling that derives every concrete skill's composition from it and that de-duplicates byte-identical skill installations across harness roots. Use when composing a skill out of primitives, deriving a skill's primitive set, declaring primitives in a SKILL.md, or auditing duplicate skill copies.
primitives:
  - skill.execute_contract
  - experiment.initialize
  - candidate.propose
  - experiment.evaluate
  - experiment.record
  - experiment.decide
  - quota.preflight
  - data.analyze
  - artifact.persist
---

# autoresearchprimitives

The single canonical registry of **primitive skills**, plus the tooling that
*derives* every concrete skill from it and that *de-duplicates* the copies a
skill library scatters across harness roots.

This repo is the "program.md" idea of [karpathy/autoresearch] applied to a
skill library:

| karpathy/autoresearch              | autoresearchprimitives                          |
| ---------------------------------- | ----------------------------------------------- |
| `prepare.py` (fixed constants)      | `primitives/registry.json` (fixed contracts)   |
| `train.py` (the agent edits it)     | the concrete `SKILL.md` (the agent edits it)   |
| `program.md` (the human edits it)   | `primitives/registry.json` + `skills/INDEX.json` |
| `results.tsv` (keep/discard log)    | `skills/DUPLICATES.csv` (keep/discard log)       |
| `uv run train.py` (fixed budget)    | `python primitives/derive.py` (fixed cost)      |

The upstream repo [karpathy/autoresearch] at commit
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
3. The composition map is a rebuildable index, not a hand-maintained copy.

## Layout

```
primitives/registry.json   canonical primitive list (schema primitive-skill-registry/v1)
primitives/derive.py       derive one skill's composition from the registry
primitives/dedup.py        census of duplicate skill copies across roots
skills/INDEX.json          every active skill name with its content fingerprint
skills/DUPLICATES.csv      ranked duplicate pairs (identical content first)
skills/DEDUP-APPLIED.jsonl what the de-duplication actually applied, and proved
```

## Declaring primitives in a skill

`primitives:` in the frontmatter is authoritative; unknown ids fail closed.

```markdown
---
name: autoresearch
description: Autonomous experiment loop that tries ideas and keeps what works.
primitives:
  - skill.execute_contract
  - experiment.initialize
  - candidate.propose
  - experiment.evaluate
  - experiment.record
  - experiment.decide
---
```

## Using the tooling

```bash
python primitives/derive.py --registry primitives/registry.json <path-to-SKILL.md>
python primitives/dedup.py --registry primitives/registry.json     --root /home/mascc/.agents/skills --root /home/mascc/.gemini/skills     --csv duplicates.csv --json duplicates.json
```

## De-duplication that is reversible

A byte-identical copy is not deleted: it becomes an **alias** of the canonical
copy, and a dated `tar` of the replaced file is kept first. Every applied
alias is recorded in `skills/DEDUP-APPLIED.jsonl` with the canonical path, the
sha256 before and after and the backup that restores it.

[karpathy/autoresearch]: https://github.com/karpathy/autoresearch
