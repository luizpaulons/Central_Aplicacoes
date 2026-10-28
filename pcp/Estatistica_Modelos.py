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

# ==========================================================
# MENU LATERAL ESQUERDO DO PCP
# ==========================================================
#st.sidebar.title("🏭 Módulo PCP")
#st.sidebar.markdown("---")

menu_selecionado = st.sidebar.radio(
    "Navegação Interna:",
    [
        "📝 De-Para",
        "⚙️ Cadastro de Solados e Cores",
        "📑 Importar Excel e Gerar Relatório"
    ]
)
st.sidebar.markdown("---")

if menu_selecionado == "📝 De-Para":
    # (Código da tela de De-Para com SQL Server)
    ...

elif menu_selecionado == "⚙️ Cadastro de Solados e Cores":
    # (Código da tela com consulta da tabela PC10T)
    ...

elif menu_selecionado == "📑 Importar Excel e Gerar Relatório":
    # (Código de processamento do Excel e geração do PDF/Excel)
    ...