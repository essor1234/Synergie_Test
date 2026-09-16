# Bright Path agent guide

Before changing the project, read `agent-progress.md`, `feature_list.json`, `session-handoff.md`, `quality-document.md`, and the relevant skill under `.agents/skills`.

## Working rules

- Work only inside this repository.
- Keep at most one feature marked `in_progress`.
- Follow the simplified architecture in `DESIGN.md` and `DECISIONS.md`.
- Preserve the source files in `data/source` as operational evidence.
- Record repeatable verification before marking a feature `passing`.
- Preserve unrelated user work.
- Never commit credentials, secret values, runtime databases, process state, or logs.
- Use `Set-Location -LiteralPath` and literal-path file operations for Windows paths containing brackets.
- Run `init.ps1 -Action Verify` before every handoff.

## Completion

Update `feature_list.json`, `agent-progress.md`, and `session-handoff.md`, complete `clean-state-checklist.md`, and leave a clean Git working tree after the phase commit.
