import logging

from fastembed import TextEmbedding

logger = logging.getLogger(__name__)

_model: TextEmbedding | None = None


def _get_model() -> TextEmbedding:
    global _model
    if _model is None:
        _model = TextEmbedding('BAAI/bge-small-en-v1.5')
    return _model


class EmbeddingError(Exception):
    pass


def embed_text(text: str) -> list[float]:
    try:
        model = _get_model()
        return next(model.embed([text])).tolist()
    except Exception as e:
        logger.error(f"Embedding failed: {e}")
        raise EmbeddingError(str(e)) from e
