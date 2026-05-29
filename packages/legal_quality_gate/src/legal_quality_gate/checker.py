"""The Checker protocol and CheckContext.

Every analyzer in the quality gate — formatting, Bluebook, citation
existence, defined-term consistency, quote accuracy — implements
`Checker`. The Pipeline runs them concurrently grouped by capability:
deterministic checkers (no `Capability.LLM` / `Capability.NETWORK`) run
first; LLM and network-bound checkers run after, so deterministic
findings can short-circuit obviously-wrong document state before
spending money on LLM calls.
"""

from __future__ import annotations

from typing import Awaitable, Callable, Iterable, Protocol, runtime_checkable

from legal_quality_gate.types import (
    Capability,
    Document,
    Finding,
    Segment,
    Severity,
)


class CheckContext:
    """Per-run context passed to every Checker.

    Provides:
      - `get_text(segment)`: returns the plaintext of a segment from the
        encrypted blob. Checkers MUST go through this method rather than
        reading any stored field, so the encryption boundary stays clean.
      - `resolved_style`: the merged FormatSpec for this document (output
        of `legal_format_engine.merge_with_rules`). Available so style
        checkers don't each redo the merge.
      - `style_guide`, `policy`, and arbitrary services (`llm`,
        `authority`) injected by the Pipeline.
    """

    def __init__(
        self,
        *,
        text_loader: Callable[[Segment], str],
        resolved_style: dict | None = None,
        style_guide: dict | None = None,
        policy: dict | None = None,
        services: dict | None = None,
    ) -> None:
        self._text_loader = text_loader
        self.resolved_style = resolved_style or {}
        self.style_guide = style_guide or {}
        self.policy = policy or {}
        self.services = services or {}

    def get_text(self, segment: Segment) -> str:
        return self._text_loader(segment)

    def service(self, name: str):
        return self.services.get(name)


@runtime_checkable
class Checker(Protocol):
    """Protocol every checker implements.

    `id` is a stable identifier (e.g. `"formatting.spec_diff"`).
    `severity_default` is the severity used for findings that don't
    override. `requires` declares what runtime capabilities the
    checker needs; the Pipeline uses it to filter checkers out when
    capabilities are unavailable (e.g. offline run with no LLM).
    """

    id: str
    severity_default: Severity
    requires: Iterable[Capability]

    def check(
        self, document: Document, ctx: CheckContext
    ) -> Awaitable[list[Finding]] | list[Finding]: ...
