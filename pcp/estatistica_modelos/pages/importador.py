import streamlit as st
import pandas as pd
from utils.storage import carregar_de_para
from utils.relatorios import gerar_pdf_relatorio

#st.set_page_config(page_title="Relatório CHB", layout="wide")
st.title("📑 Importar Excel e Gerar Relatório CHB")

arquivo_excel = st.file_uploader("Selecione o arquivo Excel do ERP CHB (.xlsx):", type=["xlsx", "xls"])

if arquivo_excel:
    if st.button("🚀 Processar Excel e Gerar Relatório"):
        with st.spinner("Processando dados e gerando PDF..."):
            df_cadastros = carregar_de_para()
            mapa_de_para = {}
            if not df_cadastros.empty:
                for _, r in df_cadastros.iterrows():
                    chave = (str(r["linha"]).strip().upper(), str(r["cor"]).strip().upper())
                    mapa_de_para[chave] = {
                        "solado": str(r.get("nome_solado", "")).strip().upper(),
                        "eva": str(r.get("cor_eva", "")).strip().upper()
                    }

            df_raw = pd.read_excel(arquivo_excel, header=None)
            empresa_nome = "1 LYND CALCADOS LTDA"
            total_geral_num = 0
            modelos_processados = []
            modelo_atual_obj = None

            for idx, row in df_raw.iterrows():
                col0 = str(row[0]).strip().upper() if pd.notna(row[0]) else ""
                col1 = str(row[1]).strip().upper() if pd.notna(row[1]) else ""
                col2 = str(row[2]).strip().upper() if pd.notna(row[2]) else ""
                col4 = str(row[4]).strip() if pd.notna(row[4]) else ""
                col5 = str(row[5]).strip() if pd.notna(row[5]) else ""
                col6 = str(row[6]).strip() if pd.notna(row[6]) else ""

                if "EMPRESA:" in col0 and col2:
                    empresa_nome = col2

                col9 = str(row[9]).strip().upper() if len(row) > 9 and pd.notna(row[9]) else ""
                col10 = str(row[10]).strip() if len(row) > 10 and pd.notna(row[10]) else ""
                if "TOTAL" in col9:
                    try:
                        total_geral_num = int(float(col10.replace(".0", "")))
                    except:
                        total_geral_num = 0

                if col0 == "" and col1.isdigit() and col2 != "":
                    if modelo_atual_obj:
                        modelos_processados.append(modelo_atual_obj)
                    pares_num = int(float(col4)) if col4 and col4.replace(".0", "").isdigit() else 0
                    perc_ger = f"{float(col6):.2f}".replace(".", ",") if col6 and col6.replace(".", "", 1).isdigit() else col6
                    modelo_atual_obj = {
                        "linha": col1, "nome": col2, "pares_total": pares_num, "perc_geral": perc_ger, "cores": []
                    }

                elif col0.isdigit() and col1.isdigit():
                    cod_cor = col1
                    mod = col0
                    info_extra = mapa_de_para.get((mod, cod_cor), {"solado": "", "eva": ""})
                    pares_num = int(float(col4)) if col4 and col4.replace(".0", "").isdigit() else 0
                    perc_lin = f"{float(col5):.2f}".replace(".", ",") if col5 and col5.replace(".", "", 1).isdigit() else col5
                    perc_ger = f"{float(col6):.2f}".replace(".", ",") if col6 and col6.replace(".", "", 1).isdigit() else col6

                    if modelo_atual_obj:
                        modelo_atual_obj["cores"].append({
                            "cod_cor": cod_cor, "desc_cor": col2,
                            "solado": info_extra["solado"], "cor_eva": info_extra["eva"],
                            "pares": pares_num, "perc_linha": perc_lin, "perc_geral": perc_ger
                        })

            if modelo_atual_obj:
                modelos_processados.append(modelo_atual_obj)

            buffer_pdf = gerar_pdf_relatorio(empresa_nome, total_geral_num, modelos_processados)

            st.success("Relatório gerado com sucesso!")
            st.download_button(
                label="📄 Baixar PDF do Relatório",
                data=buffer_pdf,
                file_name="Estatistica_Modelo_PCP.pdf",
                mime="application/pdf"
            )