# repo-replay-data (PUBLIC)

Repo Replay data store — public splice (owner: as much public as possible,
2026-10-30). Engine + code: `timerloggedout-spec/repo-replay`.

## Layout
- `db/stage_scores.db` — combined-corpus stage scores (every stage, per
  file, % by version|method columns) + kind-categorized pointer index
  (class | fn | method).
- `db/stage_scores_assistant.db` — ASSISTANT-only corpus (the
  reconstruction target).
- `db/stage_scores_user.db` — USER-only corpus (separate database).
- `harvest/MANIFEST.json` — harvest inventory: path, bytes, sha256 per file.

## The splice
Raw harvest bytes + the restricted sensitivity sidecar (sha_orig of
sensitive spans) live in the PRIVATE repo `repo-replay-sensitive` —
session exports contain token/cookie/PII spans (sensitivity-rules v0.1:
taxonomy C1–C5, fail-closed). Everything else — scores, indexes,
manifests, reports — is public here. Scores are corpus-relative;
NULL % = measured GAP, never hidden.
