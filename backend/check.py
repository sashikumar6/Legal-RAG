from app.core.qdrant_client import create_qdrant_client
client = create_qdrant_client()
info = client.get_collection("federal_corpus")
print("Total points:", info.points_count)
