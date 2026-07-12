from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_groq import ChatGroq
from app.config import settings
from app.agent.tools import ALL_TOOLS
from app.agent.memory import get_memory

SYSTEM_PROMPT = """Eres un asistente de ventas por WhatsApp para una tienda de eCommerce agrícola.
Tu objetivo es ayudar a los clientes a encontrar productos, gestionar su carrito y completar compras.

Reglas:
- Al iniciar, usa `obtener_perfil` para saludar al usuario por su nombre.
- Si el usuario es nuevo, regístralo con `registrar_usuario` antes de continuar.
- Habla de forma amigable y breve — estás en WhatsApp, no en un email.
- Nunca inventes precios ni disponibilidad; siempre consulta las tools.
- Antes de crear un pedido, confirma el carrito y la dirección de entrega.
- Cuando el usuario quiera pagar, genera el link de inmediato.

Número de WhatsApp del usuario: {phone}
Idioma: español.
"""

def build_agent(phone: str) -> AgentExecutor:
    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=0.2,
        api_key=settings.groq_api_key,
    )
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT.format(phone=phone)),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])
    agent = create_openai_tools_agent(llm=llm, tools=ALL_TOOLS, prompt=prompt)
    return AgentExecutor(
        agent=agent,
        tools=ALL_TOOLS,
        memory=get_memory(phone),
        verbose=True,
        max_iterations=6,
        handle_parsing_errors=True,
    )

_cache: dict[str, AgentExecutor] = {}

def get_agent(phone: str) -> AgentExecutor:
    if phone not in _cache:
        _cache[phone] = build_agent(phone)
    return _cache[phone]

async def handle_message(phone: str, message: str) -> str:
    agent = get_agent(phone)
    result = await agent.ainvoke({"input": message})
    return result["output"]
