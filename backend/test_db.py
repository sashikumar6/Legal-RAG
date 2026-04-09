from app.core.qdrant_client import create_qdrant_client
from app.core.llm import create_embedding_fn
client = create_qdrant_client()
embed_fn = create_embedding_fn()
vec = embed_fn(["What is bankruptcy?"])[0]

from qdrant_client.models import Filter, FieldCondition, MatchValue

res = client.search(
    collection_name="federal_corpus",
    query_vector=vec,
    limit=5
)
for r in res:
    print(f"[{r.score:.3f}] {r.payload.get('text', '')[:100]}...")
