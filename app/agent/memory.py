from langchain.memory import ConversationBufferWindowMemory
from langchain_community.chat_message_histories import RedisChatMessageHistory
from app.config import settings


def get_memory(phone: str, k: int = 10) -> ConversationBufferWindowMemory:
    history = RedisChatMessageHistory(
        session_id=f"whatsapp:{phone}",
        url=settings.redis_url,
        ttl=86400,
    )
    return ConversationBufferWindowMemory(
        k=k,
        chat_memory=history,
        memory_key="chat_history",
        return_messages=True,
    )

def clear_memory(phone: str) -> None:
    history = RedisChatMessageHistory(
        session_id=f"whatsapp:{phone}",
        url=settings.redis_url,
    )
    history.clear()
