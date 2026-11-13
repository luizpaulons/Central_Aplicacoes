import streamlit as st

st.set_page_config(page_title="Central de Aplicações", page_icon="🏢", layout="wide")


# --- 1. PÁGINA INICIAL DA CENTRAL ---
def home():
    st.title("🏢 Central de Aplicações")
    st.markdown("Selecione uma das ferramentas no menu superior para começar:")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.info(
            "### 📊 Financeiro\n**Consulta Cliente:** Consulta de limites, títulos e histórico financeiro."
        )
    with col2:
        st.info(
            "### 🏭 PCP\n**Estatística de Modelos:** Gerenciamento de solados, EVA e relatórios CHB."
        )
    with col3:
        st.info(
            "### 🛒 Compras\n**Liberação de Produtos:** Manutenção em lote de preços, custos e desbloqueio (`CO13T`)."
        )


pagina_home = st.Page(home, title="Início", icon="🏠", default=True)

# --- 2. PÁGINAS DO MÓDULO FINANCEIRO ---
paginas_financeiro = [
    st.Page(
        "financeiro/Consulta_Cliente.py",
        title="Consulta Cliente",
        icon="📊",
        url_path="consulta-cliente",
    ),
    st.Page(
        "financeiro/conciliador_cartao/Conciliador_Fatura.py",
        title="Conciliador de Fatura",
        icon="🏭",
        url_path="conciliador-fatura",
        # visibility="hidden",
    ),
]

# --- 3. PÁGINAS DO MÓDULO PCP ---
paginas_pcp = [
    st.Page(
        "pcp/estatistica_modelos/Estatistica_Modelos.py",
        title="Estatística de Modelos",
        icon="🏭",
        url_path="pcp-estatistica",
    ),
    st.Page(
        "pcp/planos_elaboracao/planos_elaboracao.py",
        title="Planos em Elaboração",
        icon="🏭",
        url_path="planos-elaboracao",
        # visibility="hidden",
    ),
]

# --- 4. PÁGINAS DO MÓDULO COMPRAS ---
paginas_compras = [
    st.Page(
        "compras/liberacao_produtos/liberacao_produtos.py",
        title="Liberação de Produtos",
        icon="📦",
        url_path="liberacao-produtos",
        visibility="hidden",
    ),
]

# --- 5. AGRUPAMENTO DOS MENUS ---
rotas = {
    "Central": [pagina_home],
    "Financeiro": paginas_financeiro,
    "PCP": paginas_pcp,
    "Compras": paginas_compras,
}

# --- 6. NAVEGAÇÃO NO TOPO ---
pg = st.navigation(rotas, position="top")
pg.run()
