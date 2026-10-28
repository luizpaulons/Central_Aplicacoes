import streamlit as st

st.set_page_config(
    page_title="Central de Aplicações",
    page_icon="🏢",
    layout="wide"
)

# --- 1. PÁGINA INICIAL DA CENTRAL (Assume o http://localhost:8501/) ---
def home():
    st.title("🏢 Central de Aplicações")
    st.markdown("Selecione uma das ferramentas no menu superior para começar:")
    
    col1, col2 = st.columns(2)
    with col1:
        st.info("### 📊 Financeiro\n**Consulta Cliente:** Consulta de limites, títulos e histórico financeiro.")
    with col2:
        st.info("### 🏭 PCP\n**Estatística de Modelos:** Gerenciamento de solados, EVA e relatórios CHB.")

pagina_home = st.Page(
    home,
    title="Início",
    icon="🏠",
    default=True
)

# --- 2. PÁGINAS DOS MÓDULOS ---
paginas_financeiro = [
    st.Page(
        "financeiro/Consulta_Cliente.py",
        title="Consulta Cliente",
        icon="📊",
        url_path="consulta-cliente"  # http://localhost:8501/consulta-cliente
    )
]

paginas_pcp = [
    st.Page(
        "pcp/Estatistica_Modelos.py",
        title="Estatística de Modelos",
        icon="🏭",
        url_path="estatistica-modelos"  # http://localhost:8501/estatistica-modelos
    )
]

# --- 3. AGRUPAMENTO DOS MENUS ---
rotas = {
    "Central": [pagina_home],
    "Financeiro": paginas_financeiro,
    "PCP": paginas_pcp
}

# --- 4. NAVEGAÇÃO NO TOPO ---
pg = st.navigation(rotas, position="top")
pg.run()