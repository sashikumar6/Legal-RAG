import os
import sys

sys.path.insert(0, os.path.abspath("backend"))

from app.core.config import settings

key = settings.openai_api_key
if key:
    print(f"Key starts with: {key[:10]}...")
else:
    print("NO KEY")
