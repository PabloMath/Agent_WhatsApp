"""
FastAPI — punto de entrada del servidor.
Maneja el handshake de verificación de Meta y los mensajes entrantes.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from app.config import settings
from app.db.models import Base, engine
from app.tasks import process_whatsapp_message


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Crea las tablas en PostgreSQL al arrancar (en producción usa Alembic)
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="WhatsApp Sales Agent", lifespan=lifespan)


# ─── Verificación del webhook (Meta lo llama una sola vez al configurar) ──────

@app.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
):
    if hub_mode == "subscribe" and hub_verify_token == settings.whatsapp_verify_token:
        return PlainTextResponse(hub_challenge)
    raise HTTPException(status_code=403, detail="Token de verificación inválido")


# ─── Recepción de mensajes ────────────────────────────────────────────────────

@app.post("/webhook")
async def receive_message(request: Request):
    payload = await request.json()

    try:
        entry   = payload["entry"][0]
        changes = entry["changes"][0]["value"]

        # Ignorar notificaciones de estado (delivered, read, etc.)
        if "messages" not in changes:
            return {"status": "ignored"}

        message_data = changes["messages"][0]

        # Solo procesamos mensajes de texto
        if message_data.get("type") != "text":
            return {"status": "ignored", "reason": "non-text message"}

        phone   = message_data["from"]
        message = message_data["text"]["body"]

        # Encola la tarea en Celery (responde a Meta en < 1 seg)
        process_whatsapp_message.delay(phone, message)

    except (KeyError, IndexError):
        # Payload inesperado — no relanzamos para que Meta no reintente
        pass

    return {"status": "ok"}


# ─── Webhook de pago (Stripe notifica cuando el pago se completa) ─────────────

@app.post("/payment/webhook")
async def payment_webhook(request: Request):
    import stripe
    stripe.api_key = settings.stripe_secret_key

    payload   = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret="whsec_..."  # reemplaza con tu secret
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Firma inválida")

    if event["type"] == "checkout.session.completed":
        session  = event["data"]["object"]
        order_id = int(session["metadata"]["order_id"])

        from app.db import SessionLocal
        from app.db import crud

        db = SessionLocal()
        try:
            crud.update_order_status(db, order_id, "pagado", payment_id=session["id"])
        finally:
            db.close()

    return {"status": "ok"}


# ─── Health check ─────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok"}
