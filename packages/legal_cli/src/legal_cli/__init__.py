"""The `lqg` command-line interface.

Use via the console script (`lqg check ...`) or programmatically:

    from legal_cli import app
    app(["check", "/path/to/brief.docx"])
"""

from legal_cli.app import app

__all__ = ["app"]
