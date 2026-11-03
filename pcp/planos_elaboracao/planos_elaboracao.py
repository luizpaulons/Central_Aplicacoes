import streamlit as st
import openpyxl
from openpyxl.styles import PatternFill, Font, Alignment
from openpyxl.utils import get_column_letter
import io

st.set_page_config(
    page_title="Formatação de Planos em Elaboração",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -------------------------------------------------------------
# BARRA LATERAL (NAVEGAÇÃO POR RÁDIO)
# -------------------------------------------------------------
st.sidebar.title("Planos em Elaboração")
st.sidebar.markdown("---")
pagina = st.sidebar.radio(
    "Selecione a Tela:",
    ["Início", "Processar Planilha"]
)
st.sidebar.markdown("---")
# -------------------------------------------------------------
# FUNÇÃO PRINCIPAL DE PROCESSAMENTO DO EXCEL
# -------------------------------------------------------------
def processar_planilha_planos(uploaded_file):
    wb = openpyxl.load_workbook(uploaded_file)
    ws_original = wb.active
    ws_original.title = "Analitico"
    ws_analitico = ws_original

    # Estilos
    fill_secao = PatternFill(start_color="DAE9F8", end_color="DAE9F8", fill_type="solid")
    fill_plano = PatternFill(start_color="DAF2D0", end_color="DAF2D0", fill_type="solid")
    fill_header = PatternFill(start_color="000000", end_color="000000", fill_type="solid")
    font_header = Font(color="FFFFFF", bold=True)
    font_bold = Font(bold=True)

    # Formatos numéricos de milhar
    fmt_milhar_2dec = "#,##0.00"
    fmt_milhar_int = "#,##0"

    # =========================================================
    # PARTE 1: FORMATAÇÃO DA ABA ANALÍTICO (Passos 1 a 7)
    # =========================================================
    # 1. Excluir as 2 primeiras linhas
    ws_analitico.delete_rows(1, 2)

    # 3 a 6. Formatações condicionais e máscaras no Analítico
    for r in range(1, ws_analitico.max_row + 1):
        col_a_val = str(ws_analitico.cell(r, 1).value or "").strip().upper()
        col_c_val = str(ws_analitico.cell(r, 3).value or "").strip().upper()
        col_d_val = str(ws_analitico.cell(r, 4).value or "").strip().upper()

        # 3. Pintar linhas com "SEÇÃO" na Coluna A de #DAE9F8 (Col A até J)
        if "SEÇÃO" in col_a_val or "SECAO" in col_a_val:
            for c in range(1, 11):
                ws_analitico.cell(r, c).fill = fill_secao

        # 4. Pintar linhas com "PLANO" na Coluna A de #DAF2D0 (Col A até J)
        elif "PLANO" in col_a_val:
            for c in range(1, 11):
                ws_analitico.cell(r, c).fill = fill_plano

        # 5. Colunas D até J como milhar
        for c in range(4, 11):
            cell = ws_analitico.cell(r, c)
            if isinstance(cell.value, (int, float)):
                cell.number_format = fmt_milhar_2dec

        # 6. Onde estiver "Pares", retirar casas decimais da quantidade
        if "PARES" in col_c_val and isinstance(ws_analitico.cell(r, 4).value, (int, float)):
            ws_analitico.cell(r, 4).number_format = fmt_milhar_int
        elif "PARES" in col_d_val and isinstance(ws_analitico.cell(r, 6).value, (int, float)):
            ws_analitico.cell(r, 6).number_format = fmt_milhar_int

    # 2. Redimensionar colunas da aba Analítico
    for col in ws_analitico.columns:
        col_letter = get_column_letter(col[0].column)
        max_len = 0
        for cell in col:
            val = str(cell.value or '')
            if cell.number_format and ('#' in cell.number_format or '0' in cell.number_format):
                val += "    "
            max_len = max(max_len, len(val))
        ws_analitico.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 45)

    # =========================================================
    # PARTE 2: CRIAÇÃO E FORMATAÇÃO DA ABA SINTÉTICO (Passos 8 a 24)
    # =========================================================
    ws_sintetico = wb.create_sheet(title="Sintetico")

    # 21. Cabeçalho na Linha 1
    headers = [
        "",                     # A: Vazia
        "",                     # B: Vazia
        "Total Pares",          # C
        "R$ Previsto",          # D
        "R$ Realizado",         # E
        "R$ Resultado",         # F
        "Média (Prev)",         # G
        "Média (Real)"          # H
    ]
    ws_sintetico.append(headers)

    # 23. Linha 1: fundo #000000 e letras #FFFFFF
    for c in range(1, 9):
        cell = ws_sintetico.cell(1, c)
        cell.fill = fill_header
        cell.font = font_header
        cell.alignment = Alignment(horizontal="center", vertical="center")

    current_secao_code = ""
    current_secao_desc = ""
    current_plano_code = ""
    target_row_sint = 2

    # Lista para alimentar a aba Resumo com os totais de cada seção
    dados_resumo_secoes = []

    for r in range(1, ws_analitico.max_row + 1):
        col_a = ws_analitico.cell(r, 1).value
        col_b = ws_analitico.cell(r, 2).value
        col_c = ws_analitico.cell(r, 3).value
        col_d = ws_analitico.cell(r, 4).value
        col_g = ws_analitico.cell(r, 7).value  # R$ Previsto
        col_h = ws_analitico.cell(r, 8).value  # R$ Realizado
        col_j = ws_analitico.cell(r, 10).value # R$ Resultado

        col_a_str = str(col_a or "").strip().upper()
        col_b_str = str(col_b or "").strip()

        # Identifica Seção
        if "SEÇÃO" in col_a_str or "SECAO" in col_a_str:
            current_secao_code = str(col_b or "").strip()
            current_secao_desc = str(col_c or "").strip()

            ws_sintetico.cell(target_row_sint, 1, value="Seção")
            ws_sintetico.cell(target_row_sint, 2, value=f"{current_secao_code} - {current_secao_desc}".strip(" -"))

            # 24. Pinta SOMENTE se tiver "Seção" na Coluna A
            for c in range(1, 9):
                ws_sintetico.cell(target_row_sint, c).fill = fill_secao
                ws_sintetico.cell(target_row_sint, c).font = font_bold
            target_row_sint += 1

        # Identifica Plano
        elif "PLANO" in col_a_str:
            current_plano_code = col_b_str

        # Linha Total do Plano
        elif "TOTAL DO PLANO" in col_b_str.upper():
            pares = col_d if isinstance(col_d, (int, float)) else 0
            rs_prev = col_g if isinstance(col_g, (int, float)) else 0.0
            rs_real = col_h if isinstance(col_h, (int, float)) else 0.0
            rs_res = col_j if isinstance(col_j, (int, float)) else 0.0

            ws_sintetico.cell(target_row_sint, 1, value="Plano")
            ws_sintetico.cell(target_row_sint, 2, value=current_plano_code)
            ws_sintetico.cell(target_row_sint, 3, value=pares)
            ws_sintetico.cell(target_row_sint, 4, value=rs_prev)
            ws_sintetico.cell(target_row_sint, 5, value=rs_real)
            ws_sintetico.cell(target_row_sint, 6, value=rs_res)

            # Médias
            ws_sintetico.cell(target_row_sint, 7, value=f"=IF(C{target_row_sint}>0, D{target_row_sint}/C{target_row_sint}, 0)")
            ws_sintetico.cell(target_row_sint, 8, value=f"=IF(C{target_row_sint}>0, E{target_row_sint}/C{target_row_sint}, 0)")

            # Formatações
            ws_sintetico.cell(target_row_sint, 3).number_format = fmt_milhar_int
            for c in range(4, 9):
                ws_sintetico.cell(target_row_sint, c).number_format = fmt_milhar_2dec

            target_row_sint += 1

        # Linha Total da Seção
        elif "TOTAL DA SEÇÃO" in col_b_str.upper() or "TOTAL DA SECAO" in col_b_str.upper():
            pares = col_d if isinstance(col_d, (int, float)) else 0
            rs_prev = col_g if isinstance(col_g, (int, float)) else 0.0
            rs_real = col_h if isinstance(col_h, (int, float)) else 0.0
            rs_res = col_j if isinstance(col_j, (int, float)) else 0.0

            ws_sintetico.cell(target_row_sint, 1, value="")
            ws_sintetico.cell(target_row_sint, 2, value="Total Seção")
            ws_sintetico.cell(target_row_sint, 3, value=pares)
            ws_sintetico.cell(target_row_sint, 4, value=rs_prev)
            ws_sintetico.cell(target_row_sint, 5, value=rs_real)
            ws_sintetico.cell(target_row_sint, 6, value=rs_res)

            ws_sintetico.cell(target_row_sint, 7, value=f"=IF(C{target_row_sint}>0, D{target_row_sint}/C{target_row_sint}, 0)")
            ws_sintetico.cell(target_row_sint, 8, value=f"=IF(C{target_row_sint}>0, E{target_row_sint}/C{target_row_sint}, 0)")

            ws_sintetico.cell(target_row_sint, 3).number_format = fmt_milhar_int
            for c in range(4, 9):
                ws_sintetico.cell(target_row_sint, c).number_format = fmt_milhar_2dec

            for c in range(1, 9):
                ws_sintetico.cell(target_row_sint, c).font = font_bold

            # Guarda os dados da Seção para gerar a aba Resumo
            dados_resumo_secoes.append({
                "secao_desc": f"{current_secao_code} - {current_secao_desc}".strip(" -"),
                "pares": pares,
                "rs_prev": rs_prev,
                "rs_real": rs_real,
                "rs_res": rs_res
            })

            target_row_sint += 1

    # Redimensionar colunas do Sintético
    for col in ws_sintetico.columns:
        col_letter = get_column_letter(col[0].column)
        max_len = 0
        for cell in col:
            val = str(cell.value or '')
            if cell.number_format and ('#' in cell.number_format or '0' in cell.number_format):
                val += "    "
            max_len = max(max_len, len(val))
        ws_sintetico.column_dimensions[col_letter].width = max(max_len + 3, 14)

    # =========================================================
    # PARTE 3: CRIAÇÃO E FORMATAÇÃO DA ABA RESUMO
    # =========================================================
    ws_resumo = wb.create_sheet(title="Resumo")

    # 4. Cabeçalho idêntico na linha 1 (#000000 com letras #FFFFFF)
    ws_resumo.append(headers)
    for c in range(1, 9):
        cell = ws_resumo.cell(1, c)
        cell.fill = fill_header
        cell.font = font_header
        cell.alignment = Alignment(horizontal="center", vertical="center")

    # Preenche cada seção com seus totais consolidados
    # (Sem linhas de Plano, sem linhas de Total Seção e sem cores nas células de dados)
    target_row_res = 2
    for item in dados_resumo_secoes:
        ws_resumo.cell(target_row_res, 1, value="Seção")
        ws_resumo.cell(target_row_res, 2, value=item["secao_desc"])
        ws_resumo.cell(target_row_res, 3, value=item["pares"])
        ws_resumo.cell(target_row_res, 4, value=item["rs_prev"])
        ws_resumo.cell(target_row_res, 5, value=item["rs_real"])
        ws_resumo.cell(target_row_res, 6, value=item["rs_res"])

        # Fórmulas de Média
        ws_resumo.cell(target_row_res, 7, value=f"=IF(C{target_row_res}>0, D{target_row_res}/C{target_row_res}, 0)")
        ws_resumo.cell(target_row_res, 8, value=f"=IF(C{target_row_res}>0, E{target_row_res}/C{target_row_res}, 0)")

        # Formatação numérica
        ws_resumo.cell(target_row_res, 3).number_format = fmt_milhar_int
        for c in range(4, 9):
            ws_resumo.cell(target_row_res, c).number_format = fmt_milhar_2dec

        target_row_res += 1

    # 5. Redimensionar colunas da aba Resumo
    for col in ws_resumo.columns:
        col_letter = get_column_letter(col[0].column)
        max_len = 0
        for cell in col:
            val = str(cell.value or '')
            if cell.number_format and ('#' in cell.number_format or '0' in cell.number_format):
                val += "    "
            max_len = max(max_len, len(val))
        ws_resumo.column_dimensions[col_letter].width = max(max_len + 3, 14)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output

