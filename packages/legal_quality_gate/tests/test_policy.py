"""Policy loading + auto-fix glob matching."""

from __future__ import annotations

import textwrap

from legal_quality_gate import load_policy


def test_load_policy(tmp_path):
    p = tmp_path / "policy.yaml"
    p.write_text(
        textwrap.dedent(
            """
            name: wi_appellate
            enabled:
              - formatting.spec_diff
              - bluebook.case_form
            severity_overrides:
              bluebook.case_form: warning
            auto_fix:
              allow:
                - FORMAT.FONT.*
                - BB.SIGNAL.UNDERLINE
            """
        )
    )

    policy = load_policy(p)
    assert policy.name == "wi_appellate"
    assert policy.enabled == ["formatting.spec_diff", "bluebook.case_form"]
    assert policy.severity_overrides == {"bluebook.case_form": "warning"}

    assert policy.auto_fix_allowed("FORMAT.FONT.NAME")
    assert policy.auto_fix_allowed("FORMAT.FONT.SIZE")
    assert policy.auto_fix_allowed("BB.SIGNAL.UNDERLINE")
    assert not policy.auto_fix_allowed("FORMAT.MARGIN.TOP")
    assert not policy.auto_fix_allowed("CITE.GHOST")
