import asyncio
import os
import sys

# Ensure backend directory is in PYTHONPATH
sys.path.insert(0, os.path.abspath("backend"))

from app.core.config import settings
from app.core.qdrant_client import create_qdrant_client

def inspect_db():
    client = create_qdrant_client()
    if not client:
        print("Failed to initialize Qdrant client")
        return
        
    try:
        colls = client.get_collections()
        print("Collections:", colls)
        
        for coll in colls.collections:
            info = client.get_collection(coll.name)
            print(f"Collection {coll.name}: {info.points_count} points")
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    inspect_db()
