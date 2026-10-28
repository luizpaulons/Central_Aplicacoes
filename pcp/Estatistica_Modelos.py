import os
import streamlit as st

st.warning(f"Arquivos e pastas em /app: {os.listdir('/app')}")
if os.path.exists("/app/pcp"):
    st.info(f"Arquivos dentro de /app/pcp: {os.listdir('/app/pcp')}")