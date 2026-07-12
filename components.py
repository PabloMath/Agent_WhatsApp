import streamlit as st
import requests

def enviar_comando_backend(texto_orden):
    st.session_state.messages.append({"role": "user", "content": texto_orden})
    
    # Filtramos el historial para asegurar que solo viajen 'role' y 'content' puros
    historial_limpio = [
        {"role": msg["role"], "content": msg["content"]} 
        for msg in st.session_state.messages[:-1]
    ]
    
    payload = {"text": texto_orden, "history": historial_limpio}
    try:
        response = requests.post("http://localhost:8000/api/admin/chat", json=payload)
        respuesta_ia = response.json().get("reply", "Orden procesada.") if response.status_code == 200 else f"⚠️ Error: {response.text}"
    except Exception:
        respuesta_ia = "🚨 Error de conexión con FastAPI."
    st.session_state.messages.append({"role": "assistant", "content": respuesta_ia})
    st.rerun()

def render_asistente_ventas():
    st.markdown("### Asistente de Administración")
    
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "assistant", "content": "¡Hola, jefa! Soy tu asistente de **Vende tu producción**. ¿Qué precio deseas cambiar o qué base de datos configuramos hoy?"}
        ]

    # --- AQUÍ CORREGIMOS LA ALTURA FIJA PARA QUE NO SE BAJE ---
    caja_estatica_chat = st.container(height=450)
    with caja_estatica_chat:
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])

    st.markdown("⚡ **Accesos rápidos:**")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("📢 Lanzar Promoción"): enviar_comando_backend("Redacta y envía una promoción masiva de papaya a WhatsApp")
    with col2:
        if st.button("📦 Ver Inventario"): enviar_comando_backend("Dame un resumen del stock actual")
    with col3:
        if st.button("📝 Resumen del Día"): enviar_comando_backend("Genera un resumen de las ventas de hoy")

    st.divider()
    
    if prompt := st.chat_input("Escribe una orden, pregunta o aclaración..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        with caja_estatica_chat:
            with st.chat_message("user"): st.write(prompt)
            
        with caja_estatica_chat:
            with st.chat_message("assistant"):
                with st.spinner("Procesando..."):
                    try:
                        # Filtramos también aquí el historial para evitar el KeyError
                        historial_limpio = [
                            {"role": msg["role"], "content": msg["content"]} 
                            for msg in st.session_state.messages[:-1]
                        ]
                        payload = {"text": prompt, "history": historial_limpio}
                        response = requests.post("http://app:8000/api/admin/chat", json=payload)                        
                        respuesta_ia = response.json().get("reply") if response.status_code == 200 else "Error en el servidor."
                    except Exception:
                        respuesta_ia = "Error de conexión."
                    st.write(respuesta_ia)
                    st.session_state.messages.append({"role": "assistant", "content": respuesta_ia})
        st.rerun()


def render_control_almacen():
    st.markdown("### Caja y Control de Almacén")
    st.markdown("Digita el código para buscar el producto e ingresa la cantidad vendida.")
    st.divider()
    
    col_input1, col_input2 = st.columns([1, 1])
    with col_input1:
        codigo_prod = st.text_input("🔢 Código del Producto:", value="58", placeholder="Ej: 58")
        
    with col_input2:
        if codigo_prod == "58":
            producto_nombre = "PAPA PASTUSA"
            precio_por_kg = 3600
            inventario_disponible = "305 Kg"
        elif codigo_prod == "6":
            producto_nombre = "LACTO8000 X 40"
            precio_por_kg = 78986
            inventario_disponible = "12 Unidades"
        else:
            producto_nombre = "PRODUCTO GENERAL"
            precio_por_kg = 2500
            inventario_disponible = "100 Kg"
            
        st.markdown(f"**Detalle:** `{producto_nombre}`")
        st.markdown(f"**Precio base (Kg/Unid):** `${precio_por_kg:,} COP`")
        st.markdown(f"**Inventario Finca:** `{inventario_disponible}`")

    st.divider()
    
    col_cant1, col_cant2 = st.columns([2, 1])
    with col_cant1:
        cantidad_ingresada = st.number_input("⚖️ Cantidad a vender:", min_value=0.0, value=300.0, step=1.0)
    with col_cant2:
        unidad_medida = st.selectbox("📏 Unidad:", ["Gramos (g)", "Libras (lb)", "Kilos (Kg)"])
    
    if unidad_medida == "Gramos (g)":
        factor_conversion = cantidad_ingresada / 1000.0
    elif unidad_medida == "Libras (lb)":
        factor_conversion = cantidad_ingresada * 0.5
    else:
        factor_conversion = cantidad_ingresada
        
    total_calculado = precio_por_kg * factor_conversion
    
    st.markdown("### 💰 VALOR TOTAL A COBRAR:")
    st.markdown(f"<div class='total-gigante'>$ {total_calculado:,.0f} COP</div>", unsafe_allow_html=True)
    
    st.divider()
    if st.button("✅ Confirmar y Despachar Salida", use_container_width=True):
        st.success(f"¡Salida Confirmada! Se despacharon {cantidad_ingresada} {unidad_medida} de {producto_nombre}.")