import streamlit as st
import requests
# Importamos nuestros módulos locales
from styles import inject_premium_css, set_background_image
from components import render_asistente_ventas, render_control_almacen

# Configuración inicial de la página
st.set_page_config(
    page_title="Vende tu producción - Panel", 
    page_icon="🚜", 
    layout="centered"
)

# Inyectar estilos limpios desde styles.py
inject_premium_css()

# --- PANEL LATERAL IZQUIERDO (SIDEBAR) ---
with st.sidebar:
    st.markdown("<h3 style='text-align: center;'>🚜 Vende tu producción</h3>", unsafe_allow_html=True)
    st.markdown("**Finca:** Central Agro Tolima")
    st.divider()
    
    st.markdown("💾 **Cargar Base de Datos**")
    archivo_inventario = st.file_uploader("Sube tu lista (.xlsx o .csv)", type=["xlsx", "csv"], key="inventario_uploader", label_visibility="collapsed")
    
    # === PASO 4: INTERFAZ DE ANALIZADOR INTERACTIVO ===
    if archivo_inventario is not None:
        if st.button("🚀 Analizar Inventario", use_container_width=True):
            with st.spinner("Analizando estructura..."):
                files = {"file": (archivo_inventario.name, archivo_inventario.getvalue(), archivo_inventario.type)}
                try:
                    response = requests.post("http://app:8000/api/admin/upload-database", files=files)
                    if response.status_code == 200:
                        res = response.json()
                        if res.get("status") == "success":
                            suposicion = res["suposicion"]
                            columnas = res["columnas"]
                            
                            # Construimos el mensaje inicial que la IA pondrá en el chat central
                            mensaje_ia = (
                                f"🤖 Jefa, acabo de escanear el archivo que subió. Detecté estas columnas: `{columnas}`.\n\n"
                                f"Mi suposición inteligente para configurar el sistema es:\n"
                                f"* **Código:** `{suposicion['codigo']}`\n"
                                f"* **Producto:** `{suposicion['nombre']}`\n"
                                f"* **Precio:** `{suposicion['precio']}`\n\n"
                                f"¿Me confirma si los datos son correctos para guardarlos en el almacén o prefiere que aclaremos alguna columna?"
                            )
                            
                            # Inyectamos el mensaje directamente en el historial del chat de Streamlit
                            if "messages" not in st.session_state:
                                st.session_state.messages = []
                            st.session_state.messages.append({"role": "assistant", "content": mensaje_ia})
                            st.rerun()
                        else:
                            st.error(res.get("message", "Error analizando el archivo."))
                    else:
                        st.error("⚠️ Error de comunicación con el backend.")
                except Exception:
                    st.error("🚨 No se pudo conectar con el servidor.")
                    
    st.divider()
    st.markdown("🎨 **Imagen de Fondo**")
    imagen_fondo = st.file_uploader("Cambiar fondo", type=["png", "jpg", "jpeg"], key="fondo_uploader", label_visibility="collapsed")
    if imagen_fondo:
        set_background_image(imagen_fondo)


# =========================================================
# --- ESTRUCTURA DE PESTAÑAS (TABS) ---
# =========================================================
tab_ventas, tab_almacen = st.tabs(["🤖 Asistente de Ventas", "📦 Control de Almacén"])

# Renderizar pestaña 1 usando components.py
with tab_ventas:
    render_asistente_ventas()

# Renderizar pestaña 2 usando components.py
with tab_almacen:
    render_control_almacen()