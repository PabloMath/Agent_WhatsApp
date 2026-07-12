import asyncio
from celery import Celery
from twilio.rest import Client  # Importamos el cliente oficial de Twilio
from app.config import settings

celery_app = Celery("whatsapp_agent", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(task_serializer="json", result_serializer="json", accept_content=["json"], timezone="America/Bogota")

def _send_twilio_whatsapp_message(phone: str, text: str) -> None:
    """
    Envía el mensaje de respuesta al usuario utilizando la API de Twilio.
    """
    # Inicializamos el cliente con tus credenciales de Twilio
    client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
    
    # Aseguramos que el formato del número incluya el prefijo que Twilio requiere
    # Si el 'phone' ya viene con el '+57...', Twilio necesita 'whatsapp:+57...'
    to_whatsapp = f"whatsapp:{phone}" if not phone.startswith("whatsapp:") else phone
    from_whatsapp = f"whatsapp:{settings.twilio_whatsapp_number}" # Tu número de Sandbox o comercial
    
    # Enviamos el mensaje
    client.messages.create(
        body=text,
        from_=from_whatsapp,
        to=to_whatsapp
    )

@celery_app.task(bind=True, max_retries=3, default_retry_delay=5)
def process_whatsapp_message(self, phone: str, message: str) -> None:
    try:
        from app.agent.agent import handle_message
        respuesta = asyncio.run(handle_message(phone, message))
        
        # Cambiamos la función de envío de Meta por la de Twilio
        _send_twilio_whatsapp_message(phone, respuesta)
    except Exception as exc:
        raise self.retry(exc=exc)