import httpx
from app.config import settings

async def generate(prompt: str, system: str, temperature: float = 0.2) -> str:
    """Call a local Ollama-compatible API. Keep generation separate per document type."""
    payload = {
        "model": settings.ollama_model,
        "system": system,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temperature},
    }
    async with httpx.AsyncClient(timeout=240) as client:
        response = await client.post(f"{settings.ollama_base_url.rstrip('/')}/api/generate", json=payload)
        response.raise_for_status()
        data = response.json()
    result = (data.get("response") or "").strip()
    if not result:
        raise RuntimeError("The configured LLM returned an empty response.")
    return result

async def embed(text: str) -> list[float]:
    """fastembed wrapper for embedding text using the configured model. Returns a list of floats."""
    from fastembed import TextEmbedding
    from pathlib import Path

    MODEL = settings.embedding_model or "BAAI/bge-large-en-v1.5"
    model = TextEmbedding(MODEL, cache_dir=str(Path(__file__).parent / ".models"))
    vectors = [vector.tolist() for vector in model.passage_embed([text], batch_size=64)]
    return vectors[0] if vectors else []

async def embed_old(text: str) -> list[float]:
    """Use Ollama's embedding endpoint; set OLLAMA_EMBED_MODEL and dimensions consistently if changed."""
    import os
    model = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
    async with httpx.AsyncClient(timeout=90) as client:
        response = await client.post(
            f"{settings.ollama_base_url.rstrip('/')}/api/embed",
            json={"model": model, "input": text[:12000]},
        )
        response.raise_for_status()
        data = response.json()
    vectors = data.get("embeddings") or []
    if not vectors:
        raise RuntimeError("Embedding model returned no vector.")
    vector = vectors[0]
    from app.models import EMBEDDING_DIM
    if len(vector) != EMBEDDING_DIM:
        raise RuntimeError(
            f"Embedding dimension is {len(vector)}, but DB schema expects {EMBEDDING_DIM}. "
            "Set EMBEDDING_DIM in app/models.py to match your embedding model and recreate the jobs table."
        )
    return vector
