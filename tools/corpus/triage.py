"""Interactive triage loop.

Walks a candidates JSONL, presents each to the user with the source
context + the eyecite-derived `expected.canonical` guess, accepts an
action (accept / edit / reject / skip / quit / help), and appends
labeled cases to the output JSONL. Checkpoints after every decision.

UI is plain stdin/stdout so it works in any terminal — no curses, no
prompt_toolkit. For batch-mode use (scripts, CI), pass an iterable of
actions and the loop runs without input().
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Callable

from rich.console import Console
from rich.panel import Panel

from tools.corpus.state import TriageState, save_state
from tools.eval.dataset import load_dataset
from tools.eval.types import EvalCase


class TriageQuit(Exception):
    """User asked to quit; the loop is expected to save state and stop."""


HELP_TEXT = """
Actions:
  a  accept   keep the case as-is; canonical guess becomes the gold label.
  e  edit    type a corrected canonical form, then optional comma-separated
              field=value pairs (e.g. year=2010,case_name=Tews v. NHI, LLC).
  r  reject  drop the candidate (eyecite confused it, OCR ate it, etc).
  s  skip    don't decide; revisit next session.
  q  quit    save state and stop.
  ?  help    print this message.
""".strip()


def run_triage(
    *,
    candidates_path: str | Path,
    output_path: str | Path,
    session_dir: str | Path,
    state: TriageState,
    input_fn: Callable[[str], str] = input,
    console: Console | None = None,
    actions: Iterator[str] | None = None,
) -> TriageState:
    """Drive the triage loop until the user quits or candidates run out.

    `input_fn` and `actions` are injection points for tests; the real
    CLI uses input() and stdin. The loop appends to `output_path`,
    saves state after every decision, and returns the final state.
    """
    console = console or Console()
    candidates = load_dataset(candidates_path)
    total = len(candidates)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fp = open(output, "a", encoding="utf-8")
    actions_iter = actions

    try:
        while state.next_index < total:
            case = candidates[state.next_index]
            _render_case(case, state, total, console=console)
            try:
                action = next(actions_iter) if actions_iter is not None else input_fn("> ").strip()
            except (KeyboardInterrupt, EOFError):
                raise TriageQuit()
            action = (action or "").lower()
            if action in ("q", "quit"):
                raise TriageQuit()
            if action in ("?", "help", "h"):
                console.print(HELP_TEXT)
                continue
            if action in ("s", "skip"):
                state.record("skip")
            elif action in ("r", "reject"):
                state.record("reject")
            elif action in ("e", "edit"):
                edited = _prompt_edit(case, input_fn=input_fn, console=console)
                fp.write(json.dumps(_case_to_dict(edited), ensure_ascii=False) + "\n")
                fp.flush()
                state.record("edit")
            elif action in ("a", "accept", ""):
                fp.write(json.dumps(_case_to_dict(case), ensure_ascii=False) + "\n")
                fp.flush()
                state.record("accept")
            else:
                console.print(f"[yellow]Unknown action {action!r}. Type ? for help.[/]")
                continue
            save_state(session_dir, state)
    except TriageQuit:
        save_state(session_dir, state)
    finally:
        fp.close()
    return state


def _render_case(
    case: EvalCase,
    state: TriageState,
    total: int,
    *,
    console: Console,
) -> None:
    src = case.metadata.get("brief_source", "?")
    page = case.metadata.get("page_number", "?")
    canonical = case.expected.get("canonical", "")
    header = (
        f"[bold]{state.progress(total)}[/]\n"
        f"[dim]brief:[/] {src} · [dim]page:[/] {page}"
    )
    body = (
        f"\n[bold]Source citation:[/]\n  {case.input.get('raw', '')}\n\n"
        f"[bold]Context:[/]\n  {case.input.get('context', '')}\n\n"
        f"[bold]Candidate canonical:[/]\n  [green]{canonical}[/]"
    )
    console.print(Panel(header + body, expand=False))


def _prompt_edit(
    case: EvalCase,
    *,
    input_fn: Callable[[str], str],
    console: Console,
) -> EvalCase:
    current = case.expected.get("canonical", "")
    console.print(
        f"Edit canonical (Enter to keep [{current!r}]):"
    )
    new_canonical = input_fn("  canonical = ").strip() or current
    console.print(
        "Optional field overrides (comma-separated, key=value; Enter to skip):"
    )
    raw_fields = input_fn("  overrides = ").strip()
    expected = dict(case.expected)
    expected["canonical"] = new_canonical
    if raw_fields:
        for kv in raw_fields.split(","):
            if "=" not in kv:
                continue
            k, _, v = kv.strip().partition("=")
            k = k.strip()
            v = v.strip()
            if not k:
                continue
            expected[k] = _coerce_value(v)
    return EvalCase(
        id=case.id,
        input=case.input,
        expected=expected,
        tags=tuple(set(case.tags) | {"human_labeled"}),
        difficulty=case.difficulty,
        source="human_labeled",
        metadata=case.metadata,
    )


def _coerce_value(s: str):
    """Coerce numeric overrides to int/float for nicer JSON."""
    if s.isdigit():
        return int(s)
    try:
        return float(s)
    except ValueError:
        return s


def _case_to_dict(case: EvalCase) -> dict:
    return {
        "id": case.id,
        "input": case.input,
        "expected": case.expected,
        "tags": list(case.tags),
        "difficulty": case.difficulty,
        "source": case.source,
        **({"metadata": case.metadata} if case.metadata else {}),
    }
