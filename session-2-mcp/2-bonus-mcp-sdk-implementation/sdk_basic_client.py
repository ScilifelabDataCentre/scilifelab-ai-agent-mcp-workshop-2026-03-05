# ═══════════════════════════════════════════════════════════════════════════════
# sdk_basic_client.py
# ═══════════════════════════════════════════════════════════════════════════════
# Run:  python sdk_basic_client.py
# Requires sdk_basic_server.py running on http://localhost:8501

import asyncio
from typing import Any

from mcp.client.streamable_http import streamablehttp_client
from mcp.client.session import ClientSession


def _text(obj: Any) -> str:
    """Extract text from an SDK content/result object."""
    for item in getattr(obj, "contents", None) or getattr(obj, "content", []):
        if hasattr(item, "text") and item.text:
            return item.text
        if hasattr(item, "blob"):
            return item.blob.decode("utf-8", errors="replace")
    return str(obj)


async def main() -> None:
    SERVER = "http://localhost:8501/mcp"
    print(f"Connecting to {SERVER}\n")

    async with streamablehttp_client(SERVER) as (r, w, _):
        async with ClientSession(r, w) as session:
            await session.initialize()
            print("Session initialised.\n")

            # List resources
            print("── Resources ─────────────────────────────────────")
            for res in await session.list_resources():
                uri = getattr(res, "uri", res)
                print(" •", uri)

            # Dataset overview
            print("\n── Dataset overview ──────────────────────────────")
            overview = await session.read_resource("dataset://drugs")
            import json
            data = json.loads(_text(overview))
            print(f"  {data['count']} drugs: {', '.join(data['ids'])}")

            # Read one drug record
            print("\n── Drug record: ERLOTINIB ────────────────────────")
            rec = await session.read_resource("drug://ERLOTINIB")
            print(_text(rec))

            # List tools
            print("\n── Tools ─────────────────────────────────────────")
            for t in await session.list_tools():
                name = getattr(t, "name", t)
                desc = getattr(t, "description", "")
                print(f" • {name}: {desc}")

            # Call get_drug_info
            print("\n── get_drug_info(IMATINIB) ───────────────────────")
            result = await session.call_tool(
                "get_drug_info", arguments={"drug_id": "IMATINIB"}
            )
            print(_text(result))


if __name__ == "__main__":
    asyncio.run(main())