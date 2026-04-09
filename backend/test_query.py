import asyncio
import logging
from app.core.schemas import ChatRequest, QueryMode
from app.services import ChatService
from app.core.qdrant_client import create_qdrant_client
from app.core.llm import create_embedding_fn

logging.basicConfig(level=logging.DEBUG)

async def main():
    q_client = create_qdrant_client()
    emb_fn = create_embedding_fn()
    svc = ChatService(qdrant_client=q_client, embedding_fn=emb_fn)
    print("Graph:", svc.agent_graph)
    req = ChatRequest(query="who is the victim", mode=QueryMode.FEDERAL, session_id="test1234")
    res = await svc.process_query(req)
    print("---------------------------------")
    print("RESPONSE:", res)
    print("---------------------------------")

asyncio.run(main())
