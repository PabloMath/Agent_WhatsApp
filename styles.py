import streamlit as st
import base64

def set_background_image(uploaded_file):
    if uploaded_file is not None:
        bytes_data = uploaded_file.read()
        b64_encoded = base64.b64encode(bytes_data).decode()
        style = f"""
        <style>
        [data-testid="stAppViewContainer"], [data-testid="stHeader"], .stApp {{
            background-image: linear-gradient(rgba(15, 20, 17, 0.88), rgba(15, 20, 17, 0.88)), url("data:image/png;base64,{b64_encoded}");
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
        }}
        [data-testid="stSidebar"] {{
            background-image: linear-gradient(rgba(20, 28, 24, 0.92), rgba(20, 28, 24, 0.92)), url("data:image/png;base64,{b64_encoded}");
            background-size: cover;
        }}
        </style>
        """
        st.markdown(style, unsafe_allow_html=True)

def inject_premium_css():
    css = """
    <style>
        .block-container {
            padding-top: 2rem !important;
            padding-bottom: 2rem !important;
            max-width: 730px !important;
        }

        /* CENTRADO DE PESTAÑAS (TABS) */
        [data-testid="stTabBlock"] {
            display: flex !important;
            justify-content: center !important;
            margin-top: 0rem !important;
            margin-bottom: 30px !important;
            border-bottom: 1px solid #223028 !important;
        }
        
        [data-testid="stTabBlock"] div[data-baseweb="tab-list"] {
            gap: 20px !important;
        }

        [data-testid="stTabContent"] {
            background-color: transparent !important;
            border: none !important;
            padding: 0px !important;
            box-shadow: none !important;
        }
        
        button[data-baseweb="tab"] {
            font-size: 18px !important;
            color: #b3cbb7 !important;
            background: transparent !important;
            border: none !important;
            padding: 12px 20px !important;
        }
        button[data-baseweb="tab"][aria-selected="true"] {
            color: #76a786 !important;
            font-weight: bold !important;
            border-bottom: 3px solid #76a786 !important;
        }

        [data-testid="stAppViewContainer"], [data-testid="stHeader"], .stApp {
            background-color: #0f1411 !important;
            color: #e3ebd5 !important;
        }
        [data-testid="stSidebar"] {
            background-color: #141c18 !important;
            border-right: 1px solid #223028;
        }
        .stChatMessage {
            font-size: 18px !important;
            background-color: #1a241f !important;
            border-radius: 12px;
            border: 1px solid #28382f;
            margin-bottom: 14px;
            padding: 15px !important;
        }
        .stChatInput textarea {
            font-size: 18px !important;
            background-color: #1c2621 !important;
            color: #e3ebd5 !important;
            border: 1px solid #34473c !important;
        }
        h2, h3, h4 {
            color: #76a786 !important;
            font-family: 'Segoe UI', Roboto, sans-serif;
        }
        p, span, li, label {
            font-size: 17px !important;
        }
        [data-testid="stMetricValue"] {
            font-size: 24px !important;
            color: #ffffff !important;
        }
        .stButton>button {
            background-color: #1c2621 !important;
            color: #76a786 !important;
            border: 1px solid #34473c !important;
            border-radius: 8px !important;
        }
        .total-gigante {
            font-size: 54px !important;
            font-weight: bold;
            color: #76a786 !important;
            background-color: #141c18;
            padding: 20px;
            border-radius: 10px;
            border: 2px solid #28382f;
            text-align: center;
            font-family: 'Courier New', monospace;
        }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)