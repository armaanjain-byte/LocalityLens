"""Main entry point for the LocalityLens CLI."""

import typer

from localitylens.cli.commands import analyze, export
from localitylens.config.settings import settings

app = typer.Typer(
    name=settings.app_name,
    help="AST-aware observability tool for coding-agent traces.",
    add_completion=False,
)

# Register command sub-modules
app.add_typer(analyze.app, name="analyze")
app.add_typer(export.app, name="export")


@app.callback()
def main() -> None:
    """
    LocalityLens: Detect semantic thrashing and context locality failures 
    in coding-agent workflows.
    """
    pass


if __name__ == "__main__":
    app()