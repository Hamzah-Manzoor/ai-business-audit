from django.test import SimpleTestCase
from audits.scorers.schemas import CategoryResult, ParameterResult


class ParameterResultTest(SimpleTestCase):
    def test_valid_parameter(self):
        p = ParameterResult(key='meta_title', score=7, rationale='Title is good.')
        self.assertEqual(p.key, 'meta_title')
        self.assertEqual(p.score, 7)

    def test_model_dump(self):
        p = ParameterResult(key='h1_tag', score=0, rationale='Missing.')
        d = p.model_dump()
        self.assertEqual(d, {'key': 'h1_tag', 'score': 0, 'rationale': 'Missing.'})


class CategoryResultTest(SimpleTestCase):
    def _make(self, **kwargs):
        defaults = dict(
            category='seo', score=70,
            parameters=[ParameterResult(key='meta_title', score=7, rationale='OK')],
            top_issues=[], summary='Looks good.'
        )
        defaults.update(kwargs)
        return CategoryResult(**defaults)

    def test_valid_category_result(self):
        r = self._make()
        self.assertEqual(r.category, 'seo')
        self.assertEqual(r.score, 70)

    def test_model_dump_includes_parameters(self):
        r = self._make()
        d = r.model_dump()
        self.assertIn('parameters', d)
        self.assertEqual(d['parameters'][0]['key'], 'meta_title')
