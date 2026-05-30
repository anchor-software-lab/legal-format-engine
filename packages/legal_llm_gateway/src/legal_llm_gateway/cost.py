"""Per-call cost recording.

v0 ships an in-memory recorder useful for the CLI and tests. v1 adds
`PostgresCostRecorder` which appends to an `llm_calls` table read by
the billing endpoint (`/v1/billing/usage`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from legal_llm_gateway.types import LLMUsage


@dataclass
class CostRecord:
    prompt_id: str
    provider: str
    model: str
    usage: LLMUsage
    recorded_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class CostRecorder(Protocol):
    def record(
        self,
        *,
        prompt_id: str,
        provider: str,
        model: str,
        usage: LLMUsage,
    ) -> None: ...


@dataclass
class InMemoryCostRecorder:
    """Stores records in a list. Useful for tests and short-lived CLI runs."""

    records: list[CostRecord] = field(default_factory=list)

    def record(
        self,
        *,
        prompt_id: str,
        provider: str,
        model: str,
        usage: LLMUsage,
    ) -> None:
        self.records.append(
            CostRecord(
                prompt_id=prompt_id,
                provider=provider,
                model=model,
                usage=usage,
            )
        )

    def total_cents(self) -> int:
        return sum(r.usage.cost_usd_cents for r in self.records)

    def by_provider(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for r in self.records:
            out[r.provider] = out.get(r.provider, 0) + r.usage.cost_usd_cents
        return out

    def by_prompt(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for r in self.records:
            out[r.prompt_id] = out.get(r.prompt_id, 0) + r.usage.cost_usd_cents
        return out
