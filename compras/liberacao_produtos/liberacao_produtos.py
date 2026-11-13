import streamlit as st
import pandas as pd
import pyodbc
import re
import os
from pathlib import Path
from datetime import datetime
from pypdf import PdfReader
from dotenv import load_dotenv

# Carrega o .env da pasta atual ou da pasta raiz 'Central'
load_dotenv()
caminho_env_raiz = Path(__file__).resolve().parent.parent.parent / ".env"
if caminho_env_raiz.exists():
    load_dotenv(dotenv_path=caminho_env_raiz)


# -------------------------------------------------------------
# CONEXÃO COM O BANCO DE DADOS (VIA .ENV)
# -------------------------------------------------------------
def get_connection():
    cfg = {
        "dialect": os.getenv("DB_DIALECT", "mssql"),
        "driver": os.getenv("DB_DRIVER", "ODBC Driver 18 for SQL Server"),
        "host": os.getenv("DB_HOST", "localhost"),
        "port": int(os.getenv("DB_PORT", 1433)),
        "database": os.getenv("DB_NAME", "CHB"),
        "username": os.getenv("DB_USER", ""),
        "password": os.getenv("DB_PASS", ""),
    }

    host = cfg.get("host") or "localhost"
    port = cfg.get("port", 1433)
    server_str = f"{host},{port}" if port else host

    drivers_disponiveis = pyodbc.drivers()
    driver_solicitado = cfg.get("driver", "").replace("+", " ").strip()

    driver_escolhido = None
    if driver_solicitado and driver_solicitado in drivers_disponiveis:
        driver_escolhido = f"{{{driver_solicitado}}}"
    else:
        for d in [
            "ODBC Driver 18 for SQL Server",
            "ODBC Driver 17 for SQL Server",
            "SQL Server Native Client 11.0",
            "SQL Server",
        ]:
            if d in drivers_disponiveis:
                driver_escolhido = f"{{{d}}}"
                break

    if not driver_escolhido:
        raise RuntimeError(
            f"Nenhum driver compatível com SQL Server encontrado. Drivers instalados: {drivers_disponiveis}"
        )

    conn_str = (
        f"DRIVER={driver_escolhido};"
        f"SERVER={server_str};"
        f"DATABASE={cfg['database']};"
        f"UID={cfg['username']};"
        f"PWD={cfg['password']};"
    )
    if "ODBC Driver" in driver_escolhido:
        conn_str += "TrustServerCertificate=yes;"

    return pyodbc.connect(conn_str)


