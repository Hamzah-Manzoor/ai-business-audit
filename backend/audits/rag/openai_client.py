import logging

from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer('all-MiniLM-L6-v2')
    return _model


class EmbeddingError(Exception):
    pass


def embed_text(text: str) -> list[float]:
    try:
        model = _get_model()
        return model.encode(text, convert_to_numpy=True).tolist()
    except Exception as e:
        logger.error(f"Embedding failed: {e}")
        raise EmbeddingError(str(e)) from e
