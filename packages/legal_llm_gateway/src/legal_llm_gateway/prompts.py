"""Load versioned prompt files from `schemas/prompts/`.

File format:

    ---
    id: <namespace>.<name>@v<n>
    model_class: cheap_fast | balanced | top_quality | local_only
    temperature: 0.0
    max_tokens: 512
    pinned_model: anthropic/claude-haiku-4-5  # optional
    cache_segments: [SYSTEM]                  # optional
    output_schema_ref: bluebook/normalize_case_output.schema.json
    ---

    SYSTEM:

    <system prompt content, possibly multi-paragraph>

    USER:

    <user prompt content with {variable} placeholders>

`load_prompt(prompt_id, search_dir=...)` resolves `<namespace>.<name>`
in `prompt_id` to `<search_dir>/<namespace>.<name>.md` (dropping the
`@vN` suffix from the filename) and parses it into a `PromptSpec`.

Versioning: prompts are addressed by `<id>@v<n>`. Bumping the version
means a new file (`bluebook.normalize_case@v2.md`) or — more commonly —
a new `id` line in the same file's frontmatter that callers pin against.
The loader matches by frontmatter `id`, not filename, so the two stay
decoupled.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

import yaml

from legal_llm_gateway.types import ModelClass, PromptSpec

# Match a section header at the start of a line: "SYSTEM:" or "USER:"
# (uppercase, alphanumeric/underscore, terminated by colon and newline).
_SECTION_HEADER = re.compile(r"^(?P<label>[A-Z][A-Z0-9_]*):\s*$", re.MULTILINE)

# Frontmatter delimiter.
_FRONTMATTER = re.compile(
    r"\A---\s*\n(?P<yaml>.*?)\n---\s*\n(?P<body>.*)\Z",
    re.DOTALL,
)


class PromptNotFound(LookupError):
    pass


class PromptParseError(ValueError):
    pass


def load_prompt(
    prompt_id: str,
    *,
    search_dirs: Iterable[Path] | None = None,
) -> PromptSpec:
    """Resolve `prompt_id` to a parsed `PromptSpec`.

    `prompt_id` is `<namespace>.<name>@v<n>` (the `@v<n>` is optional —
    when absent, the loader picks the highest-numbered version in the
    matching file).

    `search_dirs` defaults to `<repo_root>/schemas/prompts/`. Pass a
    list to override (useful for tests that ship their own prompts).
    """
    dirs = list(search_dirs or [_default_prompt_dir()])
    base, version = _split_id(prompt_id)

    for d in dirs:
        for path in _candidate_paths(d, base):
            spec = _parse_file(path)
            if spec.id == prompt_id:
                return spec
            # Match `<namespace>.<name>` if caller didn't specify a version.
            spec_base, _ = _split_id(spec.id)
            if version is None and spec_base == base:
                return spec

    raise PromptNotFound(
        f"prompt {prompt_id!r} not found in {[str(d) for d in dirs]}"
    )


def _split_id(prompt_id: str) -> tuple[str, str | None]:
    if "@" in prompt_id:
        base, _, version = prompt_id.partition("@")
        return base, version
    return prompt_id, None


def _candidate_paths(directory: Path, base: str) -> Iterable[Path]:
    """Yield candidate prompt files for `base`.

    Tries `<dir>/<base>.md` first (the conventional one-file-per-prompt
    layout), then any file in the directory (so callers can name files
    however they like as long as the frontmatter `id` matches).
    """
    canonical = directory / f"{base}.md"
    if canonical.exists():
        yield canonical
    if directory.is_dir():
        for path in sorted(directory.glob("*.md")):
            if path != canonical:
                yield path


def _parse_file(path: Path) -> PromptSpec:
    text = path.read_text()
    fm_match = _FRONTMATTER.match(text)
    if not fm_match:
        raise PromptParseError(
            f"{path}: missing YAML frontmatter delimited by --- lines"
        )

    try:
        meta = yaml.safe_load(fm_match.group("yaml")) or {}
    except yaml.YAMLError as exc:
        raise PromptParseError(f"{path}: invalid frontmatter YAML: {exc}") from exc

    if "id" not in meta:
        raise PromptParseError(f"{path}: frontmatter missing required 'id'")

    body = fm_match.group("body")
    sections = _split_sections(body)

    system = sections.get("SYSTEM", "").strip()
    user = sections.get("USER", "").strip()
    if not user:
        raise PromptParseError(f"{path}: USER section is empty or missing")

    model_class = ModelClass(meta.get("model_class", ModelClass.BALANCED.value))

    return PromptSpec(
        id=meta["id"],
        system_template=system,
        user_template=user,
        model_class=model_class,
        temperature=float(meta.get("temperature", 0.0)),
        max_tokens=int(meta.get("max_tokens", 1024)),
        pinned_model=meta.get("pinned_model"),
        cache_segments=list(meta.get("cache_segments") or []),
        output_schema_ref=meta.get("output_schema_ref"),
    )


def _split_sections(body: str) -> dict[str, str]:
    """Split a prompt body into labelled sections.

    Sections start at a line like `LABEL:` and run until the next such
    line or end of file. Any text before the first label is discarded
    (treated as comments / formatting whitespace).
    """
    matches = list(_SECTION_HEADER.finditer(body))
    if not matches:
        return {}

    sections: dict[str, str] = {}
    for i, m in enumerate(matches):
        label = m.group("label")
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        sections[label] = body[start:end].strip("\n")
    return sections


def _default_prompt_dir() -> Path:
    # Walk up from this file to the repo root, then into schemas/prompts.
    # packages/legal_llm_gateway/src/legal_llm_gateway/prompts.py
    # parents[0]: legal_llm_gateway/
    # parents[1]: src/
    # parents[2]: legal_llm_gateway/  (package root)
    # parents[3]: packages/
    # parents[4]: <repo root>
    return Path(__file__).resolve().parents[4] / "schemas" / "prompts"
