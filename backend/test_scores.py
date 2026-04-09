import shutil
import os
from qdrant_client import QdrantClient
from app.core.llm import create_embedding_fn

try:
    shutil.rmtree("/tmp/q_copy")
except: pass

shutil.copytree("qdrant_local_data", "/tmp/q_copy")
client = QdrantClient(path="/tmp/q_copy")
embed_fn = create_embedding_fn()
vec = embed_fn(["What is bankruptcy?"])[0]

try:
    res = client.search(
        collection_name="federal_corpus",
        query_vector=vec,
        limit=5
    )
    for r in res:
        print(f"[{r.score:.4f}] Title: {r.payload.get('title')} | {r.payload.get('text', '')[:100]}...")
except Exception as e:
    print(e)
