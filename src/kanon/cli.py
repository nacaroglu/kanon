"""The `kanon` command-line interface.

Design: the CLI calls application code in-process rather than going through HTTP,
so it works without a running server and shares services with the API.
"""

import typer

from kanon import __version__

app = typer.Typer(help="Kanon command-line interface.", no_args_is_help=True)


@app.callback()
def main() -> None:
    """Kanon command-line interface."""


@app.command()
def version() -> None:
    """Print the Kanon version."""
    typer.echo(__version__)
