import tempfile
from pathlib import Path
from unittest.mock import patch

from django.test import TestCase

from audits.management.commands.seed_knowledge import seed_knowledge_base
from audits.models import KnowledgeDoc
from audits.rag.retrieval import retrieve_similar_docs


def _make_vector(hot_index: int) -> list[float]:
    v = [0.0] * 1536
    v[hot_index] = 1.0
    return v


class RetrievalTest(TestCase):
    def setUp(self):
        # 3 docs aligned to dimension 0 (close to query)
        for i in range(3):
            KnowledgeDoc.objects.create(
                title=f"Close Doc {i}",
                category="conversion",
                content="CTA best practices",
                embedding=_make_vector(0),
                source="test",
            )
        # 2 docs aligned to dimension 1 (far from query)
        for i in range(2):
            KnowledgeDoc.objects.create(
                title=f"Far Doc {i}",
                category="seo",
                content="SEO checklist",
                embedding=_make_vector(1),
                source="test",
            )

    def test_retrieve_returns_top_3(self):
        with patch('audits.rag.retrieval.embed_text', return_value=_make_vector(0)):
            results = retrieve_similar_docs("weak CTA with no benefit language")

        self.assertEqual(len(results), 3)
        for doc in results:
            self.assertIn("Close Doc", doc.title)

    def test_retrieve_skips_null_embeddings(self):
        KnowledgeDoc.objects.create(
            title="No Embedding Doc",
            category="trust",
            content="trust signals",
            embedding=None,
            source="test",
        )
        with patch('audits.rag.retrieval.embed_text', return_value=_make_vector(0)):
            results = retrieve_similar_docs("missing trust signals")

        titles = [r.title for r in results]
        self.assertNotIn("No Embedding Doc", titles)

    def test_seed_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            md_content = "---\ntitle: Test Doc\ncategory: conversion\nsource: test\n---\n\nTest content."
            (tmp_path / "test_doc.md").write_text(md_content)

            with patch('audits.management.commands.seed_knowledge.embed_text', return_value=_make_vector(0)):
                seed_knowledge_base(directory=tmp_path)
                count_after_first = KnowledgeDoc.objects.count()
                seed_knowledge_base(directory=tmp_path)
                count_after_second = KnowledgeDoc.objects.count()

        self.assertEqual(count_after_first, count_after_second)
