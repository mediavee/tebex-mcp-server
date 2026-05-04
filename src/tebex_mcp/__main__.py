"""Entry point: ``python -m tebex_mcp`` or the ``tebex-mcp`` console script."""

from __future__ import annotations

import asyncio

from tebex_mcp.server import run


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
