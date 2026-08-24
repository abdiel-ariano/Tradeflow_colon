"""Regression tests for the resilient B2B TradeFlow Assistant endpoint."""
from __future__ import annotations

import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings

from core.models import Company, UserProfile
from core.utils.ai_assistant import SYSTEM_PROMPT


class ApiAsistenteChatFixesTests(TestCase):
    def setUp(self):
        self.client = Client()

    @override_settings(GROQ_API_KEY='test-groq-key')
    def test_groq_exception_falls_back_to_catalog_answer(self):
        with patch(
            'core.utils.ai_assistant._consultar_groq',
            side_effect=RuntimeError('upstream down'),
        ):
            resp = self.client.post(
                '/api/asistente/',
                data=json.dumps({'mensaje': 'hello'}),
                content_type='application/json',
            )

        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertTrue(payload['ok'])
        self.assertIn('TF Assistant', payload['respuesta'])
        self.assertNotIn('could not generate', payload['respuesta'].lower())

    @override_settings(GROQ_API_KEY='')
    def test_public_context_uses_catalog_backed_assistant_without_api_key(self):
        with patch(
            'core.utils.ai_assistant.consultar_asistente',
            return_value={
                'respuesta': 'B2B catalog answer',
                'respuesta_html': '<div>B2B catalog answer</div>',
                'confianza': 0.9,
                'categoria': 'catalogo',
            },
        ) as mocked:
            resp = self.client.post(
                '/api/asistente/',
                data=json.dumps({'mensaje': 'what is the free zone?', 'contexto': ''}),
                content_type='application/json',
            )

        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertTrue(payload['ok'])
        self.assertEqual(payload['respuesta'], 'B2B catalog answer')
        self.assertEqual(payload['categoria'], 'catalogo')
        kwargs = mocked.call_args.kwargs
        self.assertIsNone(kwargs.get('company'))

    def test_seller_context_uses_company_rag(self):
        user = User.objects.create_user(username='seller_chat', password='x')
        UserProfile.objects.update_or_create(user=user, defaults={'role': 'seller'})
        Company.objects.create(name='Seller Co', owner=user)
        self.client.force_login(user)

        with patch(
            'core.utils.ai_assistant.consultar_asistente',
            return_value={
                'respuesta': 'Orders this month: 3',
                'respuesta_html': '<div class="tf-bot-card">Orders this month: 3</div>',
            },
        ) as mocked:
            resp = self.client.post(
                '/api/asistente/',
                data=json.dumps(
                    {
                        'mensaje': 'top products by sales',
                        'contexto': 'seller',
                        'historial': [],
                    }
                ),
                content_type='application/json',
            )

        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertTrue(payload['ok'])
        self.assertEqual(payload['respuesta'], 'Orders this month: 3')
        kwargs = mocked.call_args.kwargs
        self.assertEqual(kwargs.get('company').name, 'Seller Co')

    @override_settings(GROQ_API_KEY='')
    def test_company_verification_question_has_deterministic_b2b_answer(self):
        """RUC/DV guidance stays available without an external AI provider."""
        resp = self.client.post(
            '/api/asistente/',
            data=json.dumps({'mensaje': '¿Cómo verifico una empresa con RUC y DV?'}),
            content_type='application/json',
        )

        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertTrue(payload['ok'])
        self.assertEqual(payload['categoria'], 'verificacion')
        self.assertFalse(payload['baja_confianza'])
        self.assertIn('RUC', payload['respuesta'])
        self.assertIn('DV', payload['respuesta'])
        self.assertIn('revisión manual', payload['respuesta'])
        self.assertNotIn('no tengo suficiente información', payload['respuesta'].lower())

    def test_system_prompt_is_b2b_only(self):
        self.assertIn('B2B wholesale marketplace', SYSTEM_PROMPT)
        self.assertNotIn('B2B/B2C', SYSTEM_PROMPT)
