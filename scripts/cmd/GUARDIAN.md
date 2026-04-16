# Canonical Guardian Commands

## Purpose

This note documents the runtime guard layer for the canonical 4B experiment.

Use it when the formal canonical run is already in progress and you want:

- live progress refresh
- helper process restart
- resume-safe recovery
- Codex handoff artifacts

## Commands

- one-shot status + remediation:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/cmd/supervise_canonical.ps1 -Apply -RefreshLiveOnce
```

- run guardian in foreground:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/cmd/run_canonical_guardian.ps1
```

- launch guardian in background:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/cmd/launch_canonical_guardian.ps1
```

## Key Outputs

- `report_live/canonical_supervisor_status.json`
- `report_live/codex_incident_bundle.json`
- `docs/35_codex_reentry_prompt.md`
- `logs/canonical_guardian/events.jsonl`
