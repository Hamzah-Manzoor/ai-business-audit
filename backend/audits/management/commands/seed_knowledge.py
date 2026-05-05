import logging
from pathlib import Path

import frontmatter
from django.conf import settings
from django.core.management.base import BaseCommand

from audits.models import KnowledgeDoc
from audits.rag.openai_client import EmbeddingError, embed_text

logger = logging.getLogger(__name__)

KNOWLEDGE_BASE_DIR = Path(settings.BASE_DIR).parent / 'knowledge_base'


def seed_knowledge_base() -> tuple[int, int]:
    """
    Scan KNOWLEDGE_BASE_DIR for *.md files, embed each, and save to KnowledgeDoc.
    Idempotent: skips docs whose title already exists in the DB.
    Returns (created_count, skipped_count).
    """
    created = 0
    skipped = 0

    for md_file in sorted(KNOWLEDGE_BASE_DIR.glob('*.md')):
        post = frontmatter.load(md_file)
        title = post.metadata.get('title', md_file.stem)
        category = post.metadata.get('category', 'general')
        source = post.metadata.get('source', md_file.name)
        content = post.content.strip()

        if KnowledgeDoc.objects.filter(title=title).exists():
            skipped += 1
            continue

        try:
            embedding = embed_text(content)
        except EmbeddingError as e:
            logger.error(f"Skipping '{title}' — embedding failed: {e}")
            continue

        KnowledgeDoc.objects.create(
            title=title,
            category=category,
            content=content,
            embedding=embedding,
            source=source,
        )
        created += 1

    return created, skipped


class Command(BaseCommand):
    help = 'Seed the KnowledgeDoc table from knowledge_base/*.md files'

    def handle(self, *args, **options):
        created, skipped = seed_knowledge_base()
        self.stdout.write(f"Done: {created} created, {skipped} skipped")
