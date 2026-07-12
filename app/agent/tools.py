import json
from typing import Optional
import redis as redis_lib
from langchain.tools import tool
from app.config import settings
from app.db import SessionLocal
from app.db import crud

redis = redis_lib.from_url(settings.redis_url, decode_responses=True)

def _cart_key(phone: str) -> str:
    return f"cart:{phone}"

@tool
def buscar_producto(query: str, categoria: Optional[str] = None, precio_max: Optional[float] = None) -> str:
    """Busca productos en el catálogo. Úsala cuando el usuario pregunte por productos o precios."""
    db = SessionLocal()
    try:
        productos = crud.search_products(db, query, categoria, precio_max)
        if not productos:
            return f"No encontré productos para '{query}'."
        resultado = f"Encontré {len(productos)} producto(s):\n\n"
        for p in productos:
            resultado += f"• *{p.name}* — ${p.price:,.0f}\n  {(p.description or '')[:80]}...\n  ID: {p.id}\n\n"
        return resultado
    finally:
        db.close()

@tool
def ver_detalle_producto(product_id: int) -> str:
    """Retorna descripción completa, precio y stock de un producto."""
    db = SessionLocal()
    try:
        p = crud.get_product(db, product_id)
        if not p:
            return f"No encontré el producto con ID {product_id}."
        return f"*{p.name}*\nPrecio: ${p.price:,.0f}\nStock: {p.stock}\nCategoría: {p.category}\n\n{p.description}"
    finally:
        db.close()

@tool
def agregar_al_carrito(phone: str, product_id: int, cantidad: int = 1) -> str:
    """Agrega productos al carrito del usuario en Redis."""
    key = _cart_key(phone)
    cart = json.loads(redis.get(key) or "{}")
    cart[str(product_id)] = cart.get(str(product_id), 0) + cantidad
    redis.setex(key, 7200, json.dumps(cart))
    return f"Agregado. Tienes {sum(cart.values())} item(s) en el carrito."

@tool
def ver_carrito(phone: str) -> str:
    """Muestra los productos en el carrito con subtotales."""
    cart = json.loads(redis.get(_cart_key(phone)) or "{}")
    if not cart:
        return "Tu carrito está vacío."
    db = SessionLocal()
    try:
        total = 0
        resumen = "Tu carrito:\n\n"
        for pid, qty in cart.items():
            p = crud.get_product(db, int(pid))
            if p:
                sub = p.price * qty
                total += sub
                resumen += f"• {p.name} x{qty} — ${sub:,.0f}\n"
        resumen += f"\nTotal: ${total:,.0f}"
        return resumen
    finally:
        db.close()

@tool
def eliminar_del_carrito(phone: str, product_id: int) -> str:
    """Elimina un producto del carrito."""
    key = _cart_key(phone)
    cart = json.loads(redis.get(key) or "{}")
    cart.pop(str(product_id), None)
    redis.setex(key, 7200, json.dumps(cart))
    return "Producto eliminado del carrito."

@tool
def limpiar_carrito(phone: str) -> str:
    """Vacía el carrito completamente."""
    redis.delete(_cart_key(phone))
    return "Carrito vaciado."

@tool
def crear_pedido(phone: str, direccion_entrega: str) -> str:
    """Convierte el carrito en un pedido en PostgreSQL."""
    cart = json.loads(redis.get(_cart_key(phone)) or "{}")
    if not cart:
        return "Tu carrito está vacío."
    db = SessionLocal()
    try:
        user = crud.get_user_by_phone(db, phone)
        if not user:
            return "No encontré tu perfil. Dime tu nombre para registrarte."
        total = 0
        items = []
        for pid, qty in cart.items():
            p = crud.get_product(db, int(pid))
            if p:
                sub = p.price * qty
                total += sub
                items.append({"product_id": p.id, "name": p.name, "qty": qty, "price": p.price})
                crud.decrement_stock(db, p.id, qty)
        order = crud.create_order(db, user.id, items, total, direccion_entrega)
        redis.delete(_cart_key(phone))
        return f"Pedido #{order.id} creado.\nTotal: ${total:,.0f}\nEntrega en: {direccion_entrega}\n\n¿Deseas el link de pago?"
    finally:
        db.close()

@tool
def consultar_pedido(order_id: int) -> str:
    """Retorna el estado de un pedido."""
    db = SessionLocal()
    try:
        order = crud.get_order(db, order_id)
        if not order:
            return f"No encontré el pedido #{order_id}."
        estados = {"pendiente_pago": "Esperando pago", "pagado": "Pago recibido", "en_camino": "En camino", "entregado": "Entregado"}
        return f"Pedido #{order.id}\nEstado: {estados.get(order.status, order.status)}\nTotal: ${order.total:,.0f}"
    finally:
        db.close()

@tool
def generar_link_pago(order_id: int) -> str:
    """Genera un link de pago con Mercado Pago."""
    import mercadopago
    sdk = mercadopago.SDK(settings.mp_access_token)
    db = SessionLocal()
    try:
        order = crud.get_order(db, order_id)
        if not order:
            return f"No encontré el pedido #{order_id}."
        preference_data = {
            "items": [{"title": f"Pedido #{order_id}", "quantity": 1, "unit_price": order.total}],
            "back_urls": {
                "success": f"{settings.base_url}/payment/success?order={order_id}",
                "failure": f"{settings.base_url}/payment/cancel?order={order_id}",
            },
            "auto_return": "approved",
            "external_reference": str(order_id),
        }
        preference_response = sdk.preference().create(preference_data)
        link = preference_response["response"]["init_point"]
        return f"Aquí está tu link de pago:\n{link}"
    finally:
        db.close()

@tool
def obtener_perfil(phone: str) -> str:
    """Retorna nombre, dirección e historial del usuario."""
    db = SessionLocal()
    try:
        user = crud.get_user_by_phone(db, phone)
        if not user:
            return "Usuario nuevo. Pregúntale su nombre para registrarlo."
        pedidos = crud.get_user_orders(db, user.id, limit=3)
        historial = "\n".join([f"  Pedido #{o.id} — ${o.total:,.0f} ({o.status})" for o in pedidos])
        return f"Hola, {user.name}!\nDirección: {user.default_address or 'no guardada'}\nÚltimas compras:\n{historial or '  (ninguna aún)'}"
    finally:
        db.close()

@tool
def registrar_usuario(phone: str, nombre: str) -> str:
    """Crea un nuevo usuario con su número de WhatsApp."""
    db = SessionLocal()
    try:
        existe = crud.get_user_by_phone(db, phone)
        if existe:
            return f"Ya estás registrado como {existe.name}."
        crud.create_user(db, phone, nombre)
        return f"Bienvenido, {nombre}! Tu cuenta ha sido creada."
    finally:
        db.close()

@tool
def guardar_direccion(phone: str, direccion: str) -> str:
    """Guarda la dirección de entrega del usuario."""
    db = SessionLocal()
    try:
        crud.update_address(db, phone, direccion)
        return f"Dirección guardada: {direccion}"
    finally:
        db.close()

ALL_TOOLS = [
    buscar_producto, ver_detalle_producto,
    agregar_al_carrito, ver_carrito, eliminar_del_carrito, limpiar_carrito,
    crear_pedido, consultar_pedido, generar_link_pago,
    obtener_perfil, registrar_usuario, guardar_direccion,
]
