from sqlalchemy.orm import Session
from typing import Optional, List  # Agregamos List para tipado limpio
from app.db.models import Order, Product, User


def get_user_by_phone(db: Session, phone: str) -> Optional[User]:
    return db.query(User).filter(User.phone == phone).first()

def create_user(db: Session, phone: str, name: str) -> User:
    user = User(phone=phone, name=name)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def update_address(db: Session, phone: str, address: str) -> Optional[User]:
    user = get_user_by_phone(db, phone)
    if user:
        user.default_address = address
        db.commit()
    return user

# Corregidos los parámetros de category y max_price
def search_products(db: Session, query: str, category: Optional[str] = None, max_price: Optional[float] = None, limit: int = 5) -> List[Product]:
    q = db.query(Product).filter(Product.name.ilike(f"%{query}%"), Product.stock > 0)
    if category:
        q = q.filter(Product.category == category)
    if max_price:
        q = q.filter(Product.price <= max_price)
    return q.limit(limit).all()

# Corregido el retorno a Optional[Product]
def get_product(db: Session, product_id: int) -> Optional[Product]:
    return db.query(Product).filter(Product.id == product_id).first()

def decrement_stock(db: Session, product_id: int, qty: int) -> None:
    product = get_product(db, product_id)
    if product:
        product.stock = max(0, product.stock - qty)
        db.commit()

def create_order(db: Session, user_id: int, items: list[dict], total: float, address: str) -> Order:
    order = Order(user_id=user_id, items=items, total=total, delivery_address=address, status="pendiente_pago")
    db.add(order)
    db.commit()
    db.refresh(order)
    return order

# Corregido el retorno a Optional[Order]
def get_order(db: Session, order_id: int) -> Optional[Order]:
    return db.query(Order).filter(Order.id == order_id).first()

def get_user_orders(db: Session, user_id: int, limit: int = 5) -> List[Order]:
    return db.query(Order).filter(Order.user_id == user_id).order_by(Order.created_at.desc()).limit(limit).all()

# Corregidos tanto el parámetro payment_id como el retorno de la función
def update_order_status(db: Session, order_id: int, status: str, payment_id: Optional[str] = None) -> Optional[Order]:
    order = get_order(db, order_id)
    if order:
        order.status = status
        if payment_id:
            order.payment_id = payment_id
        db.commit()
    return order