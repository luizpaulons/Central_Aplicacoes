import os
import pyodbc
import json
from io import BytesIO
import pandas as pd
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
import urllib.parse
from sqlalchemy import create_engine



st.set_page_config(page_title="PCP - Gestão de Solados e EVA", layout="wide")

ARQUIVO_DE_PARA = "de_para_solados_eva.csv"
ARQUIVO_CADASTROS = "cadastros_base.json"

# ==========================================================
# 1. FUNÇÕES DE BANCO DE DADOS (ERP SQL E TABELAS LOCAIS)
# ==========================================================

def obter_driver_compativel():
    """Detecta se o ambiente tem o driver do Linux (VPS) ou o do Windows."""
    drivers_instalados = pyodbc.drivers()
    preferencias = [
        "ODBC Driver 18 for SQL Server",
        "ODBC Driver 17 for SQL Server",
        "SQL Server"
    ]
    for d in preferencias:
        if d in drivers_instalados:
            return d
    return "SQL Server"

@st.cache_data(ttl=600)
def buscar_dados_base_sql():
    sec = st.secrets["sql_server_CHB"]
    
    # 1. Se estiver configurado por URL única:
    if "url" in sec and sec["url"]:
        conn_str = sec["url"]
    # 2. Se estiver configurado com parâmetros separados:
    else:
        host = sec.get("host") or sec.get("server", "")
        port = sec.get("port", 1433)
        database = sec.get("database", "CHB")
        username = sec.get("username", "")
        password = urllib.parse.quote_plus(str(sec.get("password", "")))
        
        # Detecta automaticamente se usa ODBC 18 (Linux) ou SQL Server (Windows)
        driver_real = obter_driver_compativel()
        driver_codificado = urllib.parse.quote_plus(driver_real)
        
        flags = "&TrustServerCertificate=yes" if "ODBC Driver" in driver_real else ""
        
        conn_str = (
            f"mssql+pyodbc://{username}:{password}@{host}:{port}/{database}"
            f"?driver={driver_codificado}{flags}"
        )
    
    engine = create_engine(conn_str)
    
    query = """
        SELECT 
            C.PC03Codigo AS Linha, 
            C.PC03Descr  AS Modelo, 
            B.PC10Codigo AS Cor, 
            B.PC10Descr  AS [Descrição Cor]
        FROM PC13T A
        INNER JOIN PC10T B ON (A.PC13Cor = B.PC10Codigo)
        INNER JOIN PC03T C ON (A.PC13Linha = C.PC03Codigo)
        WHERE A.PC13Emp08 = 1
          AND A.PC13AnoPed = 0
          AND A.PC13CodPed = 0
          AND C.PC03Codigo > 660
        GROUP BY C.PC03Codigo, C.PC03Descr, B.PC10Codigo, B.PC10Descr
        ORDER BY C.PC03Codigo, B.PC10Codigo
    """
    
    with engine.connect() as conexao:
        df = pd.read_sql_query(query, con=conexao)
        
    return df

def carregar_cadastros_base():
    if os.path.exists(ARQUIVO_CADASTROS):
        with open(ARQUIVO_CADASTROS, "r", encoding="utf-8") as f:
            dados = json.load(f)
            # Garante que cores_eva seja lista de dicionários
            cores_tratadas = []
            for item in dados.get("cores_eva", []):
                if isinstance(item, dict):
                    cores_tratadas.append(item)
                else:
                    cores_tratadas.append({"codigo": "", "cor": str(item)})
            dados["cores_eva"] = cores_tratadas
            return dados
            
    return {
        "solados": ["SKY", "TR TRATORADO", "ALPHA", "NEEVO", "DUNA"],
        "cores_eva": [
            {"codigo": "545", "cor": "PRETO"},
            {"codigo": "1214", "cor": "ARENITO"},
            {"codigo": "2125", "cor": "PRETO/CREPE"}
        ]
    }

def salvar_cadastros_base(cadastros):
    with open(ARQUIVO_CADASTROS, "w", encoding="utf-8") as f:
        json.dump(cadastros, f, ensure_ascii=False, indent=2)

def carregar_de_para():
    if os.path.exists(ARQUIVO_DE_PARA):
        return pd.read_csv(ARQUIVO_DE_PARA, dtype=str)
    return pd.DataFrame(columns=["linha", "modelo", "cor", "descricao_cor", "nome_solado", "cor_eva"])

