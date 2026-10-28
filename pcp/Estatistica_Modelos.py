import streamlit as st

#st.set_page_config(
#    page_title="Central PCP - Gestão de Solados e EVA",
#    page_icon="🏭",
#    layout="wide"
#)

st.title("🏭 Central PCP - Gestão de Solados e EVA")
st.markdown("---")

st.markdown("""
### Bem-vindo ao sistema de controle e relatórios do PCP!

Utilize o menu na **barra lateral esquerda** para navegar pelas telas do sistema:

1. **📝 De-Para**: Faça o vínculo das referências e cores ativas do banco ERP com os solados e cores de EVA.
2. **⚙️ Cadastro de Solados e Cores**: Cadastre novos solados e consulte as cores oficiais diretamente da tabela `PC10T`.
3. **📑 Importar Excel e Gerar Relatório**: Carregue o arquivo `.xlsx` do ERP CHB para gerar os relatórios consolidados em PDF e Excel.
""")

# Estilo global para manter campos de texto em caixa alta
st.markdown("""
<style>
    input[type="text"] {
        text-transform: uppercase !important;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================================
# MENU LATERAL ESQUERDO DO MÓDULO PCP
# ==========================================================
st.sidebar.title("🏭 PCP - Solados e EVA")
st.sidebar.markdown("---")

submenu_pcp = st.sidebar.radio(
    "Navegação PCP:",
    [
        "📝 De-Para",
        "⚙️ Cadastro de Solados e Cores",
        "📑 Importar Relatório CHB"
    ]
)
st.sidebar.markdown("---")
st.sidebar.caption("Central de Controle PCP / CHB")

# ==========================================================
# CARREGAMENTO DINÂMICO DAS TELAS
# ==========================================================
# Procura os arquivos na raiz do app ou na pasta pages/
def obter_caminho_arquivo(nome_arquivo):
    locais_possiveis = [
        nome_arquivo,
        os.path.join("pages", nome_arquivo),
        os.path.join("pcp", nome_arquivo)
    ]
    for caminho in locais_possiveis:
        if os.path.exists(caminho):
            return caminho
    return nome_arquivo

if submenu_pcp == "📝 De-Para":
    caminho = obter_caminho_arquivo("de-para.py")
    if os.path.exists(caminho):
        with open(caminho, "r", encoding="utf-8") as f:
            exec(f.read(), globals())
    else:
        st.error(f"Arquivo '{caminho}' não encontrado.")

elif submenu_pcp == "⚙️ Cadastro de Solados e Cores":
    caminho = obter_caminho_arquivo("cadastro_solados.py")
    if os.path.exists(caminho):
        with open(caminho, "r", encoding="utf-8") as f:
            exec(f.read(), globals())
    else:
        st.error(f"Arquivo '{caminho}' não encontrado.")

elif submenu_pcp == "📑 Importar Relatório CHB":
    caminho = obter_caminho_arquivo("importador.py")
    if os.path.exists(caminho):
        with open(caminho, "r", encoding="utf-8") as f:
            exec(f.read(), globals())
    else:
        st.error(f"Arquivo '{caminho}' não encontrado.")