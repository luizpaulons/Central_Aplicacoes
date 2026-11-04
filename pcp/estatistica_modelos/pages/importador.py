import streamlit as st
import pandas as pd
from utils.storage import carregar_de_para
from utils.relatorios import gerar_pdf_relatorio

#st.set_page_config(page_title="Relatório CHB", layout="wide")
st.title("📑 Importar Excel e Gerar Relatório CHB")

with aba_processar:
    st.subheader("3. Importar o Relatório Excel gerado pelo ERP CHB (.xlsx)")
    
    arquivo_excel = st.file_uploader("Selecione o arquivo Excel do CHB:", type=["xlsx", "xls"], key="excel_chb")
    
    if arquivo_excel:
        if st.button("🚀 Processar Excel e Gerar Relatório"):
            with st.spinner("Processando relatório e calculando resumos..."):
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
                total_geral_txt = ""
                
                modelos_processados = []
                modelo_atual_obj = None

                # Estruturas para os novos resumos
                # solado -> { cor: quantidade }
                resumo_por_solado_dict = {}
                # cor -> quantidade total
                resumo_por_cor_dict = {}

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
                        total_geral_txt = col10.replace(".0", "")
                        try:
                            total_geral_num = int(float(total_geral_txt))
                        except:
                            total_geral_num = 0

                    if col0 == "" and col1.isdigit() and col2 != "":
                        if modelo_atual_obj:
                            modelos_processados.append(modelo_atual_obj)
                        
                        pares_num = int(float(col4)) if col4 and col4.replace(".0", "").isdigit() else 0
                        perc_ger = f"{float(col6):.2f}".replace(".", ",") if col6 and col6.replace(".", "", 1).isdigit() else col6
                        
                        modelo_atual_obj = {
                            "linha": col1,
                            "nome": col2,
                            "pares_total": pares_num,
                            "perc_geral": perc_ger,
                            "cores": []
                        }

                    elif col0.isdigit() and col1.isdigit():
                        cod_cor = col1
                        mod = col0
                        info_extra = mapa_de_para.get((mod, cod_cor), {"solado": "", "eva": ""})
                        
                        pares_num = int(float(col4)) if col4 and col4.replace(".0", "").isdigit() else 0
                        perc_lin = f"{float(col5):.2f}".replace(".", ",") if col5 and col5.replace(".", "", 1).isdigit() else col5
                        perc_ger = f"{float(col6):.2f}".replace(".", ",") if col6 and col6.replace(".", "", 1).isdigit() else col6
                        
                        solado_nome = info_extra["solado"].strip().upper() if info_extra["solado"].strip() else "SEM SOLADO"
                        eva_nome = info_extra["eva"].strip().upper() if info_extra["eva"].strip() else "SEM EVA"

                        # Acumulação do Resumo 1 (Solado -> Cor)
                        if solado_nome not in resumo_por_solado_dict:
                            resumo_por_solado_dict[solado_nome] = {}
                        resumo_por_solado_dict[solado_nome][eva_nome] = resumo_por_solado_dict[solado_nome].get(eva_nome, 0) + pares_num

                        # Acumulação do Resumo 2 (Cor Geral)
                        resumo_por_cor_dict[eva_nome] = resumo_por_cor_dict.get(eva_nome, 0) + pares_num

                        cor_item = {
                            "cod_cor": cod_cor,
                            "desc_cor": col2,
                            "solado": info_extra["solado"],
                            "cor_eva": info_extra["eva"],
                            "pares": pares_num,
                            "perc_linha": perc_lin,
                            "perc_geral": perc_ger
                        }
                        
                        if modelo_atual_obj:
                            modelo_atual_obj["cores"].append(cor_item)

                if modelo_atual_obj:
                    modelos_processados.append(modelo_atual_obj)

                soma_geral = sum(resumo_por_cor_dict.values())
                divisor_perc = total_geral_num if total_geral_num > 0 else soma_geral

                # Ordenação do Resumo 1 (Solado com SEM SOLADO primeiro, depois A-Z)
                solados_ordenados = sorted(
                    resumo_por_solado_dict.keys(),
                    key=lambda s: (0 if s == "SEM SOLADO" else 1, s)
                )

                # Ordenação do Resumo 2 (Cor com SEM EVA primeiro, depois A-Z)
                cores_ordenadas = sorted(
                    resumo_por_cor_dict.items(),
                    key=lambda c: (0 if c[0] == "SEM EVA" else 1, c[0])
                )

                # ==========================================================
                # MONTAGEM DO PDF
                # ==========================================================
                buffer_pdf = BytesIO()
                doc = SimpleDocTemplate(
                    buffer_pdf,
                    pagesize=landscape(letter),
                    leftMargin=18, rightMargin=18, topMargin=18, bottomMargin=18
                )

                est_header = ParagraphStyle('CHB_H', fontName='Courier-Bold', fontSize=8, leading=9)
                est_header_tab = ParagraphStyle('CHB_HT', fontName='Courier-Bold', fontSize=7.5, leading=8.5, textColor=colors.black)
                est_text = ParagraphStyle('CHB_T', fontName='Courier', fontSize=7.5, leading=8.5)
                est_text_bold = ParagraphStyle('CHB_TB', fontName='Courier-Bold', fontSize=7.5, leading=8.5)
                est_destaque = ParagraphStyle('CHB_DEST', fontName='Courier-Bold', fontSize=7.5, leading=8.5, textColor=colors.HexColor("#0B5394"))
                est_subtot = ParagraphStyle('CHB_SUB', fontName='Courier-Bold', fontSize=7, leading=8, textColor=colors.HexColor("#78281F"))
                est_right = ParagraphStyle('CHB_R', fontName='Courier', fontSize=7.5, leading=8.5, alignment=2)
                est_right_bold = ParagraphStyle('CHB_RB', fontName='Courier-Bold', fontSize=7.5, leading=8.5, alignment=2)

                elementos = []
                elementos.append(Paragraph(f"Empresa: {empresa_nome}", est_header))
                elementos.append(Paragraph("Estatistica de Modelo - PCP", est_header))
                elementos.append(Spacer(1, 6))

                # Tabela Principal Detalhada
                cabecalho_tabela = [
                    Paragraph("<b>Linha</b>", est_header),
                    Paragraph("<b>Modelo / Descrição da Cor</b>", est_header),
                    Paragraph("<b>Cor</b>", est_header),
                    Paragraph("<b>Cor EVA</b>", est_header),
                    Paragraph("<b>Solado</b>", est_header),
                    Paragraph("<b>Pares</b>", est_header),
                    Paragraph("<b>(%) Linha</b>", est_header),
                    Paragraph("<b>(%) Geral</b>", est_header)
                ]

                col_widths = [45, 175, 45, 115, 115, 60, 65, 65]
                linhas_doc = [cabecalho_tabela]
                estilo_tabela = [
                    ('LINEABOVE', (0, 0), (-1, 0), 1, colors.black),
                    ('LINEBELOW', (0, 0), (-1, 0), 1, colors.black),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('TOPPADDING', (0, 0), (-1, -1), 1.5),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5),
                ]

                row_idx = 1
                for mod_obj in modelos_processados:
                    linhas_doc.append([
                        Paragraph(f"<b>{mod_obj['linha']}</b>", est_text_bold),
                        Paragraph(f"<b>{mod_obj['nome']}</b>", est_text_bold),
                        Paragraph("", est_text),
                        Paragraph("", est_text),
                        Paragraph("", est_text),
                        Paragraph(f"<b>{fmt_milhar(mod_obj['pares_total'])}</b>", est_right_bold),
                        Paragraph("", est_right),
                        Paragraph(f"<b>{mod_obj['perc_geral']}</b>", est_right_bold)
                    ])
                    estilo_tabela.append(('BACKGROUND', (0, row_idx), (-1, row_idx), colors.HexColor("#EDEDED")))
                    row_idx += 1

                    subtotais_eva = {}
                    for c in mod_obj["cores"]:
                        linhas_doc.append([
                            Paragraph("", est_text),
                            Paragraph(f"&nbsp;&nbsp;{c['desc_cor']}", est_text),
                            Paragraph(c["cod_cor"], est_text),
                            Paragraph(f"<b>{c['cor_eva']}</b>", est_destaque),
                            Paragraph(f"<b>{c['solado']}</b>", est_destaque),
                            Paragraph(fmt_milhar(c["pares"]), est_right),
                            Paragraph(c["perc_linha"], est_right),
                            Paragraph(c["perc_geral"], est_right)
                        ])
                        row_idx += 1
                        
                        eva_nome = c["cor_eva"].strip().upper() if c["cor_eva"].strip() else "SEM EVA"
                        subtotais_eva[eva_nome] = subtotais_eva.get(eva_nome, 0) + c["pares"]

                    for nome_eva, qtd_eva in sorted(subtotais_eva.items(), key=lambda x: x[1], reverse=True):
                        linhas_doc.append([
                            Paragraph("", est_text),
                            Paragraph(f"&nbsp;&nbsp;&nbsp;&nbsp;<i>[Subtotal EVA] {nome_eva}</i>", est_subtot),
                            Paragraph("", est_text),
                            Paragraph(f"<i>{nome_eva}</i>", est_subtot),
                            Paragraph("", est_text),
                            Paragraph(f"<b>{fmt_milhar(qtd_eva)}</b>", est_subtot),
                            Paragraph("", est_right),
                            Paragraph("", est_right)
                        ])
                        estilo_tabela.append(('BACKGROUND', (0, row_idx), (-1, row_idx), colors.HexColor("#FDF2E9")))
                        row_idx += 1

                if total_geral_num > 0:
                    linhas_doc.append([
                        Paragraph("<b>Total............:</b>", est_text_bold),
                        Paragraph("", est_text),
                        Paragraph("", est_text),
                        Paragraph("", est_text),
                        Paragraph("", est_text),
                        Paragraph(f"<b>{fmt_milhar(total_geral_num)}</b>", est_right_bold),
                        Paragraph("", est_right),
                        Paragraph("<b>100,00</b>", est_right_bold)
                    ])
                    estilo_tabela.append(('LINEABOVE', (0, row_idx), (-1, row_idx), 1, colors.black))
                    estilo_tabela.append(('LINEBELOW', (0, row_idx), (-1, row_idx), 1, colors.black))

                tab_principal = Table(linhas_doc, colWidths=col_widths, repeatRows=1)
                tab_principal.setStyle(TableStyle(estilo_tabela))
                elementos.append(tab_principal)

                # ==========================================================
                # RESUMO 1: POR SOLADO E COR COM SUBTOTAL
                # ==========================================================
                elementos.append(Spacer(1, 16))
                elementos.append(Paragraph("<b>RESUMO 1: QUANTIDADE POR SOLADO E COR</b>", est_header))
                elementos.append(Spacer(1, 4))

                linhas_r1 = [[
                    Paragraph("<b>Solado</b>", est_header_tab),
                    Paragraph("<b>Cor do EVA</b>", est_header_tab),
                    Paragraph("<b>Quantidade (Pares)</b>", est_header_tab)
                ]]
                estilo_r1 = [
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('TOPPADDING', (0, 0), (-1, -1), 2.5),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#A0AEC0")),
                ]

                r1_idx = 1
                for sol_nome in solados_ordenados:
                    cores_do_solado = resumo_por_solado_dict[sol_nome]
                    total_solado = sum(cores_do_solado.values())
                    
                    primeira_linha = True
                    for cor_n, qtd_n in sorted(cores_do_solado.items(), key=lambda x: (0 if x[0] == "SEM EVA" else 1, x[0])):
                        linhas_r1.append([
                            Paragraph(f"<b>{sol_nome}</b>" if primeira_linha else "", est_text),
                            Paragraph(cor_n, est_text),
                            Paragraph(fmt_milhar(qtd_n), est_right)
                        ])
                        r1_idx += 1
                        primeira_linha = False
                    
                    # Linha de Total do Solado
                    linhas_r1.append([
                        Paragraph(f"<b>Total {sol_nome}</b>", est_text_bold),
                        Paragraph("", est_text),
                        Paragraph(f"<b>{fmt_milhar(total_solado)}</b>", est_right_bold)
                    ])
                    estilo_r1.append(('BACKGROUND', (0, r1_idx), (-1, r1_idx), colors.HexColor("#F4F6F6")))
                    r1_idx += 1

                # Total Geral do Resumo 1
                linhas_r1.append([
                    Paragraph("<b>TOTAL GERAL</b>", est_text_bold),
                    Paragraph("", est_text),
                    Paragraph(f"<b>{fmt_milhar(soma_geral)}</b>", est_right_bold)
                ])
                estilo_r1.append(('BACKGROUND', (0, r1_idx), (-1, r1_idx), colors.HexColor("#EDF2F7")))

                tab_resumo_1 = Table(linhas_r1, colWidths=[240, 240, 140])
                tab_resumo_1.setStyle(TableStyle(estilo_r1))
                elementos.append(tab_resumo_1)

                # ==========================================================
                # RESUMO 2: CONSOLIDADO POR COR
                # ==========================================================
                elementos.append(Spacer(1, 16))
                elementos.append(Paragraph("<b>RESUMO 2: QUANTIDADE CONSOLIDADA POR COR</b>", est_header))
                elementos.append(Spacer(1, 4))

                linhas_r2 = [[
                    Paragraph("<b>Cor do EVA</b>", est_header_tab),
                    Paragraph("<b>Quantidade (Pares)</b>", est_header_tab),
                    Paragraph("<b>(%) Geral</b>", est_header_tab)
                ]]
                estilo_r2 = [
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('TOPPADDING', (0, 0), (-1, -1), 2.5),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#A0AEC0")),
                ]

                r2_idx = 1
                for cor_nome, qtd_cor in cores_ordenadas:
                    perc = (qtd_cor / divisor_perc * 100) if divisor_perc > 0 else 0
                    linhas_r2.append([
                        Paragraph(f"<b>{cor_nome}</b>", est_text),
                        Paragraph(fmt_milhar(qtd_cor), est_right),
                        Paragraph(f"{perc:.2f}%".replace(".", ","), est_right)
                    ])
                    if cor_nome == "SEM EVA":
                        estilo_r2.append(('BACKGROUND', (0, r2_idx), (-1, r2_idx), colors.HexColor("#FADBD8")))
                    r2_idx += 1

                linhas_r2.append([
                    Paragraph("<b>TOTAL GERAL</b>", est_text_bold),
                    Paragraph(f"<b>{fmt_milhar(soma_geral)}</b>", est_right_bold),
                    Paragraph("<b>100,00%</b>", est_right_bold)
                ])
                estilo_r2.append(('BACKGROUND', (0, r2_idx), (-1, r2_idx), colors.HexColor("#EDF2F7")))

                tab_resumo_2 = Table(linhas_r2, colWidths=[300, 160, 160])
                tab_resumo_2.setStyle(TableStyle(estilo_r2))
                elementos.append(tab_resumo_2)

                doc.build(elementos)
                buffer_pdf.seek(0)

                # ==========================================================
                # MONTAGEM DAS ABAS DO EXCEL
                # ==========================================================
                buffer_excel = BytesIO()

                # 1. Tabela Detalhada
                linhas_excel = []
                for mod_obj in modelos_processados:
                    linhas_excel.append({
                        "Linha": mod_obj["linha"],
                        "Modelo": mod_obj["nome"],
                        "Cód. Cor": "",
                        "Descrição": f"TOTAL MODELO {mod_obj['linha']}",
                        "Cor EVA": "",
                        "Solado": "",
                        "Pares": mod_obj["pares_total"],
                        "(%) Linha": "",
                        "(%) Geral": mod_obj["perc_geral"]
                    })
                    subtotais_eva = {}
                    for c in mod_obj["cores"]:
                        linhas_excel.append({
                            "Linha": mod_obj["linha"],
                            "Modelo": mod_obj["nome"],
                            "Cód. Cor": c["cod_cor"],
                            "Descrição": c["desc_cor"],
                            "Cor EVA": c["cor_eva"],
                            "Solado": c["solado"],
                            "Pares": c["pares"],
                            "(%) Linha": c["perc_linha"],
                            "(%) Geral": c["perc_geral"]
                        })
                        eva_nome = c["cor_eva"].strip().upper() if c["cor_eva"].strip() else "SEM EVA"
                        subtotais_eva[eva_nome] = subtotais_eva.get(eva_nome, 0) + c["pares"]

                    for nome_eva, qtd_eva in sorted(subtotais_eva.items(), key=lambda x: x[1], reverse=True):
                        linhas_excel.append({
                            "Linha": mod_obj["linha"],
                            "Modelo": mod_obj["nome"],
                            "Cód. Cor": "",
                            "Descrição": f"   SUBTOTAL EVA: {nome_eva}",
                            "Cor EVA": nome_eva,
                            "Solado": "",
                            "Pares": qtd_eva,
                            "(%) Linha": "",
                            "(%) Geral": ""
                        })

                # 2. Resumo 1 (Por Solado e Cor)
                linhas_excel_r1 = []
                for sol_nome in solados_ordenados:
                    cores_do_solado = resumo_por_solado_dict[sol_nome]
                    total_solado = sum(cores_do_solado.values())
                    for cor_n, qtd_n in sorted(cores_do_solado.items(), key=lambda x: (0 if x[0] == "SEM EVA" else 1, x[0])):
                        linhas_excel_r1.append({
                            "Solado": sol_nome,
                            "Cor do EVA": cor_n,
                            "Quantidade (Pares)": qtd_n
                        })
                    linhas_excel_r1.append({
                        "Solado": f"TOTAL {sol_nome}",
                        "Cor do EVA": "-",
                        "Quantidade (Pares)": total_solado
                    })
                linhas_excel_r1.append({
                    "Solado": "TOTAL GERAL",
                    "Cor do EVA": "-",
                    "Quantidade (Pares)": soma_geral
                })

                # 3. Resumo 2 (Por Cor)
                linhas_excel_r2 = []
                for cor_nome, qtd_cor in cores_ordenadas:
                    perc = (qtd_cor / divisor_perc * 100) if divisor_perc > 0 else 0
                    linhas_excel_r2.append({
                        "Cor do EVA": cor_nome,
                        "Quantidade (Pares)": qtd_cor,
                        "(%) Geral": f"{perc:.2f}%".replace(".", ",")
                    })
                linhas_excel_r2.append({
                    "Cor do EVA": "TOTAL GERAL",
                    "Quantidade (Pares)": soma_geral,
                    "(%) Geral": "100,00%"
                })

                with pd.ExcelWriter(buffer_excel, engine='openpyxl') as writer:
                    pd.DataFrame(linhas_excel).to_excel(writer, index=False, sheet_name="Estatistica Detalhada")
                    pd.DataFrame(linhas_excel_r1).to_excel(writer, index=False, sheet_name="Resumo 1 - Solado e Cor")
                    pd.DataFrame(linhas_excel_r2).to_excel(writer, index=False, sheet_name="Resumo 2 - Total por Cor")
                buffer_excel.seek(0)

                st.success("Relatório gerado com sucesso!")
                
                col_d1, col_d2 = st.columns(2)
                with col_d1:
                    st.download_button(
                        label="📄 Baixar PDF com os 2 Novos Resumos",
                        data=buffer_pdf,
                        file_name="Estatistica_Modelo_CHB_Resumos.pdf",
                        mime="application/pdf"
                    )
                with col_d2:
                    st.download_button(
                        label="📊 Baixar Excel com as Abas de Resumos",
                        data=buffer_excel,
                        file_name="Estatistica_Modelo_CHB_Resumos.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )