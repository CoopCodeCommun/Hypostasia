"""
Tests pour l'application Hypostasis Extractor.
"""

from django.test import TestCase
from core.models import Page, AIModel, Provider
from .models import ExtractionJob, ExtractedEntity, ExtractionExample


class ExtractionJobModelTests(TestCase):
    
    def setUp(self):
        self.page = Page.objects.create(
            url='https://example.com/article',
            html_original='<html><body>Test</body></html>',
            html_readability='<article>Test content</article>',
            text_readability='Test content'
        )
        self.ai_model = AIModel.objects.create(
            name='Test Model',
            provider=Provider.MOCK,
            model_name='gemini-2.5-flash'
        )
    
    def test_job_creation(self):
        job = ExtractionJob.objects.create(
            page=self.page,
            ai_model=self.ai_model,
            name='Test Extraction',
            prompt_description='Extract test entities'
        )
        self.assertEqual(job.status, 'pending')
        self.assertEqual(str(job), f'Test Extraction sur {self.page.url[:50]}...')


class ExtractedEntityModelTests(TestCase):
    
    def setUp(self):
        self.page = Page.objects.create(
            url='https://example.com/article',
            html_original='<html><body>Test</body></html>',
            html_readability='<article>Test content</article>',
            text_readability='Test content'
        )
        self.job = ExtractionJob.objects.create(
            page=self.page,
            name='Test Job',
            prompt_description='Test'
        )
    
    def test_entity_creation(self):
        entity = ExtractedEntity.objects.create(
            job=self.job,
            extraction_class='probleme',
            extraction_text='Test entity text',
            start_char=0,
            end_char=10,
            attributes={'severity': 'high'}
        )
        self.assertEqual(str(entity), '[probleme] Test entity text...')
        self.assertFalse(entity.user_validated)


class ExtractionExampleModelTests(TestCase):
    
    def test_example_creation(self):
        example = ExtractionExample.objects.create(
            name='Test Example',
            example_text='Example text here',
            example_extractions=[
                {
                    'extraction_class': 'character',
                    'extraction_text': 'Example',
                    'attributes': {'type': 'test'}
                }
            ]
        )
        self.assertTrue(example.is_active)
        self.assertEqual(str(example), 'Test Example')