# -------------------------------------------------------------
# RENDERIZAÇÃO DAS TELAS
# -------------------------------------------------------------
if pagina == "Início":
    st.title("Rotina: Relatório de Planos em Elaboração")
    st.markdown("""
    Esta aplicação automatiza a limpeza, formatação e síntese do relatório de **Planos em Elaboração**, gerando 3 visões:

    1. **Aba Analítico:**
        - Limpeza de cabeçalhos institucionais.
        - Destacamento visual de **Seção** (`#DAE9F8`) e **Plano** (`#DAF2D0`).
        - Aplicação de máscara de milhar e formatação de inteiros para pares.
    2. **Aba Sintético:**
        - Visão por Seção e Planos com totais de pares, previsto, realizado e resultado.
        - Cálculo automático de médias unitárias.
        - Destaque em `#DAE9F8` restrito à identificação da **Seção**.
    3. **Aba Resumo:**
        - Visão executiva apenas com o fechamento consolidado por **Seção**.
        - Linhas de planos e totais redundantes removidas.
        - Células sem preenchimento colorido para impressão/leitura limpa.
    """)
    st.info("Para iniciar, selecione **Processar Planilha** no menu lateral esquerdo.")

elif pagina == "Processar Planilha":
    st.title("Importação e Tratamento do Arquivo")
    st.write("Faça o upload do arquivo XLSX bruto emitido pelo sistema:")

    uploaded_file = st.file_uploader(
        "Selecione o arquivo Excel (.xlsx)",
        type=["xlsx"]
    )

    if uploaded_file is not None:
        st.success("Arquivo carregado com sucesso!")

        if st.button("Processar e Gerar Relatórios", type="primary"):
            with st.spinner("Processando abas Analítico, Sintético e Resumo..."):
                try:
                    processed_data = processar_planilha_planos(uploaded_file)
                    st.success("Processamento concluído com sucesso!")

                    st.download_button(
                        label="📥 Baixar Excel Completo (Analítico + Sintético + Resumo)",
                        data=processed_data,
                        file_name=f"Planos_Formatado_{uploaded_file.name}",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                except Exception as e:
                    st.error(f"Erro durante o processamento da planilha: {e}")