def salvar_de_para(df_novos):
    df_existente = carregar_de_para()
    df_novos["linha"] = df_novos["linha"].astype(str).str.strip()
    df_novos["cor"] = df_novos["cor"].astype(str).str.strip()
    
    if not df_existente.empty:
        df_existente["linha"] = df_existente["linha"].astype(str).str.strip()
        df_existente["cor"] = df_existente["cor"].astype(str).str.strip()
        df_final = pd.concat([df_existente, df_novos]).drop_duplicates(subset=["linha", "cor"], keep="last")
    else:
        df_final = df_novos
        
    df_final.to_csv(ARQUIVO_DE_PARA, index=False)
    return df_final

def fmt_milhar(v):
    try:
        n = int(round(float(str(v).replace(".", "").replace(",", "."))))
        return f"{n:,}".replace(",", ".")
    except:
        return str(v)

# ==========================================================
# 2. CARREGAMENTO INICIAL DOS DADOS
# ==========================================================
cadastros_base = carregar_cadastros_base()

try:
    df_base_sql = buscar_dados_base_sql()
except Exception as e:
    st.sidebar.error(f"Erro na conexão SQL: {e}")
    df_base_sql = pd.DataFrame(columns=["Linha", "Modelo", "Cor", "Descrição Cor"])

if df_base_sql is not None and not df_base_sql.empty:
    df_base_sql["Linha"] = df_base_sql["Linha"].astype(str).str.strip()
    df_base_sql["Modelo"] = df_base_sql["Modelo"].astype(str).str.strip()
    df_base_sql["Cor"] = df_base_sql["Cor"].astype(str).str.strip()
    df_base_sql["Descrição Cor"] = df_base_sql["Descrição Cor"].astype(str).str.strip()
    
    # Mapeamento do código para descrição da cor
    mapa_codigo_cor = dict(zip(df_base_sql["Cor"], df_base_sql["Descrição Cor"]))
else:
    mapa_codigo_cor = {}

# Lista de opções para os dropdowns (evita vazios)
lista_solados_opcoes = sorted(cadastros_base.get("solados", []))
lista_cores_opcoes = sorted(list(set([c["cor"] for c in cadastros_base.get("cores_eva", []) if c.get("cor")])))

# ==========================================================
# 3. MENU LATERAL
# ==========================================================
st.sidebar.title("🏭 PCP CHB")
menu_selecionado = st.sidebar.radio(
    "Navegação:",
    ["📝 De-Para", "⚙️ Cadastro de Solados e Cores", "📑 Relatório e Resumos"]
)

