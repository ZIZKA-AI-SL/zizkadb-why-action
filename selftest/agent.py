"""Test agent: logs a causal chain that ends in a failure."""
import asyncio, sys
from zizkadb import ZizkaDB

async def main():
    async with ZizkaDB() as db:
        a = "refund-agent"
        u = await db.log(agent=a, event="user_message", data={"text": "Refund order 42"}, session_id="run-1")
        t = await db.log(agent=a, event="tool_call", data={"tool": "lookup_order"}, parent_id=u.event_id, session_id="run-1")
        r = await db.log(agent=a, event="tool_result", data={"status": "delivered"}, parent_id=t.event_id, session_id="run-1")
        c = await db.log(agent=a, event="tool_call", data={"tool": "refund"}, parent_id=r.event_id, session_id="run-1")
        await db.log(agent=a, event="tool_error", data={"error": "refund denied"}, parent_id=c.event_id, session_id="run-1")
    sys.exit(1 if "--fail" in sys.argv else 0)

asyncio.run(main())
