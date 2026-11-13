import streamlit as st

# Configuração da página principal
# st.set_page_config(
#    page_title="Gestão de Produtos - CO13T",
#    page_icon="📖",
#    layout="wide",
#    initial_sidebar_state="expanded",
# )

st.title("📖 Início - Gestão de Produtos")
st.markdown("### Manutenção e Liberação em Lote de Produtos (`CO13T`)")

st.info(
    "Esta rotina foi projetada para otimizar o fluxo de precificação e liberação de mercadorias no ERP CHB, "
    "eliminando a necessidade de manutenções manuais individuais ou execução manual de scripts no banco."
)

st.markdown("---")

c1, c2 = st.columns(2)
with c1:
    st.subheader("🎯 Objetivos Principais")
    st.markdown("""
        1. **Importação Rápida:** Capturar listas de produtos a partir de planilhas (`.xlsx`, `.xls`, `.ods`), arquivos `.pdf` de fornecedores ou texto bruto copiado.
        2. **Filtro Inteligente de Códigos:** Extração automática apenas dos códigos numéricos (5 a 8 dígitos), desprezando descrições, cabeçalhos ou símbolos de moeda.
        3. **Controle de Segurança por Checkbox:** Nenhuma coluna da tabela de dados é liberada para edição até que o respectivo checkbox de controle seja ativado.
        4. **Liberação de Itens Bloqueados:** Possibilidade de reverter o bloqueio (`co13Bloq = 'N'`) com validação direta.
        5. **Sincronização de Valores:** Amarração automática entre Preço Mínimo e Preço Máximo, bem como Custo e Valor Pago.
        """)

with c2:
    st.subheader("📑 Campos Modificados na Tabela `CO13T`")
    st.markdown("""
        | Campo Físico | Nome Amigável | Descrição / Regra |
        | :--- | :--- | :--- |
        | **`co13Bloq`** | Bloqueado | Flag `S`/`N`. Permite liberação direta para `N`. |
        | **`co13PCoMax`** | Preço Máximo | Teto de preço de venda/compra. |
        | **`co13PCoMin`** | Preço Mínimo | Preço base de piso (sincronizável com o Máximo). |
        | **`co13UlCus1`** | Último Custo | Valor base do custo do produto. |
        | **`co13UlCus2`** | Último Valor Pago | Valor efetivo pago (sincronizável com Custo 1). |
        """)

st.markdown("---")
st.subheader("🔄 Fluxo Operacional Recomendado")

st.markdown("""
    1. Acesse o menu lateral e selecione **📦 1 liberacao produtos**.
    2. **Carregar Códigos:** Faça o upload do arquivo recebido (ou cole os códigos no campo de texto).
    3. **Consultar:** Clique em *Executar Consulta no Banco de Dados* para carregar os dados atuais.
    4. **Habilitar Alterações:** Marque os checkboxes dos campos que deseja alterar no topo da grade.
    5. **Editar:** Altere diretamente nas células da tabela ou use o painel *Preenchimento Rápido em Lote*.
    6. **Validar:** Clique em *Gerar Query UPDATE (Validação)* para conferir o script antes de afetar o banco.
    7. **Gravar:** Clique em *Confirmar e Gravar no Banco de Dados*. A aplicação abrirá a confirmação detalhando as alterações e gerará o log `.txt` nomeado no formato `YYYYMMDDHHmm.txt`.
    """)

st.page_link(
    "pages/1_liberacao_produtos.py",
    label="Ir para a rotina de Liberação de Produtos ➡️",
    icon="📦",
)