# ==========================================================
# TELA 1: VÍNCULO DE-PARA (DIRETO DO BANCO SQL)
# ==========================================================
if menu_selecionado == "📝 De-Para":
    st.title("📝 Vínculo De-Para: Modelo e Cor x Solado e Cor do EVA")

    col_btn_sql, _ = st.columns([2, 5])
    with col_btn_sql:
        if st.button("🔄 Atualizar Dados do Banco SQL"):
            st.cache_data.clear()
            st.rerun()

    if df_base_sql is None or df_base_sql.empty:
        st.warning("Nenhum dado retornado do banco ou conexão não configurada no secrets.toml.")
    else:
        df_ref_mod = df_base_sql[["Linha", "Modelo"]].drop_duplicates()
        df_ref_mod = df_ref_mod.sort_values(
            by=["Linha"], 
            key=lambda s: s.map(lambda x: (0, int(x)) if str(x).isdigit() else (1, str(x)))
        )
        df_ref_mod["opcao"] = df_ref_mod["Linha"] + " - " + df_ref_mod["Modelo"]
        lista_opcoes = df_ref_mod["opcao"].tolist()

        col_f1, col_f2 = st.columns([3, 3])
        with col_f1:
            item_selecionado = st.selectbox("Selecione a Referência / Linha:", options=lista_opcoes)
            linha_selecionada = item_selecionado.split(" - ")[0].strip()
        with col_f2:
            modelos_encontrados = df_base_sql[df_base_sql["Linha"] == linha_selecionada]["Modelo"].unique()
            nome_modelo_sel = modelos_encontrados[0] if len(modelos_encontrados) > 0 else ""
            st.markdown(f"**REFERENCIA SELECIONADA:** `{linha_selecionada}`")
            st.markdown(f"**Modelo:** `{nome_modelo_sel}`")

        df_filtrado = df_base_sql[df_base_sql["Linha"] == linha_selecionada].drop_duplicates(subset=["Linha", "Cor"]).copy()

        df_de_para_atual = carregar_de_para()
        df_merge = pd.merge(
            df_filtrado, 
            df_de_para_atual.rename(columns={
                "linha": "Linha", 
                "cor": "Cor", 
                "nome_solado": "Nome do Solado", 
                "cor_eva": "Cor do EVA"
            })[["Linha", "Cor", "Nome do Solado", "Cor do EVA"]], 
            on=["Linha", "Cor"], 
            how="left"
        )
        df_merge["Nome do Solado"] = df_merge["Nome do Solado"].fillna("")
        df_merge["Cor do EVA"] = df_merge["Cor do EVA"].fillna("")
        df_merge["SEL"] = False

        chave_df = f"grid_trabalho_{linha_selecionada}"
        chave_master = f"master_check_{linha_selecionada}"

        if chave_df not in st.session_state:
            st.session_state[chave_df] = df_merge

        with st.expander("⚡ Preenchimento em LOTE para os itens marcados", expanded=True):
            col_l1, col_l2, col_l3 = st.columns([2, 2, 1])
            with col_l1:
                sol_lote = st.selectbox(
                    "Nome do Solado (Lote):", 
                    options=["ESCOLHA UMA OPÇÃO"] + lista_solados_opcoes,
                    key=f"sol_lote_{linha_selecionada}"
                )
            with col_l2:
                eva_lote = st.selectbox(
                    "Cor do EVA (Lote):", 
                    options=["ESCOLHA UMA OPÇÃO"] + lista_cores_opcoes,
                    key=f"eva_lote_{linha_selecionada}"
                )
            with col_l3:
                st.write("")
                st.write("")
                if st.button("Aplicar Lote", key=f"btn_lote_{linha_selecionada}"):
                    marcados = st.session_state[chave_df]["SEL"] == True
                    if marcados.any():
                        if sol_lote != "ESCOLHA UMA OPÇÃO":
                            st.session_state[chave_df].loc[marcados, "Nome do Solado"] = sol_lote
                        if eva_lote != "ESCOLHA UMA OPÇÃO":
                            st.session_state[chave_df].loc[marcados, "Cor do EVA"] = eva_lote
                        st.success(f"Aplicado com sucesso a {marcados.sum()} item(ns)!")
                        st.rerun()
                    else:
                        st.warning("Marque as caixas na coluna 'SEL' dos itens desejados.")

        def toggle_todos_cb():
            st.session_state[chave_df]["SEL"] = st.session_state[chave_master]

        st.checkbox("Marcar / Desmarcar Todos na Tabela", key=chave_master, on_change=toggle_todos_cb)

        grid_amigavel = st.data_editor(
            st.session_state[chave_df],
            column_order=["SEL", "Linha", "Modelo", "Cor", "Descrição Cor", "Nome do Solado", "Cor do EVA"],
            column_config={
                "SEL": st.column_config.CheckboxColumn("SEL", default=False, width="small"),
                "Linha": st.column_config.TextColumn("Linha", disabled=True, width="small"),
                "Modelo": st.column_config.TextColumn("Modelo", disabled=True, width="medium"),
                "Cor": st.column_config.TextColumn("Cor", disabled=True, width="small"),
                "Descrição Cor": st.column_config.TextColumn("Descrição Cor", disabled=True, width="large"),
                "Nome do Solado": st.column_config.SelectboxColumn(
                    "Nome do Solado",
                    options=[""] + lista_solados_opcoes,
                    width="medium",
                    required=False
                ),
                "Cor do EVA": st.column_config.SelectboxColumn(
                    "Cor do EVA",
                    options=[""] + lista_cores_opcoes,
                    width="medium",
                    required=False
                ),
            },
            hide_index=True,
            use_container_width=True,
            key=f"editor_{linha_selecionada}"
        )
        st.session_state[chave_df] = grid_amigavel

        if st.button("💾 Gravar Alterações no De-Para"):
            dados_salvar = grid_amigavel[["Linha", "Modelo", "Cor", "Descrição Cor", "Nome do Solado", "Cor do EVA"]].copy()
            dados_salvar = dados_salvar.rename(columns={
                "Linha": "linha",
                "Modelo": "modelo",
                "Cor": "cor",
                "Descrição Cor": "descricao_cor",
                "Nome do Solado": "nome_solado",
                "Cor do EVA": "cor_eva"
            })
            salvar_de_para(dados_salvar)
            st.success("Configurações gravadas com sucesso no De-Para!")

