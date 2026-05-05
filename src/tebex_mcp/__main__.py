"""Entry point: ``python -m tebex_mcp`` or the ``tebex-mcp`` console script."""

from __future__ import annotations

import asyncio

from tebex_mcp.server import run_async


def main() -> None:
    asyncio.run(run_async())


if __name__ == "__main__":
    main()
