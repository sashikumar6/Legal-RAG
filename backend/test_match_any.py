from app.core.qdrant_client import create_qdrant_client
from qdrant_client.models import Filter, FieldCondition, MatchAny
from app.core.llm import create_embedding_fn
client = create_qdrant_client()
embed_fn = create_embedding_fn()
vec = embed_fn(["Explain Chapter 7 bankruptcy filing requirements"])[0]

res = client.search(
    collection_name="federal_corpus",
    query_vector=vec,
    limit=5,
    query_filter=Filter(must=[FieldCondition(key="title_number", match=MatchAny(any=[26, 11]))])
)
print("Hits:", len(res))
for r in res:
    print(f"[{r.score:.4f}] {r.payload.get('text', '')[:100]}...")