# -------------------------------------------------------------
# FUNÇÕES DE BANCO DE DADOS
# -------------------------------------------------------------
def buscar_dados_banco(codigos: list[str]) -> pd.DataFrame:
    if not codigos:
        return pd.DataFrame()

    codigos_formatados = ", ".join(f"'{c}'" for c in codigos)
    query = f"""
    SELECT 
        co13CodPro, 
        co13descri, 
        co13Bloq, 
        co13PCoMax, 
        co13PCoMin, 
        co13UlCus1, 
        co13UlCus2 
    FROM CO13T
    WHERE co13Emp06 = 1
      AND co13CodPro IN ({codigos_formatados})
    ORDER BY co13CodPro;
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        colunas = [col[0].strip() for col in cursor.description]
        registros = cursor.fetchall()

        dados = []
        for row in registros:
            linha_dict = dict(zip(colunas, row))
            linha_dict["Selecionar"] = True
            linha_dict["co13CodPro"] = str(linha_dict.get("co13CodPro", "")).strip()
            linha_dict["co13descri"] = str(linha_dict.get("co13descri", "")).strip()
            linha_dict["co13Bloq"] = (
                str(linha_dict.get("co13Bloq", "N")).strip().upper()
            )
            linha_dict["co13PCoMax"] = float(linha_dict.get("co13PCoMax") or 0.0)
            linha_dict["co13PCoMin"] = float(linha_dict.get("co13PCoMin") or 0.0)
            linha_dict["co13UlCus1"] = float(linha_dict.get("co13UlCus1") or 0.0)
            linha_dict["co13UlCus2"] = float(linha_dict.get("co13UlCus2") or 0.0)
            dados.append(linha_dict)

        df = pd.DataFrame(dados)
        if not df.empty:
            cols_ordem = [
                "Selecionar",
                "co13CodPro",
                "co13descri",
                "co13Bloq",
                "co13PCoMax",
                "co13PCoMin",
                "co13UlCus1",
                "co13UlCus2",
            ]
            df = df[cols_ordem]
        return df


def gravar_alteracoes_banco(comandos_update: list[str]):
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            for sql in comandos_update:
                cursor.execute(sql)
            conn.commit()
            return True, None
        except Exception as e:
            conn.rollback()
            return False, str(e)


# -------------------------------------------------------------
# FUNÇÕES DE EXTRAÇÃO DE CÓDIGOS
# -------------------------------------------------------------
def extrair_codigos_de_texto(texto: str) -> list[str]:
    if not texto:
        return []
    linhas = texto.splitlines()
    codigos = []
    padrao_inicio = re.compile(r"^\s*(\d{5,8})\b")
    for linha in linhas:
        match = padrao_inicio.match(linha)
        if match:
            codigos.append(match.group(1))
    if not codigos:
        codigos = re.findall(r"\b\d{5,8}\b", texto)
    return list(dict.fromkeys(codigos))


def extrair_codigos_arquivo(uploaded_file) -> list[str]:
    nome = uploaded_file.name.lower()
    codigos = []
    try:
        if nome.endswith((".xlsx", ".xls", ".ods", ".odf")):
            df = pd.read_excel(uploaded_file, header=None)
            for col in df.columns:
                amostra = df[col].dropna().astype(str)
                encontrados = [
                    re.search(r"^\d{5,8}$", str(val).strip()).group(0)
                    for val in amostra
                    if re.search(r"^\d{5,8}$", str(val).strip())
                ]
                if len(encontrados) >= max(1, int(len(amostra) * 0.4)):
                    codigos.extend(encontrados)
                    break
        elif nome.endswith(".pdf"):
            reader = PdfReader(uploaded_file)
            texto_completo = "".join(
                [(page.extract_text() or "") + "\n" for page in reader.pages]
            )
            codigos = extrair_codigos_de_texto(texto_completo)
        elif nome.endswith((".txt", ".csv")):
            conteudo = uploaded_file.read().decode("utf-8", errors="ignore")
            codigos = extrair_codigos_de_texto(conteudo)
    except Exception as e:
        st.error(f"Erro ao processar arquivo: {e}")
    return list(dict.fromkeys(codigos))


# -------------------------------------------------------------
# FUNÇÃO DE MONTAGEM DE ALTERAÇÕES
# -------------------------------------------------------------
def montar_alteracoes(
    df_orig,
    df_fim,
    alt_bloq,
    alt_max,
    alt_min,
    alt_cus1,
    alt_cus2,
    sincronizar_precos,
    sincronizar_custos,
):
    updates_sql = []
    linhas_log = []
    resumo_mudancas = []
    total_alterados = 0

    for _, row_fim in df_fim.iterrows():
        if not row_fim["Selecionar"]:
            continue

        orig_filtro = df_orig.loc[df_orig["co13CodPro"] == row_fim["co13CodPro"]]
        if orig_filtro.empty:
            continue
        row_orig = orig_filtro.iloc[0]

        sets = []
        mudancas = []

        if alt_bloq and str(row_fim["co13Bloq"]) != str(row_orig["co13Bloq"]):
            sets.append(f"co13Bloq = '{row_fim['co13Bloq']}'")
            mudancas.append(
                f"Bloqueado: De [{row_orig['co13Bloq']}] Para [{row_fim['co13Bloq']}]"
            )

        if alt_max and float(row_fim["co13PCoMax"]) != float(row_orig["co13PCoMax"]):
            sets.append(f"co13PCoMax = {row_fim['co13PCoMax']:.2f}")
            mudancas.append(
                f"Preço Máximo: De [{row_orig['co13PCoMax']:.2f}] Para [{row_fim['co13PCoMax']:.2f}]"
            )

        if (alt_min or sincronizar_precos) and float(row_fim["co13PCoMin"]) != float(
            row_orig["co13PCoMin"]
        ):
            sets.append(f"co13PCoMin = {row_fim['co13PCoMin']:.2f}")
            mudancas.append(
                f"Preço Mínimo: De [{row_orig['co13PCoMin']:.2f}] Para [{row_fim['co13PCoMin']:.2f}]"
            )

        if alt_cus1 and float(row_fim["co13UlCus1"]) != float(row_orig["co13UlCus1"]):
            sets.append(f"co13UlCus1 = {row_fim['co13UlCus1']:.2f}")
            mudancas.append(
                f"Último Custo: De [{row_orig['co13UlCus1']:.2f}] Para [{row_fim['co13UlCus1']:.2f}]"
            )

        if (alt_cus2 or sincronizar_custos) and float(row_fim["co13UlCus2"]) != float(
            row_orig["co13UlCus2"]
        ):
            sets.append(f"co13UlCus2 = {row_fim['co13UlCus2']:.2f}")
            mudancas.append(
                f"Último Valor Pago: De [{row_orig['co13UlCus2']:.2f}] Para [{row_fim['co13UlCus2']:.2f}]"
            )

        if sets:
            total_alterados += 1
            cmd_sql = f"UPDATE CO13T SET {', '.join(sets)} WHERE co13Emp06 = 1 AND co13CodPro = '{row_fim['co13CodPro']}';"
            updates_sql.append(cmd_sql)

            linhas_log.append(
                f"\nProduto: {row_fim['co13CodPro']} - {row_fim['co13descri']}"
            )
            for m in mudancas:
                linhas_log.append(f"  • {m}")
            linhas_log.append(f"  SQL: {cmd_sql}")

            resumo_mudancas.append(
                {
                    "Código": row_fim["co13CodPro"],
                    "Descrição": row_fim["co13descri"],
                    "Alterações": " | ".join(mudancas),
                }
            )

    return updates_sql, linhas_log, resumo_mudancas, total_alterados


# -------------------------------------------------------------
# MODAL DE CONFIRMAÇÃO DE GRAVAÇÃO
# -------------------------------------------------------------
@st.dialog("⚠️ Confirmação de Gravação no Banco de Dados", width="large")
def confirmar_gravacao_dialog(
    updates_sql, linhas_log, resumo_mudancas, total_alterados
):
    st.write(
        f"Você está prestes a atualizar **{total_alterados} produto(s)** na tabela `CO13T` (Empresa 1)."
    )
    st.warning(
        "Confira abaixo a lista detalhada do que será alterado antes de confirmar a execução:"
    )

    df_resumo = pd.DataFrame(resumo_mudancas)
    st.dataframe(df_resumo, use_container_width=True, hide_index=True)

    col_conf1, col_conf2 = st.columns(2)

    with col_conf1:
        if st.button(
            "✅ Sim, Gravar Alterações Agora", type="primary", use_container_width=True
        ):
            timestamp_nome = datetime.now().strftime("%Y%m%d%H%M")
            timestamp_log = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

            cabecalho_log = (
                [
                    "LOG DE ALTERAÇÕES - CO13T",
                    f"Data/Hora: {timestamp_log}",
                    "Empresa: 1",
                    "=" * 60,
                ]
                + linhas_log
                + ["\n" + "=" * 60, f"Total de registros alterados: {total_alterados}"]
            )

            with st.spinner("Gravando alterações no banco de dados..."):
                sucesso, erro = gravar_alteracoes_banco(updates_sql)

            if sucesso:
                st.session_state["msg_sucesso"] = (
                    f"✓ {total_alterados} registro(s) gravado(s) com sucesso no SQL Server!"
                )
                st.session_state["conteudo_log"] = "\n".join(cabecalho_log)
                st.session_state["conteudo_sql_exec"] = (
                    "BEGIN TRANSACTION;\n\n" + "\n".join(updates_sql) + "\n\nCOMMIT;"
                )
                st.session_state["log_filename"] = f"{timestamp_nome}.txt"
                st.session_state["sql_filename"] = f"update_{timestamp_nome}.sql"
                st.session_state["df_original"] = st.session_state["df_editado"].copy()
                st.session_state["script_sql_previo"] = None
                st.rerun()
            else:
                st.error(f"Erro ao gravar no banco: {erro}. Rollback realizado.")

    with col_conf2:
        if st.button("❌ Cancelar", use_container_width=True):
            st.rerun()


# -------------------------------------------------------------
# INICIALIZAÇÃO DE ESTADO
# -------------------------------------------------------------
if "codigos_texto" not in st.session_state:
    st.session_state["codigos_texto"] = ""
if "df_editado" not in st.session_state:
    st.session_state["df_editado"] = None
if "df_original" not in st.session_state:
    st.session_state["df_original"] = None
if "script_sql_previo" not in st.session_state:
    st.session_state["script_sql_previo"] = None

# -------------------------------------------------------------
# MENU LATERAL (SIDEBAR COM BOTÃO RADIO)
# -------------------------------------------------------------
with st.sidebar:
    st.title("⚙️ Módulo de Produtos")
    st.caption("Central de Compras & Precificação")

    pagina = st.radio("Navegação:", ["📖 Início", "📦 Manutenção e Liberação"], index=0)

    st.divider()
    st.markdown("""
        **Configuração do Ambiente:**
        - **Origem Configuração:** Arquivo `.env`
        - **Empresa:** 1
        - **Tabela:** `CO13T`
        """)

# =============================================================
# PÁGINA 1: Início
# =============================================================
if pagina == "📖 Início":
    st.title("📖 Início")
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
        1. Acesse o menu lateral esquerdo e clique em **📦 Manutenção e Liberação**.
        2. **Carregar Códigos:** Faça o upload do arquivo recebido (ou cole os códigos no campo de texto).
        3. **Consultar:** Clique em *Executar Consulta no Banco de Dados* para carregar os dados atuais.
        4. **Habilitar Alterações:** Marque os checkboxes dos campos que deseja alterar no topo da grade.
        5. **Editar:** Altere diretamente nas células da tabela ou use o painel *Preenchimento Rápido em Lote*.
        6. **Validar:** Clique em *Gerar Query UPDATE (Validação)* para conferir o script antes de afetar o banco.
        7. **Gravar:** Clique em *Confirmar e Gravar no Banco de Dados* para revisar o De/Para e gerar o log `.txt`.
        """)

