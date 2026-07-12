from contextlib import asynccontextmanager
import asyncio
import json  # <-- Importado para procesar la respuesta de Groq
from fastapi import FastAPI, HTTPException, Query, Request, Form, Response, APIRouter, Depends, UploadFile, File
from fastapi.responses import PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel  # <-- Importado para el molde del JSON
from twilio.twiml.messaging_response import MessagingResponse

import pandas as pd
import io
import os  # <-- Importado para manejar el archivo temporal

from app.db import SessionLocal
from app.db.models import Product  # Asegúrate de tener importado tu modelo de Producto
from sqlalchemy import desc, text  # <-- ¡Ajuste Clave!: Se agregó 'text' para consultas nativas SQL
from app.config import settings
from app.db.models import Base, engine
from app.agent.agent import handle_message 
from app.tasks import _send_twilio_whatsapp_message
from app.agent.admin_tools import actualizar_precio_producto  # <-- Tu nueva herramienta
from langchain_groq import ChatGroq  # <-- Para que el backend entienda a la dueña

# Carpeta temporal para guardar el inventario mientras la dueña lo confirma en el chat
UPLOAD_DIR = "/tmp"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Esto asegura que las tablas de la base de datos se creen al iniciar
    Base.metadata.create_all(bind=engine)
    yield

# Inicializamos la aplicación de FastAPI pasándole el lifespan
app = FastAPI(title="WhatsApp Sales Agent", lifespan=lifespan)

# Agrega esto justo después de inicializar app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"], # El puerto por defecto de Next.js
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === ENDPOINT DIRECTO PARA TWILIO ===
@app.post("/twilio/webhook")
async def receive_twilio_message(
    Body: str = Form(...), 
    From: str = Form(...)
):
    try:
        # Limpiamos el número y el mensaje que envía Twilio
        phone = From.replace("whatsapp:", "").strip()
        message = Body.strip()
        
        # 1. Ejecutamos el agente de forma directa (síncrona para FastAPI)
        respuesta = await handle_message(phone, message)
        
        # 2. Enviamos la respuesta usando el cliente de Twilio
        _send_twilio_whatsapp_message(phone, respuesta)
        
    except Exception as e:
        print(f"Error procesando mensaje en webhook: {e}")
        
    # Le respondemos a Twilio un XML vacío para confirmar recepción
    return Response(content="<Response></Response>", media_type="application/xml")


# === NUEVO ENDPOINT: CHAT CON MEMORIA Y CONFIGURACIÓN DE MAPEO ===
class AdminChatInput(BaseModel):
    text: str
    history: list = []  # <-- Historial para que la IA recuerde aclaraciones previas

@app.post("/api/admin/chat")
async def admin_chat_endpoint(payload: AdminChatInput):
    texto_duena = payload.text
    historial = payload.history
    
    # Inicializamos Groq con temperatura baja para ser precisos
    llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.1)
    
    # Construimos la memoria del chat basada en lo que viene de Streamlit
    contexto_conversacion = ""
    for msg in historial[-5:]:
        rol = "Dueña" if msg["role"] == "user" else "Asistente"
        contexto_conversacion += f"{rol}: {msg['content']}\n"
    
    prompt_sistema = (
        "Eres el asistente de administración de 'Vende tu producción'. Tu tarea es interactuar con la dueña "
        "para configurar la base de datos que acaba de subir o ajustar precios.\n\n"
        "Debes responder de manera muy amable y natural (Ej: 'Listo jefa...'). Puedes resolver dudas o aceptar "
        "aclaraciones si ella te dice que una columna no corresponde.\n\n"
        "HISTORIAL DE LA CONVERSACIÓN:\n"
        f"{contexto_conversacion}\n"
        f"Mensaje actual de la dueña: '{texto_duena}'\n\n"
        "REGLA DE ORO:\n"
        "Si la dueña está de acuerdo, confirma el mapeo o dice que procedas a guardar, debes incluir AL FINAL "
        "de tu respuesta textual la palabra clave EXACTA: COMMAND_IMPORT seguido de un JSON con las llaves 'col_codigo', 'col_nombre' y 'col_precio'.\n"
        "Ejemplo si ella aprueba: '¡Excelente jefa! Procedo a guardar el inventario. COMMAND_IMPORT {\"col_codigo\": \"id_producto\", \"col_nombre\": \"nombre\", \"col_precio\": \"precioVenta_\"}'\n"
        "Si ella solo te está haciendo una pregunta o aclarando una columna, NO agregues el comando, solo respóndele cordialmente."
    )
    
    try:
        respuesta_ia = llm.predict(prompt_sistema)
        
        # Si la IA detecta que la dueña dio el visto bueno, ejecutamos la importación real
        if "COMMAND_IMPORT" in respuesta_ia:
            partes = respuesta_ia.split("COMMAND_IMPORT")
            texto_visible = partes[0].strip()
            json_columnas = json.loads(partes[1].strip())
            
            # Ejecutamos internamente el guardado en Postgres pasándole las columnas elegidas
            importar_datos_finales(json_columnas)
            return {"reply": texto_visible}
            
        return {"reply": respuesta_ia.strip()}
            
    except Exception as e:
        return {"reply": f"⚠️ Tuve un problema procesando tu comando interno: {str(e)}"}


