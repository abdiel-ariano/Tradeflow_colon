"""Regression tests for TradeFlow Assistant /api/asistente/ chat fixes."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings

from core.models import Company, UserProfile


@override_settings(GROQ_API_KEY='test-groq-key', GROQ_MODEL='llama-3.1-8b-instant')
class ApiAsistenteChatFixesTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_groq_exception_returns_ok_false(self):
        with patch('groq.Groq') as groq_cls:
            groq_cls.return_value.chat.completions.create.side_effect = RuntimeError(
                'upstream down'
            )
            resp = self.client.post(
                '/api/asistente/',
                data=json.dumps({'mensaje': 'hello'}),
                content_type='application/json',
            )
        self.assertEqual(resp.status_code, 503)
        payload = resp.json()
        self.assertFalse(payload['ok'])
        self.assertIn('could not generate', payload['respuesta'].lower())

    def test_non_seller_context_does_not_call_consultar_asistente(self):
        with patch('core.utils.ai_assistant.consultar_asistente') as mocked:
            with patch('groq.Groq') as groq_cls:
                choice = MagicMock()
                choice.message.content = 'General marketplace answer'
                groq_cls.return_value.chat.completions.create.return_value = MagicMock(
                    choices=[choice]
                )
                resp = self.client.post(
                    '/api/asistente/',
                    data=json.dumps({'mensaje': 'what is the free zone?', 'contexto': ''}),
                    content_type='application/json',
                )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['ok'])
        mocked.assert_not_called()

    def test_seller_context_uses_consultar_asistente_when_company_exists(self):
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
        mocked.assert_called_once()
        kwargs = mocked.call_args.kwargs
        self.assertEqual(kwargs.get('company').name, 'Seller Co')
