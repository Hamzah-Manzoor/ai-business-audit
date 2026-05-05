import logging
import os

from openai import OpenAI

logger = logging.getLogger(__name__)


class EmbeddingError(Exception):
    pass


def embed_text(text: str) -> list[float]:
    client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))
    try:
        response = client.embeddings.create(
            model='text-embedding-3-small',
            input=text,
        )
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"OpenAI embedding failed: {e}")
        raise EmbeddingError(str(e)) from e
