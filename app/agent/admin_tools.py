# ... Tus imports anteriores ...
from app.agent.admin_tools import actualizar_precio_producto
from langchain_groq import ChatGroq
import json

# Definimos el esquema de entrada del chat administrativo
class AdminChatInput(BaseModel):
    text: str

@app.post("/api/admin/chat")
async def admin_chat_endpoint(payload: AdminChatInput):
    texto_duena = payload.text
    
    # Inicializamos Groq rápido para interpretar la orden estructuradamente
    # Le damos un sistema de instrucciones estricto para que actúe como extractor JSON
    llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.0)
    
    prompt_sistema = (
        "Eres el backend de un sistema agrícola. Tu única tarea es analizar la orden de la dueña y extraer "
        "si quiere actualizar o crear un precio. Debes responder ÚNICAMENTE con un objeto JSON plano que tenga "
        "las llaves: 'producto' (string o null) y 'precio' (number o null). "
        "Ejemplo de entrada: 'Pon la papaya a 3000 pesos' -> Respuesta: {\"producto\": \"papaya\", \"precio\": 3000}. "
        f"Orden de la dueña: '{texto_duena}'"
    )
    
    try:
        # La IA analiza el texto libre de la dueña
        respuesta_ia = llm.predict(prompt_sistema)
        # Limpiamos posibles espacios o caracteres raros y parseamos a diccionario de Python
        datos_extraidos = json.loads(respuesta_ia.strip())
        
        producto = datos_extraidos.get("producto")
        precio = datos_extraidos.get("precio")
        
        # Si la IA logró extraer un producto y un precio, ejecutamos la actualización en la DB
        if producto and precio:
            resultado_db = actualizar_precio_producto(producto, float(precio))
            return {"reply": f"🤖 Entendido, jefa. {resultado_db}"}
        else:
            return {"reply": "🤖 Recibí tu mensaje, pero no logré identificar con claridad qué producto o qué precio deseas cambiar. ¿Podrías ser un poco más específica? (Ej: 'Actualiza el aguacate a 5000')"}
            
    except Exception as e:
        # Si algo falla con la IA o el JSON, devolvemos un mensaje seguro
        return {"reply": f"⚠️ Lo siento, tuve un problema procesando tu comando interno: {str(e)}"}