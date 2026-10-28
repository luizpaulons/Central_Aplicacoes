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
