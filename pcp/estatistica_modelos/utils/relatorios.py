from io import BytesIO
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from utils.storage import fmt_milhar

def gerar_pdf_relatorio(empresa_nome, total_geral_num, modelos_processados):
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

    elementos = [
        Paragraph(f"Empresa: {empresa_nome}", est_header),
        Paragraph("Estatistica de Modelo - PCP", est_header),
        Spacer(1, 6)
    ]

    cabecalho = [
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
    linhas_doc = [cabecalho]
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
            Paragraph("", est_text), Paragraph("", est_text), Paragraph("", est_text),
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
                Paragraph("", est_right), Paragraph("", est_right)
            ])
            estilo_tabela.append(('BACKGROUND', (0, row_idx), (-1, row_idx), colors.HexColor("#FDF2E9")))
            row_idx += 1

    if total_geral_num > 0:
        linhas_doc.append([
            Paragraph("<b>Total............:</b>", est_text_bold),
            Paragraph("", est_text), Paragraph("", est_text), Paragraph("", est_text), Paragraph("", est_text),
            Paragraph(f"<b>{fmt_milhar(total_geral_num)}</b>", est_right_bold),
            Paragraph("", est_right),
            Paragraph("<b>100,00</b>", est_right_bold)
        ])
        estilo_tabela.append(('LINEABOVE', (0, row_idx), (-1, row_idx), 1, colors.black))
        estilo_tabela.append(('LINEBELOW', (0, row_idx), (-1, row_idx), 1, colors.black))

    tab_principal = Table(linhas_doc, colWidths=col_widths, repeatRows=1)
    tab_principal.setStyle(TableStyle(estilo_tabela))
    elementos.append(tab_principal)

    # Resumo por Modelo
    elementos.append(Spacer(1, 16))
    elementos.append(Paragraph("<b>1. RESUMO POR MODELO (SOLADO E CORES DE EVA)</b>", est_header))
    elementos.append(Spacer(1, 4))
    linhas_res_mod = [[
        Paragraph("<b>Linha / Modelo</b>", est_header_tab),
        Paragraph("<b>Solado</b>", est_header_tab),
        Paragraph("<b>Cor do EVA</b>", est_header_tab),
        Paragraph("<b>Quantidade (Pares)</b>", est_header_tab),
        Paragraph("<b>Total Modelo</b>", est_header_tab)
    ]]
    for mod_obj in modelos_processados:
        sub_eva_mod = {}
        solados_mod = set()
        for c in mod_obj["cores"]:
            eva_n = c["cor_eva"].strip().upper() if c["cor_eva"].strip() else "SEM EVA"
            sol_n = c["solado"].strip().upper() if c["solado"].strip() else "SEM SOLADO"
            sub_eva_mod[eva_n] = sub_eva_mod.get(eva_n, 0) + c["pares"]
            solados_mod.add(sol_n)
        solados_str = ", ".join(sorted(solados_mod)) if solados_mod else "-"
        primeiro = True
        for eva_n, qtd_n in sorted(sub_eva_mod.items(), key=lambda x: x[1], reverse=True):
            linhas_res_mod.append([
                Paragraph(f"<b>Modelo {mod_obj['linha']} ({mod_obj['nome']})</b>" if primeiro else "", est_text),
                Paragraph(solados_str if primeiro else "", est_text),
                Paragraph(eva_n, est_text),
                Paragraph(fmt_milhar(qtd_n), est_right),
                Paragraph(f"<b>Total: {fmt_milhar(mod_obj['pares_total'])}</b>" if primeiro else "", est_right_bold)
            ])
            primeiro = False

    tab_res_mod = Table(linhas_res_mod, colWidths=[180, 120, 140, 120, 120])
    tab_res_mod.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#A0AEC0")),
    ]))
    elementos.append(tab_res_mod)

    doc.build(elementos)
    buffer_pdf.seek(0)
    return buffer_pdf