# ==========================================================
# TELA 2: CADASTRO DE SOLADOS E CORES DE EVA
# ==========================================================
elif menu_selecionado == "⚙️ Cadastro de Solados e Cores":
    st.title("⚙️ Cadastro Oficial de Solados e Cores de EVA")
    st.info("Cadastre solados ou informe o código da cor para puxar automaticamente a descrição oficial do banco SQL.")

    df_de_para_atual = carregar_de_para()
    solados_em_uso = set(df_de_para_atual["nome_solado"].dropna().astype(str).str.strip().str.upper()) if not df_de_para_atual.empty else set()
    cores_em_uso = set(df_de_para_atual["cor_eva"].dropna().astype(str).str.strip().str.upper()) if not df_de_para_atual.empty else set()

    col_cad1, col_cad2 = st.columns(2)

    # CADASTRO DE SOLADOS
    with col_cad1:
        st.markdown("### 👟 Solados")
        
        with st.form("form_add_solado", clear_on_submit=True):
            novo_solado = st.text_input("Novo Solado:", placeholder="Ex: TR TRATORADO").strip().upper()
            btn_add_s = st.form_submit_button("➕ Adicionar Solado")
            if btn_add_s:
                if novo_solado and novo_solado not in cadastros_base["solados"]:
                    cadastros_base["solados"].append(novo_solado)
                    cadastros_base["solados"].sort()
                    salvar_cadastros_base(cadastros_base)
                    st.success(f"Solado '{novo_solado}' cadastrado!")
                    st.rerun()
                elif novo_solado in cadastros_base["solados"]:
                    st.warning("Este solado já existe.")

        df_grid_sol = pd.DataFrame([
            {"Selecionar": False, "Nome do Solado": s} for s in cadastros_base.get("solados", [])
        ]) if cadastros_base.get("solados") else pd.DataFrame(columns=["Selecionar", "Nome do Solado"])

        df_grid_sol["Selecionar"] = df_grid_sol["Selecionar"].astype(bool)
        df_grid_sol["Nome do Solado"] = df_grid_sol["Nome do Solado"].astype(str)

        grid_sol_editada = st.data_editor(
            df_grid_sol,
            column_config={
                "Selecionar": st.column_config.CheckboxColumn("Selecionar", default=False, width="small"),
                "Nome do Solado": st.column_config.TextColumn("Nome do Solado", disabled=True, width="large"),
            },
            hide_index=True,
            use_container_width=True,
            key="grid_solados_exclusao"
        )

        if st.button("🗑️ Excluir Solados Selecionados"):
            selecionados = grid_sol_editada[grid_sol_editada["Selecionar"] == True]["Nome do Solado"].tolist()
            if not selecionados:
                st.warning("Marque ao menos um solado na coluna 'Selecionar'.")
            else:
                bloqueados = [s for s in selecionados if s in solados_em_uso]
                permitidos = [s for s in selecionados if s not in solados_em_uso]

                if bloqueados:
                    modelos_usando = df_de_para_atual[df_de_para_atual["nome_solado"].str.upper().isin(bloqueados)][["linha", "cor", "nome_solado"]].drop_duplicates()
                    linhas_afetadas = ", ".join([f"Linha {r['linha']} (Cor {r['cor']})" for _, r in modelos_usando.iterrows()])
                    st.error(f"❌ Não é possível excluir {', '.join(bloqueados)}. Em uso em: {linhas_afetadas}.")

                if permitidos:
                    cadastros_base["solados"] = [s for s in cadastros_base["solados"] if s not in permitidos]
                    salvar_cadastros_base(cadastros_base)
                    st.success(f"Solado(s) removido(s): {', '.join(permitidos)}.")
                    st.rerun()

    # CADASTRO DE CORES DE EVA USANDO O BANCO SQL
    with col_cad2:
        st.markdown("### 🎨 Cores de EVA")
        
        col_c_in, col_c_desc = st.columns([1, 2])
        with col_c_in:
            cod_digitado = st.text_input("Código da Cor:", placeholder="Ex: 545", key="input_cod_cor_eva").strip()
        with col_c_desc:
            desc_buscada = mapa_codigo_cor.get(cod_digitado, "")
            st.text_input("Descrição (Banco SQL):", value=desc_buscada, disabled=True)

        if st.button("➕ Adicionar Cor", key="btn_add_cor"):
            if not cod_digitado:
                st.warning("Digite o código da cor.")
            elif not desc_buscada:
                st.error(f"Código {cod_digitado} não foi encontrado no banco de dados SQL.")
            else:
                codigos_existentes = [str(item.get("codigo", "")).strip() for item in cadastros_base["cores_eva"]]
                cores_existentes = [str(item.get("cor", "")).strip().upper() for item in cadastros_base["cores_eva"]]

                if cod_digitado in codigos_existentes or desc_buscada.upper() in cores_existentes:
                    st.warning("Esta cor/código já está cadastrada.")
                else:
                    cadastros_base["cores_eva"].append({
                        "codigo": cod_digitado,
                        "cor": desc_buscada.upper()
                    })
                    cadastros_base["cores_eva"] = sorted(cadastros_base["cores_eva"], key=lambda x: x["cor"])
                    salvar_cadastros_base(cadastros_base)
                    st.success(f"Cor '{desc_buscada.upper()}' (Cód. {cod_digitado}) cadastrada com sucesso!")
                    st.rerun()

        df_grid_cor = pd.DataFrame([
            {"Selecionar": False, "Codigo": c.get("codigo", ""), "Cor": c.get("cor", "")}
            for c in cadastros_base.get("cores_eva", [])
        ]) if cadastros_base.get("cores_eva") else pd.DataFrame(columns=["Selecionar", "Codigo", "Cor"])

        df_grid_cor["Selecionar"] = df_grid_cor["Selecionar"].astype(bool)
        df_grid_cor["Codigo"] = df_grid_cor["Codigo"].astype(str)
        df_grid_cor["Cor"] = df_grid_cor["Cor"].astype(str)

        grid_cor_editada = st.data_editor(
            df_grid_cor,
            column_config={
                "Selecionar": st.column_config.CheckboxColumn("Selecionar", default=False, width="small"),
                "Codigo": st.column_config.TextColumn("Codigo", disabled=True, width="small"),
                "Cor": st.column_config.TextColumn("Cor", disabled=True, width="large"),
            },
            hide_index=True,
            use_container_width=True,
            key="grid_cores_exclusao"
        )

        if st.button("🗑️ Excluir Cores Selecionadas"):
            selecionadas = grid_cor_editada[grid_cor_editada["Selecionar"] == True]["Cor"].tolist()
            if not selecionadas:
                st.warning("Marque ao menos uma cor na coluna 'Selecionar'.")
            else:
                bloqueadas = [c for c in selecionadas if c in cores_em_uso]
                permitidas = [c for c in selecionadas if c not in cores_em_uso]

                if bloqueadas:
                    modelos_usando_cor = df_de_para_atual[df_de_para_atual["cor_eva"].str.upper().isin(bloqueadas)][["linha", "cor", "cor_eva"]].drop_duplicates()
                    linhas_afetadas_cor = ", ".join([f"Linha {r['linha']} (Cor {r['cor']})" for _, r in modelos_usando_cor.iterrows()])
                    st.error(f"❌ Não é possível excluir {', '.join(bloqueadas)}. Em uso em: {linhas_afetadas_cor}.")

                if permitidas:
                    cadastros_base["cores_eva"] = [c for c in cadastros_base["cores_eva"] if c["cor"] not in permitidas]
                    salvar_cadastros_base(cadastros_base)
                    st.success(f"Cor(es) removida(s): {', '.join(permitidas)}.")
                    st.rerun()