# =============================================================
# PÁGINA 2: MANUTENÇÃO E LIBERAÇÃO
# =============================================================
elif pagina == "📦 Manutenção e Liberação":
    st.title("📦 Manutenção em Lote - Tabela CO13T")

    if "msg_sucesso" in st.session_state:
        st.success(st.session_state["msg_sucesso"])
        c_d1, c_d2 = st.columns(2)
        c_d1.download_button(
            label="📄 Baixar Arquivo de Log (.txt)",
            data=st.session_state["conteudo_log"],
            file_name=st.session_state["log_filename"],
            mime="text/plain",
        )
        c_d2.download_button(
            label="💾 Baixar Query UPDATE Executada (.sql)",
            data=st.session_state["conteudo_sql_exec"],
            file_name=st.session_state["sql_filename"],
            mime="text/plain",
        )
        st.text_area(
            "Prévia do Log Gerado:", st.session_state["conteudo_log"], height=160
        )
        del st.session_state["msg_sucesso"]

    st.subheader("1. Importação de Códigos")
    col_in1, col_in2 = st.columns([1, 1])

    with col_in1:
        arquivo = st.file_uploader(
            "Importar Arquivo (PDF, Excel XLSX/ODS, TXT):",
            type=["pdf", "xlsx", "xls", "ods", "odf", "txt", "csv"],
        )
        if arquivo is not None:
            codigos_lidos = extrair_codigos_arquivo(arquivo)
            if codigos_lidos:
                st.session_state["codigos_texto"] = "\n".join(codigos_lidos)
                st.success(f"✓ {len(codigos_lidos)} códigos encontrados no arquivo!")

    with col_in2:
        texto_codigos = st.text_area(
            "Códigos (colados do Excel/PDF ou manuais):",
            value=st.session_state["codigos_texto"],
            height=130,
            placeholder="Cole a lista de códigos aqui...",
        )
        st.session_state["codigos_texto"] = texto_codigos

    codigos_finais = extrair_codigos_de_texto(st.session_state["codigos_texto"])

    if codigos_finais:
        st.divider()
        codigos_sql_formatados = ", ".join(f"'{c}'" for c in codigos_finais)
        sql_select = (
            "SELECT co13CodPro, co13descri, co13Bloq, co13PCoMax, co13PCoMin, co13UlCus1, co13UlCus2 \n"
            f"FROM CO13T\nWHERE co13Emp06 = 1\nAND co13CodPro IN ({codigos_sql_formatados});"
        )

        with st.expander("🔍 Ver Query SELECT"):
            st.code(sql_select, language="sql")
            st.download_button(
                label="⬇️ Baixar SELECT (.sql)",
                data=sql_select,
                file_name=f"select_produtos_{datetime.now().strftime('%Y%m%d%H%M')}.sql",
                mime="text/plain",
            )

        if st.button("Executar Consulta no Banco de Dados", type="primary"):
            with st.spinner("Buscando registros no SQL Server..."):
                try:
                    df_carregado = buscar_dados_banco(codigos_finais)
                    if df_carregado.empty:
                        st.warning(
                            "Nenhum produto correspondente foi encontrado na base CO13T (Empresa 1)."
                        )
                    else:
                        st.session_state["df_original"] = df_carregado.copy()
                        st.session_state["df_editado"] = df_carregado.copy()
                        st.session_state["script_sql_previo"] = None
                        st.success(
                            f"✓ {len(df_carregado)} produto(s) carregado(s) com sucesso!"
                        )
                except Exception as e:
                    st.error(f"Erro ao consultar o banco de dados: {e}")

    if (
        st.session_state["df_editado"] is not None
        and not st.session_state["df_editado"].empty
    ):
        st.divider()
        st.subheader("2. Parâmetros de Alteração e Grid")

        st.markdown("**1. Selecione quais campos você deseja alterar:**")
        c1, c2, c3, c4, c5 = st.columns(5)
        alt_bloq = c1.checkbox("Bloqueado (co13Bloq)", value=False)
        alt_max = c2.checkbox("Preço Máx (co13PCoMax)", value=False)
        alt_min = c3.checkbox("Preço Mín (co13PCoMin)", value=False)
        alt_cus1 = c4.checkbox("Últ. Custo (co13UlCus1)", value=False)
        alt_cus2 = c5.checkbox("Últ. Valor Pago (co13UlCus2)", value=False)

        st.markdown("**2. Regras de sincronização:**")
        sync1, sync2 = st.columns(2)

        pode_sync_precos = alt_max and alt_min
        sincronizar_precos = (
            sync1.toggle(
                "Preço Mínimo = Preço Máximo",
                value=pode_sync_precos,
                disabled=not pode_sync_precos,
                help="Requer que 'Preço Máx' e 'Preço Mín' estejam ambos marcados acima.",
            )
            if pode_sync_precos
            else False
        )

        pode_sync_custos = alt_cus1 and alt_cus2
        sincronizar_custos = (
            sync2.toggle(
                "Último Custo = Último Valor Pago",
                value=pode_sync_custos,
                disabled=not pode_sync_custos,
                help="Requer que 'Últ. Custo' e 'Últ. Valor Pago' estejam ambos marcados acima.",
            )
            if pode_sync_custos
            else False
        )

        with st.expander(
            "⚡ Preenchimento Rápido em Lote (Aplicar em todos os itens selecionados)",
            expanded=True,
        ):
            st.caption(
                "Apenas os campos marcados acima estão liberados para preenchimento."
            )

            bl_c1, bl_c2, bl_c3, bl_c4, bl_c5 = st.columns(5)

            desbloquear_lote = bl_c1.checkbox(
                "Mudar Bloqueado para 'N'", value=alt_bloq, disabled=not alt_bloq
            )

            lote_pmax = bl_c2.number_input(
                "Preço Máximo (R$)",
                min_value=0.0,
                step=0.5,
                value=0.0,
                disabled=not alt_max,
            )

            val_default_pmin = lote_pmax if (sincronizar_precos and alt_max) else 0.0
            lote_pmin = bl_c3.number_input(
                "Preço Mínimo (R$)",
                min_value=0.0,
                step=0.5,
                value=val_default_pmin if (sincronizar_precos and alt_max) else 0.0,
                disabled=not alt_min or sincronizar_precos,
            )
            if sincronizar_precos and alt_max:
                lote_pmin = lote_pmax

            lote_cus1 = bl_c4.number_input(
                "Último Custo (R$)",
                min_value=0.0,
                step=0.5,
                value=0.0,
                disabled=not alt_cus1,
            )

            val_default_cus2 = lote_cus1 if (sincronizar_custos and alt_cus1) else 0.0
            lote_cus2 = bl_c5.number_input(
                "Último Valor Pago (R$)",
                min_value=0.0,
                step=0.5,
                value=val_default_cus2 if (sincronizar_custos and alt_cus1) else 0.0,
                disabled=not alt_cus2 or sincronizar_custos,
            )
            if sincronizar_custos and alt_cus1:
                lote_cus2 = lote_cus1

            btn_aplicar_lote = st.button(
                "🚀 Aplicar Alterações ao Lote",
                type="secondary",
                use_container_width=True,
            )

            if btn_aplicar_lote:
                df = st.session_state["df_editado"]
                selecionados = df["Selecionar"] == True
                qtd_sel = selecionados.sum()

                if qtd_sel == 0:
                    st.warning("Nenhum produto está marcado com 'Sel.' na grid.")
                else:
                    alterou_algo = False

                    if alt_bloq and desbloquear_lote:
                        df.loc[selecionados, "co13Bloq"] = "N"
                        alterou_algo = True

                    if alt_max and lote_pmax > 0:
                        df.loc[selecionados, "co13PCoMax"] = lote_pmax
                        alterou_algo = True

                    if alt_min or sincronizar_precos:
                        valor_min_aplicar = (
                            lote_pmax if sincronizar_precos else lote_pmin
                        )
                        if valor_min_aplicar > 0:
                            df.loc[selecionados, "co13PCoMin"] = valor_min_aplicar
                            alterou_algo = True

                    if alt_cus1 and lote_cus1 > 0:
                        df.loc[selecionados, "co13UlCus1"] = lote_cus1
                        alterou_algo = True

                    if alt_cus2 or sincronizar_custos:
                        valor_cus2_aplicar = (
                            lote_cus1 if sincronizar_custos else lote_cus2
                        )
                        if valor_cus2_aplicar > 0:
                            df.loc[selecionados, "co13UlCus2"] = valor_cus2_aplicar
                            alterou_algo = True

                    if alterou_algo:
                        st.session_state["df_editado"] = df
                        st.success(
                            f"✓ Alterações em lote aplicadas com sucesso para {qtd_sel} produto(s)!"
                        )
                    else:
                        st.info(
                            "Nenhum valor maior que zero ou campo selecionado para aplicar."
                        )

        colunas_config = {
            "Selecionar": st.column_config.CheckboxColumn("Sel.", default=True),
            "co13CodPro": st.column_config.TextColumn("Código Produto", disabled=True),
            "co13descri": st.column_config.TextColumn("Descrição", disabled=True),
            "co13Bloq": st.column_config.SelectboxColumn(
                "Bloqueado",
                options=["N", "S"] if alt_bloq else ["S"],
                disabled=not alt_bloq,
            ),
            "co13PCoMax": st.column_config.NumberColumn(
                "Preço Máximo", disabled=not alt_max, format="R$ %.2f"
            ),
            "co13PCoMin": st.column_config.NumberColumn(
                "Preço Mínimo", disabled=not alt_min, format="R$ %.2f"
            ),
            "co13UlCus1": st.column_config.NumberColumn(
                "Último Custo", disabled=not alt_cus1, format="R$ %.2f"
            ),
            "co13UlCus2": st.column_config.NumberColumn(
                "Último Valor Pago", disabled=not alt_cus2, format="R$ %.2f"
            ),
        }

        df_modificado = st.data_editor(
            st.session_state["df_editado"],
            column_config=colunas_config,
            hide_index=True,
            use_container_width=True,
            key="editor_grid",
        )

        if sincronizar_precos:
            df_modificado["co13PCoMin"] = df_modificado["co13PCoMax"]
        if sincronizar_custos:
            df_modificado["co13UlCus2"] = df_modificado["co13UlCus1"]

        st.session_state["df_editado"] = df_modificado

        st.divider()
        st.subheader("3. Validação e Gravação")

        col_btn_val, col_btn_exec = st.columns(2)

        with col_btn_val:
            if st.button("🔍 Gerar Query UPDATE (Validação)", use_container_width=True):
                df_orig = st.session_state["df_original"]
                df_fim = st.session_state["df_editado"]
                updates_sql, _, _, total_alterados = montar_alteracoes(
                    df_orig,
                    df_fim,
                    alt_bloq,
                    alt_max,
                    alt_min,
                    alt_cus1,
                    alt_cus2,
                    sincronizar_precos,
                    sincronizar_custos,
                )

                if total_alterados > 0:
                    script_sql_validacao = (
                        "BEGIN TRANSACTION;\n\n"
                        + "\n".join(updates_sql)
                        + "\n\nCOMMIT;"
                    )
                    st.session_state["script_sql_previo"] = script_sql_validacao
                    st.info(
                        f"Foram detectadas alterações em {total_alterados} registro(s)."
                    )
                else:
                    st.session_state["script_sql_previo"] = None
                    st.warning(
                        "Nenhuma alteração foi detectada nos campos selecionados."
                    )

        if st.session_state.get("script_sql_previo"):
            with st.expander("📄 Código SQL gerado para validação", expanded=True):
                st.code(st.session_state["script_sql_previo"], language="sql")
                st.download_button(
                    label="⬇️ Baixar UPDATE (.sql)",
                    data=st.session_state["script_sql_previo"],
                    file_name=f"validacao_update_{datetime.now().strftime('%Y%m%d%H%M')}.sql",
                    mime="text/plain",
                    key="down_btn_validacao",
                )

        with col_btn_exec:
            if st.button(
                "💾 Confirmar e Gravar no Banco de Dados",
                type="primary",
                use_container_width=True,
            ):
                df_orig = st.session_state["df_original"]
                df_fim = st.session_state["df_editado"]

                updates_sql, linhas_log_itens, resumo_mudancas, total_alterados = (
                    montar_alteracoes(
                        df_orig,
                        df_fim,
                        alt_bloq,
                        alt_max,
                        alt_min,
                        alt_cus1,
                        alt_cus2,
                        sincronizar_precos,
                        sincronizar_custos,
                    )
                )

                if total_alterados > 0:
                    confirmar_gravacao_dialog(
                        updates_sql, linhas_log_itens, resumo_mudancas, total_alterados
                    )
                else:
                    st.warning(
                        "Nenhuma alteração foi detectada para os campos selecionados."
                    )
