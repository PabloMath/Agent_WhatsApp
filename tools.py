"""
Tools del agente de ventas.
Cada función está decorada con @tool para que LangChain la exponga al LLM.
"""

import json
import os
from typing import Optional

import redis as redis_lib
from langchain.tools import tool

from app.config import settings
from app.db import SessionLocal
from app.db import crud

redis = redis_lib.from_url(settings.redis_url, decode_responses=True)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _cart_key(phone: str) -> str:
    return f"cart:{phone}"


# ─── Catálogo ────────────────────────────────────────────────────────────────

@tool
def buscar_producto(query: str, categoria: Optional[str] = None, precio_max: Optional[float] = None) -> str:
    """
    Busca productos en el catálogo por nombre o descripción.
    Úsala cuando el usuario pregunte por productos, precios o disponibilidad.
    """
    db = SessionLocal()
    try:
        productos = crud.search_products(db, query, categoria, precio_max)
        if not productos:
            return f"No encontré productos para '{query}'. Intenta con otro término."

        resultado = f"Encontré {len(productos)} producto(s):\n\n"
        for p in productos:
            resultado += f"• *{p.name}* — ${p.price:,.0f}\n  {(p.description or '')[:80]}...\n  ID: {p.id}\n\n"
        return resultado
    finally:
        db.close()


@tool
def ver_detalle_producto(product_id: int) -> str:
    """
    Retorna descripción completa, precio, stock e imagen de un producto.
    Úsala cuando el usuario pida más información sobre un producto.
    """
    db = SessionLocal()
    try:
        p = crud.get_product(db, product_id)
        if not p:
            return f"No encontré el producto con ID {product_id}."
        return (
            f"*{p.name}*\n"
            f"Precio: ${p.price:,.0f}\n"
            f"Stock: {p.stock} unidades\n"
            f"Categoría: {p.category}\n\n"
            f"{p.description}\n\n"
            f"Imagen: {p.image_url or 'no disponible'}"
        )
    finally:
        db.close()


# ─── Carrito ─────────────────────────────────────────────────────────────────

@tool
def agregar_al_carrito(phone: str, product_id: int, cantidad: int = 1) -> str:
    """
    Agrega uno o varios productos al carrito del usuario en Redis.
    Úsala cuando el usuario quiera comprar o agregar algo al pedido.
    """
    key = _cart_key(phone)
    cart = json.loads(redis.get(key) or "{}")
    cart[str(product_id)] = cart.get(str(product_id), 0) + cantidad
    redis.setex(key, 7200, json.dumps(cart))
    total_items = sum(cart.values())
    return f"Agregado al carrito. Tienes {total_items} item(s). ¿Deseas seguir comprando o proceder al pago?"


@tool
def ver_carrito(phone: str) -> str:
    """
    Muestra los productos en el carrito con cantidades y subtotales.
    Úsala cuando el usuario quiera revisar su pedido antes de pagar.
    """
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
    """
    Elimina un producto específico del carrito del usuario.
    Úsala cuando el usuario quiera quitar un producto de su pedido.
    """
    key = _cart_key(phone)
    cart = json.loads(redis.get(key) or "{}")
    cart.pop(str(product_id), None)
    redis.setex(key, 7200, json.dumps(cart))
    return "Producto eliminado del carrito."


@tool
def limpiar_carrito(phone: str) -> str:
    """
    Vacía completamente el carrito. Úsala solo si el usuario confirma cancelar la compra.
    """
    redis.delete(_cart_key(phone))
    return "Carrito vaciado."


# ─── Pedidos ─────────────────────────────────────────────────────────────────

@tool
def crear_pedido(phone: str, direccion_entrega: str) -> str:
    """
    Convierte el carrito en un pedido formal guardado en PostgreSQL.
    Úsala cuando el usuario confirme la compra y proporcione dirección de entrega.
    """
    cart = json.loads(redis.get(_cart_key(phone)) or "{}")
    if not cart:
        return "Tu carrito está vacío. Agrega productos antes de crear el pedido."

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
                subtotal = p.price * qty
                total += subtotal
                items.append({"product_id": p.id, "name": p.name, "qty": qty, "price": p.price})
                crud.decrement_stock(db, p.id, qty)

        order = crud.create_order(db, user.id, items, total, direccion_entrega)
        redis.delete(_cart_key(phone))

        return (
            f"Pedido #{order.id} creado.\n"
            f"Total: ${total:,.0f}\n"
            f"Entrega en: {direccion_entrega}\n\n"
            "¿Deseas que te envíe el link de pago?"
        )
    finally:
        db.close()