# ==========================================================
# TELA 3: RELATÓRIO CHB (PDF E EXCEL COM RESUMOS)
# ==========================================================
elif menu_selecionado == "📑 Relatório e Resumos":
    st.title("📑 Personalização de Relatório CHB")
    arquivo_excel = st.file_uploader("Selecione o arquivo Excel do relatório CHB (.xlsx):", type=["xlsx", "xls"])
    
    if arquivo_excel:
        if st.button("🚀 Processar e Gerar Relatórios"):
            with st.spinner("Processando dados e gerando arquivos..."):
                df_cadastros = carregar_de_para()
                mapa_de_para = {}
                if not df_cadastros.empty:
                    for _, r in df_cadastros.iterrows():
                        chave = (str(r["linha"]).strip(), str(r["cor"]).strip())
                        mapa_de_para[chave] = {
                            "solado": str(r.get("nome_solado", "")).strip(),
                            "eva": str(r.get("cor_eva", "")).strip()
                        }

                df_raw = pd.read_excel(arquivo_excel, header=None)
                empresa_nome = "1 LYND CALCADOS LTDA"
                total_geral_num = 0
                modelos_processados = []
                modelo_atual_obj = None

                resumo_solado_eva = {}
                resumo_cor_total = {}

                for idx, row in df_raw.iterrows():
                    col0 = str(row[0]).strip() if pd.notna(row[0]) else ""
                    col1 = str(row[1]).strip() if pd.notna(row[1]) else ""
                    col2 = str(row[2]).strip() if pd.notna(row[2]) else ""
                    col4 = str(row[4]).strip() if pd.notna(row[4]) else ""
                    col5 = str(row[5]).strip() if pd.notna(row[5]) else ""
                    col6 = str(row[6]).strip() if pd.notna(row[6]) else ""

                    if "EMPRESA:" in col0.upper() and col2:
                        empresa_nome = col2

                    col9 = str(row[9]).strip() if len(row) > 9 and pd.notna(row[9]) else ""
                    col10 = str(row[10]).strip() if len(row) > 10 and pd.notna(row[10]) else ""
                    if "TOTAL" in col9.upper():
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

                        resumo_solado_eva[(solado_nome, eva_nome)] = resumo_solado_eva.get((solado_nome, eva_nome), 0) + pares_num
                        resumo_cor_total[eva_nome] = resumo_cor_total.get(eva_nome, 0) + pares_num

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

                soma_resumo = sum(resumo_cor_total.values())
                divisor_perc = total_geral_num if total_geral_num > 0 else soma_resumo

                # GERAR PDF
                buffer_pdf = BytesIO()
                doc = SimpleDocTemplate(
                    buffer_pdf,
                    pagesize=landscape(letter),
                    leftMargin=18, rightMargin=18, topMargin=18, bottomMargin=18
                )

                est_header = ParagraphStyle('CHB_H', fontName='Courier-Bold', fontSize=8, leading=9)
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
                        
                        eva_n = c["cor_eva"].strip().upper() if c["cor_eva"].strip() else "SEM EVA"
                        subtotais_eva[eva_n] = subtotais_eva.get(eva_n, 0) + c["pares"]

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

                # RESUMO 1: MODELO COM TOTAL FORMATADO EM MILHAR
                elementos.append(Spacer(1, 16))
                elementos.append(Paragraph("<b>1. RESUMO POR MODELO (SOLADO E CORES DE EVA)</b>", est_header))
                elementos.append(Spacer(1, 4))

                linhas_res_mod = [[
                    Paragraph("<b>Linha / Modelo</b>", est_header),
                    Paragraph("<b>Solado</b>", est_header),
                    Paragraph("<b>Cor do EVA</b>", est_header),
                    Paragraph("<b>Quantidade (Pares)</b>", est_header),
                    Paragraph("<b>Total Modelo</b>", est_header)
                ]]

                estilo_res_mod = [
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#34495E")),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('TOPPADDING', (0, 0), (-1, -1), 2),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#BDC3C7")),
                ]

                r_mod_idx = 1
                for mod_obj in modelos_processados:
                    sub_eva_mod = {}
                    solados_mod = set()
                    for c in mod_obj["cores"]:
                        eva_n = c["cor_eva"].strip().upper() if c["cor_eva"].strip() else "SEM EVA"
                        sol_n = c["solado"].strip().upper() if c["solado"].strip() else "SEM SOLADO"
                        sub_eva_mod[eva_n] = sub_eva_mod.get(eva_n, 0) + c["pares"]
                        solados_mod.add(sol_n)
                    
                    solados_str = ", ".join(sorted(solados_mod)) if solados_mod else "-"
                    itens_eva_mod = sorted(sub_eva_mod.items(), key=lambda x: x[1], reverse=True)
                    
                    primeiro = True
                    for eva_n, qtd_n in itens_eva_mod:
                        linhas_res_mod.append([
                            Paragraph(f"<b>Modelo {mod_obj['linha']} ({mod_obj['nome']})</b>" if primeiro else "", est_text),
                            Paragraph(solados_str if primeiro else "", est_text),
                            Paragraph(eva_n, est_text),
                            Paragraph(fmt_milhar(qtd_n), est_right),
                            Paragraph(f"<b>Total: {fmt_milhar(mod_obj['pares_total'])}</b>" if primeiro else "", est_right_bold)
                        ])
                        primeiro = False
                        r_mod_idx += 1

                tab_res_mod = Table(linhas_res_mod, colWidths=[180, 120, 140, 120, 120])
                tab_res_mod.setStyle(TableStyle(estilo_res_mod))
                elementos.append(tab_res_mod)

                # RESUMO 2: SOLADO
                elementos.append(Spacer(1, 16))
                elementos.append(Paragraph("<b>2. RESUMO: ORDEM ALFABÉTICA POR SOLADO</b> (SEM SOLADO NA PRIMEIRA LINHA)", est_header))
                elementos.append(Spacer(1, 4))

                linhas_t1 = [[
                    Paragraph("<b>Solado</b>", est_header),
                    Paragraph("<b>Cor do EVA</b>", est_header),
                    Paragraph("<b>Total Pares</b>", est_header),
                    Paragraph("<b>(%) Geral</b>", est_header)
                ]]

                estilo_t1 = [
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('TOPPADDING', (0, 0), (-1, -1), 2),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#BDC3C7")),
                ]

                itens_resumo_solado = sorted(
                    resumo_solado_eva.items(), 
                    key=lambda x: (0 if x[0][0] == "SEM SOLADO" else 1, x[0][0], x[0][1])
                )

                r_idx = 1
                for (sol, eva), qtd in itens_resumo_solado:
                    perc = (qtd / divisor_perc * 100) if divisor_perc > 0 else 0
                    linhas_t1.append([
                        Paragraph(f"<b>{sol}</b>", est_text),
                        Paragraph(eva, est_text),
                        Paragraph(f"<b>{fmt_milhar(qtd)}</b>", est_right),
                        Paragraph(f"{perc:.2f}%".replace(".", ","), est_right)
                    ])
                    if sol == "SEM SOLADO":
                        estilo_t1.append(('BACKGROUND', (0, r_idx), (-1, r_idx), colors.HexColor("#FADBD8")))
                    r_idx += 1

                linhas_t1.append([
                    Paragraph("<b>TOTAL</b>", est_text_bold),
                    Paragraph("", est_text),
                    Paragraph(f"<b>{fmt_milhar(soma_resumo)}</b>", est_right_bold),
                    Paragraph("<b>100,00%</b>", est_right_bold)
                ])
                estilo_t1.append(('BACKGROUND', (0, r_idx), (-1, r_idx), colors.HexColor("#EAEDED")))

                tab_resumo_sol = Table(linhas_t1, colWidths=[200, 200, 100, 80])
                tab_resumo_sol.setStyle(TableStyle(estilo_t1))
                elementos.append(tab_resumo_sol)

                # RESUMO 3: POR COR DO EVA
                elementos.append(Spacer(1, 16))
                elementos.append(Paragraph("<b>3. RESUMO: QUANTIDADE TOTAL POR COR DO EVA</b> (ORDEM ALFABÉTICA)", est_header))
                elementos.append(Spacer(1, 4))

                linhas_t2 = [[
                    Paragraph("<b>Cor do EVA</b>", est_header),
                    Paragraph("<b>Total Pares</b>", est_header),
                    Paragraph("<b>(%) Geral</b>", est_header)
                ]]

                estilo_t2 = [
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1A5276")),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('TOPPADDING', (0, 0), (-1, -1), 2),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#BDC3C7")),
                ]

                itens_resumo_cor = sorted(
                    resumo_cor_total.items(), 
                    key=lambda x: (0 if x[0] == "SEM EVA" else 1, x[0])
                )

                r_idx2 = 1
                for eva, qtd in itens_resumo_cor:
                    perc = (qtd / divisor_perc * 100) if divisor_perc > 0 else 0
                    linhas_t2.append([
                        Paragraph(f"<b>{eva}</b>", est_text),
                        Paragraph(f"<b>{fmt_milhar(qtd)}</b>", est_right),
                        Paragraph(f"{perc:.2f}%".replace(".", ","), est_right)
                    ])
                    if eva == "SEM EVA":
                        estilo_t2.append(('BACKGROUND', (0, r_idx2), (-1, r_idx2), colors.HexColor("#FADBD8")))
                    r_idx2 += 1

                linhas_t2.append([
                    Paragraph("<b>TOTAL GERAL EVA</b>", est_text_bold),
                    Paragraph(f"<b>{fmt_milhar(soma_resumo)}</b>", est_right_bold),
                    Paragraph("<b>100,00%</b>", est_right_bold)
                ])
                estilo_t2.append(('BACKGROUND', (0, r_idx2), (-1, r_idx2), colors.HexColor("#EAEDED")))

                tab_resumo_cor = Table(linhas_t2, colWidths=[320, 140, 120])
                tab_resumo_cor.setStyle(TableStyle(estilo_t2))
                elementos.append(tab_resumo_cor)

                doc.build(elementos)
                buffer_pdf.seek(0)

                # GERAR EXCEL COM 4 ABAS
                buffer_excel = BytesIO()
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
                        eva_n = c["cor_eva"].strip().upper() if c["cor_eva"].strip() else "SEM EVA"
                        subtotais_eva[eva_n] = subtotais_eva.get(eva_n, 0) + c["pares"]

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

                linhas_excel_res_mod = []
                for mod_obj in modelos_processados:
                    sub_eva_mod = {}
                    solados_mod = set()
                    for c in mod_obj["cores"]:
                        eva_n = c["cor_eva"].strip().upper() if c["cor_eva"].strip() else "SEM EVA"
                        sol_n = c["solado"].strip().upper() if c["solado"].strip() else "SEM SOLADO"
                        sub_eva_mod[eva_n] = sub_eva_mod.get(eva_n, 0) + c["pares"]
                        solados_mod.add(sol_n)
                    
                    solados_str = ", ".join(sorted(solados_mod)) if solados_mod else "-"
                    for eva_n, qtd_n in sorted(sub_eva_mod.items(), key=lambda x: x[1], reverse=True):
                        linhas_excel_res_mod.append({
                            "Linha": mod_obj["linha"],
                            "Modelo": mod_obj["nome"],
                            "Solado": solados_str,
                            "Cor do EVA": eva_n,
                            "Quantidade (Pares)": qtd_n,
                            "Total Modelo": mod_obj["pares_total"]
                        })

                linhas_excel_sol = []
                for (sol, eva), qtd in itens_resumo_solado:
                    perc = (qtd / divisor_perc * 100) if divisor_perc > 0 else 0
                    linhas_excel_sol.append({
                        "Solado": sol,
                        "Cor do EVA": eva,
                        "Total Pares": qtd,
                        "(%) Geral": f"{perc:.2f}%".replace(".", ",")
                    })
                linhas_excel_sol.append({
                    "Solado": "TOTAL CONSOLIDADO",
                    "Cor do EVA": "",
                    "Total Pares": soma_resumo,
                    "(%) Geral": "100,00%"
                })

                linhas_excel_cor = []
                for eva, qtd in itens_resumo_cor:
                    perc = (qtd / divisor_perc * 100) if divisor_perc > 0 else 0
                    linhas_excel_cor.append({
                        "Cor do EVA": eva,
                        "Total Pares": qtd,
                        "(%) Geral": f"{perc:.2f}%".replace(".", ",")
                    })
                linhas_excel_cor.append({
                    "Cor do EVA": "TOTAL GERAL EVA",
                    "Total Pares": soma_resumo,
                    "(%) Geral": "100,00%"
                })

                with pd.ExcelWriter(buffer_excel, engine='openpyxl') as writer:
                    pd.DataFrame(linhas_excel).to_excel(writer, index=False, sheet_name="Estatistica Detalhada")
                    pd.DataFrame(linhas_excel_res_mod).to_excel(writer, index=False, sheet_name="Resumo por Modelo")
                    pd.DataFrame(linhas_excel_sol).to_excel(writer, index=False, sheet_name="Resumo por Solado")
                    pd.DataFrame(linhas_excel_cor).to_excel(writer, index=False, sheet_name="Resumo Total por Cor")
                buffer_excel.seek(0)

                st.success("Relatórios gerados com sucesso!")

                col_d1, col_d2 = st.columns(2)
                with col_d1:
                    st.download_button(
                        label="📄 Baixar PDF com Todos os Resumos",
                        data=buffer_pdf,
                        file_name="Estatistica_Modelo_CHB_Resumos.pdf",
                        mime="application/pdf"
                    )
                with col_d2:
                    st.download_button(
                        label="📊 Baixar Excel com Abas de Resumo",
                        data=buffer_excel,
                        file_name="Estatistica_Modelo_CHB_Resumos.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )