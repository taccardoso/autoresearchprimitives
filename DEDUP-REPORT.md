# DEDUP-REPORT

Generated 2026-11-18T03:18:31+00:00 from the
canonical artifacts of the harness control plane.

## Census (measured before the de-duplication)

| metric | value |
| --- | --- |
| active skill occurrences (gate boundary) | 26641 |
| distinct skill roots | 23 |
| distinct skill names | 19268 |
| distinct content fingerprints | 22472 |
| identical-content duplicate groups | 2426 |
| identical-content redundant copies | 4169 |
| ... of which in different roots | 4156 |
| same-name / different-content groups (near-duplicates) | 2159 |
| names present in more than one root | 2380 |

Platform split: {"windows": 6292, "wsl": 20349}

## De-duplication applied (measured after)

The ranked plan is `skills/DUPLICATES.csv` (200 pairs). Every pair whose
content is **identical** was applied: the duplicate became an alias of the
canonical copy, and a dated `tar` of the replaced file was written first.
Nothing was deleted.

| metric | value |
| --- | --- |
| identical-content pairs in the plan | 128 |
| pairs applicable on disk (both sides present, sha256 equal) | 123 |
| aliases actually applied | 120 |
| ... verified: alias reads the canonical bytes | 120 |
| ... verified: alias is not an independent copy | 120 |
| ... verified: dated tar carries the original bytes | 120 |
| aliases left as an independent copy | 0 |
| bytes no longer duplicated | 3129252 |
| bytes still duplicated in the applied scope | 0 |
| pairs deferred (root reserved by a parallel lease) | 3 |

Alias mechanisms: {'symlink': 108, 'hardlink': 12}

* **symlink** - the duplicate becomes a symbolic link to the canonical
  `SKILL.md`. Used when the duplicate and the canonical are both on the
  Windows volume, and when the canonical lives in WSL and the duplicate on
  Windows (the target is the `\\wsl.localhost` UNC path).
* **hardlink** - used when both live in WSL: a native POSIX hard link. A
  native WSL symlink is *not* followable from Windows, which is how the
  canonical gate reads the WSL roots, so it would fail the gate; a hard link
  is a plain file for every reader and still shares the bytes.

## Reading

* **identical-content** - the two `SKILL.md` files have the same content
  sha256. One of them can be kept and the other can point at it.
* **same-name / different-content** - the two files declare the same skill
  name but drifted apart. `similaridade` is the Jaccard index over normalized
  5-word shingles: a value near 1.0 means a cosmetic drift (safe to merge),
  a low value means a genuine fork that needs a human decision. Those pairs
  are **not** merged automatically.

## Primitives declared in the autoresearch family

| family | declared primitives |
| --- | --- |
| `autoresearch` | skill.execute_contract, experiment.initialize, candidate.propose, experiment.evaluate, experiment.record, experiment.decide |
| `autoresearch-skill` | skill.execute_contract, experiment.initialize, candidate.propose, experiment.evaluate, experiment.record, experiment.decide |
| `autoresearchclaw-skill-complete` | skill.execute_contract, quota.preflight, automation.execute, artifact.persist |
| `karpathy-autoresearch-skill` | skill.execute_contract, quota.preflight, experiment.initialize, candidate.propose, experiment.evaluate, experiment.decide |
| `vast-ai-autoresearch` | skill.execute_contract, quota.preflight, experiment.initialize, experiment.evaluate |

Canonical registry: version `1.1.0`, 24 primitives,
sha256 `32c3a2ec8ed35c82e64a4ae6c724064fda9bdf8161d1b6c9cd5d05bd7290cfe1`.

## Reproducing

```bash
python primitives/dedup.py --registry primitives/registry.json \
    --root /home/mascc/.agents/skills --root /home/mascc/.codex/skills \
    --root /home/mascc/.hermes/skills --root /home/mascc/.opencode/skills \
    --root /home/mascc/.config/opencode/skills --root /home/mascc/.gemini/skills \
    --root /home/mascc/.qwen/skills --root /home/mascc/.openclaw/skills \
    --csv duplicates.csv --json duplicates.json
```