@tool
def consultar_pedido(order_id: int) -> str:
    """
    Retorna el estado actual de un pedido.
    Úsala cuando el usuario pregunte por el estado de su compra.
    """
    db = SessionLocal()
    try:
        order = crud.get_order(db, order_id)
        if not order:
            return f"No encontré el pedido #{order_id}."
        estados = {
            "pendiente_pago": "Esperando pago",
            "pagado":         "Pago recibido, preparando envío",
            "en_camino":      "En camino",
            "entregado":      "Entregado",
            "cancelado":      "Cancelado",
        }
        return (
            f"Pedido #{order.id}\n"
            f"Estado: {estados.get(order.status, order.status)}\n"
            f"Total: ${order.total:,.0f}\n"
            f"Dirección: {order.delivery_address}"
        )
    finally:
        db.close()


# ─── Pagos ───────────────────────────────────────────────────────────────────

@tool
def generar_link_pago(order_id: int) -> str:
    """
    Genera un link de pago seguro con Stripe para el pedido indicado.
    Úsala cuando el usuario esté listo para pagar.
    """
    import stripe
    stripe.api_key = settings.stripe_secret_key

    db = SessionLocal()
    try:
        order = crud.get_order(db, order_id)
        if not order:
            return f"No encontré el pedido #{order_id}."

        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "cop",
                    "product_data": {"name": f"Pedido #{order_id}"},
                    "unit_amount": int(order.total * 100),
                },
                "quantity": 1,
            }],
            mode="payment",
            success_url=f"{settings.base_url}/payment/success?order={order_id}",
            cancel_url=f"{settings.base_url}/payment/cancel?order={order_id}",
            metadata={"order_id": str(order_id)},
        )
        return f"Aquí está tu link de pago (válido 30 min):\n{session.url}"
    finally:
        db.close()


@tool
def verificar_pago(order_id: int) -> str:
    """
    Verifica si un pedido ya fue pagado.
    Úsala cuando el usuario diga que ya realizó el pago.
    """
    db = SessionLocal()
    try:
        order = crud.get_order(db, order_id)
        if not order:
            return f"No encontré el pedido #{order_id}."
        if order.status == "pagado":
            return f"Pago confirmado para el pedido #{order_id}. Pronto recibirás tu envío."
        return f"Aún no registramos el pago del pedido #{order_id}. ¿Necesitas un nuevo link?"
    finally:
        db.close()


# ─── Usuario ─────────────────────────────────────────────────────────────────

@tool
def obtener_perfil(phone: str) -> str:
    """
    Retorna el nombre, dirección e historial de compras del usuario.
    Úsala al inicio de la conversación para personalizar el saludo.
    """
    db = SessionLocal()
    try:
        user = crud.get_user_by_phone(db, phone)
        if not user:
            return "Usuario nuevo. Pregúntale su nombre para registrarlo."

        pedidos = crud.get_user_orders(db, user.id, limit=3)
        historial = "\n".join([f"  Pedido #{o.id} — ${o.total:,.0f} ({o.status})" for o in pedidos])
        return (
            f"Hola, {user.name}!\n"
            f"Dirección: {user.default_address or 'no guardada'}\n"
            f"Últimas compras:\n{historial or '  (ninguna aún)'}"
        )
    finally:
        db.close()


@tool
def registrar_usuario(phone: str, nombre: str) -> str:
    """
    Crea un nuevo usuario con su número de WhatsApp y nombre.
    Úsala cuando el usuario sea nuevo y proporcione su nombre.
    """
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
    """
    Guarda o actualiza la dirección de entrega del usuario.
    Úsala cuando el usuario proporcione su dirección.
    """
    db = SessionLocal()
    try:
        crud.update_address(db, phone, direccion)
        return f"Dirección guardada: {direccion}"
    finally:
        db.close()


# ─── Lista exportable ────────────────────────────────────────────────────────

ALL_TOOLS = [
    buscar_producto,
    ver_detalle_producto,
    agregar_al_carrito,
    ver_carrito,
    eliminar_del_carrito,
    limpiar_carrito,
    crear_pedido,
    consultar_pedido,
    generar_link_pago,
    verificar_pago,
    obtener_perfil,
    registrar_usuario,
    guardar_direccion,
]
