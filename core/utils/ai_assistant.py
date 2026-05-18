"""
AI Assistant para TradeFlow Colón.
Usa Groq API (gratuita) con modelo llama3-8b-8192.
Asistente especializado en la Zona Libre de Colón
para ayudar a compradores con sus consultas.

Dependencias: groq (pip install groq)
Variables de entorno: GROQ_API_KEY
"""
from django.conf import settings

SYSTEM_PROMPT = """
Eres el asistente virtual de TradeFlow Colón, el
marketplace oficial de la Zona Libre de Colón, Panamá.

Tu nombre es TF Assistant.

Ayudas a los usuarios con:
- Información sobre productos disponibles en la ZLC
- Proceso de compra en TradeFlow
- Información sobre la Zona Libre de Colón
- Consultas sobre órdenes y pagos
- Recomendaciones de productos según necesidades

La Zona Libre de Colón es el segundo hub comercial
más grande del mundo, con más de 2,600 empresas
y transacciones anuales de más de $33 mil millones.

Responde siempre en el idioma del usuario.
Sé conciso, amable y profesional.
Máximo 3 párrafos por respuesta.
Si no sabes algo específico, sugiere contactar
al soporte de TradeFlow en info@tradeflow.pa
"""


def consultar_asistente(mensaje_usuario, historial=None):
    """
    Envía un mensaje al asistente de IA y obtiene respuesta.

    Args:
        mensaje_usuario: Pregunta o mensaje del usuario.
        historial: Lista de mensajes anteriores
            [{"role": "user/assistant", "content": "texto"}].

    Returns:
        str: Respuesta del asistente o mensaje de fallback si hay error.
    """
    if not settings.GROQ_API_KEY:
        return (
            'El asistente no está disponible en este momento. '
            'Contáctanos en info@tradeflow.pa'
        )

    try:
        from groq import Groq

        client = Groq(api_key=settings.GROQ_API_KEY)
        messages = [{'role': 'system', 'content': SYSTEM_PROMPT}]

        if historial:
            messages.extend(historial[-6:])

        messages.append({
            'role': 'user',
            'content': mensaje_usuario[:500],
        })

        response = client.chat.completions.create(
            model='llama3-8b-8192',
            messages=messages,
            max_tokens=400,
            temperature=0.7,
        )
        return response.choices[0].message.content
    except Exception:
        return (
            'Lo siento, no puedo responder en este momento. '
            'Intenta más tarde o escríbenos a info@tradeflow.pa'
        )
