"""Checkpoint persistence for the triage loop.

A triage session can take an hour or more; the user must be able to
quit and resume. Every accept/reject/edit/skip writes the updated
state file so a crash or interrupt loses at most one decision.

State file layout (JSON, in the session directory):

    {
      "session_id": "...",
      "candidates_path": "tools/corpus/.../candidates.jsonl",
      "output_path":     "tools/eval/datasets/.../wi_corpus.jsonl",
      "started_at": "2026-…",
      "next_index":  47,           # 0-based pointer into candidates_path
      "accepted":    32,
      "rejected":     5,
      "skipped":     10,
      "edited":       8
    }
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class TriageState:
    session_id: str
    candidates_path: str
    output_path: str
    next_index: int = 0
    accepted: int = 0
    rejected: int = 0
    skipped: int = 0
    edited: int = 0
    started_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def record(self, action: str) -> None:
        if action == "accept":
            self.accepted += 1
        elif action == "edit":
            self.edited += 1
            self.accepted += 1
        elif action == "reject":
            self.rejected += 1
        elif action == "skip":
            self.skipped += 1
        self.next_index += 1

    def progress(self, total: int) -> str:
        return (
            f"[{self.next_index}/{total}] "
            f"accepted={self.accepted} edited={self.edited} "
            f"rejected={self.rejected} skipped={self.skipped}"
        )


def state_path_for(session_dir: str | Path) -> Path:
    return Path(session_dir) / "state.json"


def load_state(session_dir: str | Path) -> TriageState | None:
    p = state_path_for(session_dir)
    if not p.exists():
        return None
    data = json.loads(p.read_text())
    return TriageState(**data)


def save_state(session_dir: str | Path, state: TriageState) -> None:
    p = state_path_for(session_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    # Atomic write.
    fd, tmp = tempfile.mkstemp(prefix=".state-", suffix=".json", dir=str(p.parent))
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(asdict(state), f, indent=2)
        os.replace(tmp, p)
    finally:
        if os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass
