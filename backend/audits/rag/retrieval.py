import logging

from pgvector.django import CosineDistance

from audits.models import KnowledgeDoc
from .openai_client import embed_text

logger = logging.getLogger(__name__)


def retrieve_similar_docs(issue_description: str, top_k: int = 3) -> list[KnowledgeDoc]:
    query_vector = embed_text(issue_description)
    return list(
        KnowledgeDoc.objects
        .exclude(embedding=None)
        .annotate(distance=CosineDistance('embedding', query_vector))
        .order_by('distance')[:top_k]
    )
