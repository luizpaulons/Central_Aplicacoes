import streamlit as st
import pandas as pd
import json
import os
import database
import imap_reader

st.title("📂 Consulta de Faturas Importadas")

faturas = database.listar_faturas()

if not faturas:
    st.info("Nenhuma fatura registrada no banco até o momento.")
else:
    # 1 - Montagem da tabela com índice a partir do 1 e coluna de fechamento
    dados_grid = []
    for i, f in enumerate(faturas, start=1):
        fid, arq, venc, total, status, dt_fech = f
        dados_grid.append({
            "Nº": i,
            "Arquivo": arq,
            "Vencimento": venc,
            "Valor Total": f"R$ {total:,.2f}",
            "Status": "🔒 FECHADA" if status == "FECHADA" else "⏳ ABERTA",
            "Fechada em": dt_fech if dt_fech else "Ainda aberta"
        })
    
    df_fat = pd.DataFrame(dados_grid).set_index("Nº")
    st.dataframe(df_fat, width='stretch')

    st.markdown("---")
    st.subheader("Visualizar / Baixar Documentos da Fatura")
    
    venc_selecionado = st.selectbox(
        "Selecione uma fatura pelo vencimento para inspecionar os anexos:",
        options=[f[2] for f in faturas]
    )
    
    if venc_selecionado:
        status_sel, itens_sel = database.carregar_fatura(venc_selecionado)
        if itens_sel:
            st.markdown(f"**Comprovantes vinculados à fatura de {venc_selecionado}:**")
            anexos_encontrados = []
            for it in itens_sel:
                for anexo in it.get("anexos_nf", []):
                    if anexo and anexo not in anexos_encontrados:
                        anexos_encontrados.append(anexo)
            
            if anexos_encontrados:
                cols = st.columns(3)
                for idx_a, anexo_nome in enumerate(anexos_encontrados):
                    caminho = os.path.join(imap_reader.NOTAS_DIR, anexo_nome)
                    if os.path.exists(caminho):
                        with open(caminho, "rb") as f_pdf:
                            cols[idx_a % 3].download_button(
                                label=f"📄 Abrir PDF: {anexo_nome[:20]}...",
                                data=f_pdf.read(),
                                file_name=anexo_nome,
                                mime="application/pdf",
                                key=f"btn_cons_{idx_a}"
                            )
            else:
                st.info("Nenhum arquivo PDF de nota fiscal vinculado a esta fatura.")