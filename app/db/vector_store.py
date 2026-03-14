import os
import numpy as np
from dotenv import load_dotenv
from app.db.supabase_client import get_client

load_dotenv()

try:
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer("all-MiniLM-L6-v2")
    EMBEDDINGS_AVAILABLE = True
except Exception:
    EMBEDDINGS_AVAILABLE = False


def embed(text: str) -> list:
    if not EMBEDDINGS_AVAILABLE:
        return []
    return model.encode(text).tolist()


def cosine_similarity(a, b):
    a, b = np.array(a), np.array(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def find_similar_incidents(query: str, top_k: int = 3) -> list:
    if not EMBEDDINGS_AVAILABLE:
        return []
    sb = get_client()
    query_vec = embed(query)
    result = sb.table("incidents").select("*").eq("status", "resolved").execute()
    incidents = result.data
    if not incidents:
        return []
    scored = []
    for inc in incidents:
        text = f"{inc['title']} {inc.get('symptoms','')} {inc.get('root_cause','')}"
        inc_vec = embed(text)
        score = cosine_similarity(query_vec, inc_vec)
        scored.append((score, inc))
    scored.sort(key=lambda x: x[0], reverse=True)
    seen_titles = set()
    deduped = []
    for score, inc in scored:
        title = inc.get("title", "")
        if title not in seen_titles and score > 0.3:
            seen_titles.add(title)
            deduped.append((score, inc))
        if len(deduped) >= top_k:
            break
    return deduped


def get_pattern_summary(query: str) -> str:
    matches = find_similar_incidents(query)
    if not matches:
        return "No similar past incidents found."
    summary = f"Found {len(matches)} similar past incidents:\n\n"
    for score, inc in matches:
        summary += f"[{int(score*100)}% match] {inc['title']} ({inc['service']})\n"
        summary += f"  Root cause: {inc.get('root_cause', 'unknown')}\n"
        summary += f"  Resolution: {inc.get('resolution', 'unknown')}\n\n"
    return summary
