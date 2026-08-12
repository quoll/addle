# Claude Code Guidelines

## Scope of action

When asked to find, identify, locate, or discuss a problem — do not implement a
fix. Report the finding and stop. Only make code changes when explicitly asked to
do so (e.g. "fix it", "implement", "change", "update").

## Commit messages and PR comments

Do not include authorship lines in commit messages or PR comments. This means no
`Co-Authored-By:`, no mention of Claude or any other tool, and no AI-attribution
footers of any kind.

## Project specifics

- `grammar/DLESyntax.g4` is a **copy** of the grammar in the Java reference
  implementation (github.com/quoll/DLe). Do not edit it here to fix a parsing
  problem — the two implementations must define the same language. Change it
  upstream, copy it across, then run `tools/grammar.py generate` and
  `tools/grammar.py update`.
- `src/addle/_antlr/` is generated. Never edit it by hand.
- The IRIs and annotation properties in `src/addle/vocab.py` are a wire format
  shared with the Java implementation. Changing any of them breaks
  cross-implementation round-trips.
- Prefer adding to the round-trip tests over adding to the unit tests when a
  change affects what gets written: idempotence is the property that matters.