# === NUEVO ENDPOINT: ANALIZAR EXCEL SIN GUARDAR (PASO 1) ===
@app.post("/api/admin/upload-database")
async def upload_database(file: UploadFile = File(...)):
    """
    Recibe cualquier archivo Excel/CSV de cualquier finca, detecta las columnas
    de forma difusa y le pasa los datos al chat para que interactúe con la dueña.
    """
    try:
        contents = await file.read()
        if file.filename.endswith('.xlsx') or file.filename.endswith('.xls'):
            df = pd.read_excel(io.BytesIO(contents))
        elif file.filename.endswith('.csv'):
            df = pd.read_csv(io.BytesIO(contents))
        else:
            return {"status": "error", "message": "Formato no soportado."}
        
        # Guardamos el archivo temporalmente en el contenedor
        temp_path = os.path.join(UPLOAD_DIR, "current_inventory.csv")
        df.to_csv(temp_path, index=False)
        
        columnas_reales = [str(c).strip() for c in df.columns]
        
        # Mapeo difuso inteligente usando sinónimos comunes del campo
        col_codigo = next((c for c in columnas_reales if any(s in c.upper() for s in ["ID", "CODIGO", "COD", "REF", "ITEM"])), "No encontrada")
        col_nombre = next((c for c in columnas_reales if any(s in c.upper() for s in ["NOMBRE", "DESCRIPCION", "PRODUCTO", "DETALLE"])), "No encontrada")
        col_precio = next((c for c in columnas_reales if any(s in c.upper() for s in ["PRECIO", "VALOR", "VENTA", "PRICE", "COSTO"])), "No encontrada")
        
        return {
            "status": "success",
            "columnas": columnas_reales,
            "suposicion": {
                "codigo": col_codigo,
                "nombre": col_nombre,
                "precio": col_precio
            }
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


# === FUNCIÓN INTERNA: GUARDAR EN POSTGRES CUANDO LA IA CONFIRME (PASO 2) ===
def importar_datos_finales(mapeo_columnas):
    db = SessionLocal()
    temp_path = os.path.join(UPLOAD_DIR, "current_inventory.csv")
    if not os.path.exists(temp_path):
        return
    try:
        df = pd.read_csv(temp_path)
        col_id = mapeo_columnas.get("col_codigo")
        col_nom = mapeo_columnas.get("col_nombre")
        col_pre = mapeo_columnas.get("col_precio")
        
        for index, row in df.iterrows():
            nombre = str(row[col_nom]).strip() if col_nom in df.columns else f"Item {index}"
            codigo = int(float(str(row[col_id]).strip())) if col_id in df.columns and not pd.isna(row[col_id]) else index + 1
            
            # Limpiador universal de signos de dinero de campo
            precio_sucio = str(row[col_pre]).replace("$", "").replace(" ", "").replace(".", "").replace(",", "") if col_pre in df.columns else "0"
            precio = float(precio_sucio) if precio_sucio.isdigit() else 0.0
            
            query = text("""
                INSERT INTO products (id, name, price) VALUES (:id, :name, :price)
                ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, price = EXCLUDED.price;
            """)
            db.execute(query, {"id": codigo, "name": nombre, "price": precio})
        db.commit()
    except Exception as e:
        print(f"Error guardando en Postgres: {e}")
        db.rollback()
    finally:
        db.close()


# === ENDPOINTS COMPLEMENTARIOS ===
@app.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
):
    if hub_mode == "subscribe" and hub_verify_token == settings.whatsapp_verify_token:
        return PlainTextResponse(hub_challenge)
    raise HTTPException(status_code=403, detail="Token inválido")


@app.post("/payment/webhook")
async def payment_webhook(request: Request):
    payload = await request.json()
    if payload.get("type") == "payment":
        order_id   = int(payload["data"]["metadata"]["order_id"])
        payment_id = str(payload["data"]["id"])
        from app.db import SessionLocal
        from app.db import crud
        db = SessionLocal()
        try:
            crud.update_order_status(db, order_id, "pagado", payment_id=payment_id)
        finally:
            db.close()
    return {"status": "ok"}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/admin/metrics")
def get_admin_metrics():
    db = SessionLocal()
    try:
        query_top = text("SELECT name, price FROM products ORDER BY price DESC LIMIT 1;")
        res_top = db.execute(query_top).fetchone()
        query_low = text("SELECT name, price FROM products ORDER BY price ASC LIMIT 1;")
        res_low = db.execute(query_low).fetchone()
        
        nombre_top = res_top[0] if res_top else "Papaya"
        delta_top = f"${int(res_top[1]):,}" if res_top else "+15%"
        nombre_low = res_low[0] if res_low else "Café Pergamino"
        delta_low = f"${int(res_low[1]):,}" if res_low else "-5%"
        
        return {
            "mas_vendido": {"nombre": nombre_top, "delta": delta_top},
            "menos_vendido": {"nombre": nombre_low, "delta": delta_low}
        }
    except Exception as e:
        print(f"🚨 Error en SQL Directo: {e}")
        return {
            "mas_vendido": {"nombre": "Base de Datos", "delta": "Conectando..."},
            "menos_vendido": {"nombre": "Escribe una orden", "delta": "en el chat"}
        }
    finally:
        db.close()