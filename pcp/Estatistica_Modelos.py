import os
import streamlit as st

# Mostra onde o Streamlit está sendo executado e o que tem na pasta
diretorio_atual = os.getcwd()
st.info(f"📁 Diretório de execução atual: `{diretorio_atual}`")

if os.path.exists("pages"):
    st.write("Conteúdo da pasta `pages/` encontrada:", os.listdir("pages"))
else:
    st.warning("⚠️ A pasta `pages` NÃO foi encontrada no diretório raiz atual.")