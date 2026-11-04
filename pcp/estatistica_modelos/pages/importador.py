import streamlit as st
from utils.storage import carregar_de_para
from utils.relatorios import processar_relatorio_chb

st.title("📑 Importar Relatório CHB e Gerar Resumos")
st.markdown("---")
st.subheader("1. Importar o Relatório Excel gerado pelo ERP CHB (.xlsx)")

arquivo_excel = st.file_uploader(
    "Selecione o arquivo Excel do CHB:", type=["xlsx", "xls"], key="excel_chb_uploader"
)

if arquivo_excel:
    if st.button("🚀 Processar Excel e Gerar Relatório", type="primary"):
        with st.spinner("Processando relatório e calculando resumos..."):
            df_cadastros = carregar_de_para()

            # Chama a lógica desacoplada
            buffer_pdf, buffer_excel = processar_relatorio_chb(
                arquivo_excel, df_cadastros
            )

        st.success("Relatório gerado com sucesso em padrão A4 Retrato!")

        col_d1, col_d2 = st.columns(2)
        with col_d1:
            st.download_button(
                label="📄 Baixar PDF (A4 Retrato)",
                data=buffer_pdf,
                file_name="Estatistica_Modelo_CHB_A4_Retrato.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        with col_d2:
            st.download_button(
                label="📊 Baixar Excel com Abas dos Resumos",
                data=buffer_excel,
                file_name="Estatistica_Modelo_CHB_Resumos.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
