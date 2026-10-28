import streamlit as st
import os

# ==========================================================
# MENU LATERAL ESQUERDO (SIDEBAR)
# ==========================================================
st.sidebar.title("🏭 Estatística de Modelos")
st.sidebar.markdown("---")

menu_selecionado = st.sidebar.radio(
    "Navegação:",
    [
        "📝 De-Para",
        "⚙️ Cadastro de Solados e Cores",
        "📑 Importar Relatório CHB"
    ]
)
st.sidebar.markdown("---")
st.sidebar.caption("PCP - Gestão de Solados e EVA")

# ==========================================================
# RESOLUÇÃO DE CAMINHOS DOS SUBMÓDULOS
# ==========================================================
def carregar_script(nome_arquivo):
    locais_possiveis = [
        os.path.join("pages", nome_arquivo),
        nome_arquivo,
        os.path.join("pcp", nome_arquivo)
    ]
    for caminho in locais_possiveis:
        if os.path.exists(caminho):
            with open(caminho, "r", encoding="utf-8") as f:
                exec(f.read(), globals())
            return
    st.error(f"Arquivo '{nome_arquivo}' não foi encontrado em 'pages/'.")

# ==========================================================
# RENDERIZAÇÃO DA PÁGINA ESCOLHIDA
# ==========================================================
if menu_selecionado == "📝 De-Para":
    carregar_script("de-para.py")

elif menu_selecionado == "⚙️ Cadastro de Solados e Cores":
    carregar_script("cadastro_solados.py")

elif menu_selecionado == "📑 Importar Relatório CHB":
    carregar_script("importador.py")