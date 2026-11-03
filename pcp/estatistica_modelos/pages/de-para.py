import streamlit as st
import pandas as pd
from datetime import datetime

from utils.storage import (
    carregar_cadastros_base,
    carregar_de_para,
    salvar_de_para,
    carregar_dados_base_local
)
from utils.database import sincronizar_dados_base_sql_para_sqlite

st.title("📝 Vínculo De-Para: Modelo e Cor x Solado e Cor do EVA")

# --- CABEÇALHO: SINCRONIZAÇÃO SQL SERVER -> SQLITE ---
col_btn, col_info = st.columns([1, 4])

with col_btn:
    clicou_sincronizar = st.button("🔄 Sincronizar Banco", use_container_width=True)

if clicou_sincronizar:
    try:
        with st.spinner("Sincronizando modelos e cores do SQL Server para o SQLite..."):
            total_linhas = sincronizar_dados_base_sql_para_sqlite()
            agora = datetime.now().strftime("%d/%m/%Y às %H:%M:%S")
            st.session_state["ultima_atualizacao_banco"] = agora
            st.session_state["msg_banco"] = ("sucesso", f"✅ Base sincronizada com sucesso! {total_linhas} registros atualizados em {agora}.")
            st.rerun()
    except Exception as e:
        st.session_state["msg_banco"] = ("erro", f"❌ Falha ao sincronizar com SQL Server: {e}")

with col_info:
    ultima_atualizacao = st.session_state.get("ultima_atualizacao_banco", "Base local SQLite em uso")
    st.markdown(f"🕒 **Status da Base:** `{ultima_atualizacao}`")

if "msg_banco" in st.session_state:
    tipo_msg, texto_msg = st.session_state.pop("msg_banco")
    if tipo_msg == "sucesso":
        st.success(texto_msg)
    else:
        st.error(texto_msg)

st.markdown("---")

# Lê a base diretamente da tabela SQLite local
df_fonte = carregar_dados_base_local()

if df_fonte.empty:
    st.warning("A base local do SQLite ainda não possui dados. Clique em '🔄 Sincronizar Banco' para importar do SQL Server.")
else:
    df_fonte["Linha"] = df_fonte["Linha"].astype(str).str.strip().str.upper()
    df_fonte["Modelo"] = df_fonte["Modelo"].astype(str).str.strip().str.upper()
    df_fonte["Cor"] = df_fonte["Cor"].astype(str).str.strip().str.upper()
    df_fonte["Descrição Cor"] = df_fonte["Descrição Cor"].astype(str).str.strip().str.upper()

    df_ref_mod = df_fonte[["Linha", "Modelo"]].drop_duplicates()
    df_ref_mod = df_ref_mod.sort_values(
        by=["Linha"],
        key=lambda s: s.map(lambda x: (0, int(x)) if str(x).isdigit() else (1, str(x)))
    )
    df_ref_mod["opcao"] = df_ref_mod["Linha"] + " - " + df_ref_mod["Modelo"]
    lista_opcoes = df_ref_mod["opcao"].tolist()

    col_f1, col_f2 = st.columns([3, 3])
    with col_f1:
        item_selecionado = st.selectbox("Selecione a Referência / Modelo", options=lista_opcoes)
        linha_selecionada = item_selecionado.split(" - ")[0].strip().upper()

    with col_f2:
        modelos_encontrados = df_fonte[df_fonte["Linha"] == linha_selecionada]["Modelo"].unique()
        nome_modelo_sel = modelos_encontrados[0] if len(modelos_encontrados) > 0 else ""
        st.markdown(f"**REFERÊNCIA SELECIONADA:** `{linha_selecionada}`")
        st.markdown(f"**Modelo:** `{nome_modelo_sel}`")

    df_filtrado = df_fonte[df_fonte["Linha"] == linha_selecionada].drop_duplicates(subset=["Linha", "Cor"]).copy()

    df_de_para_atual = carregar_de_para()
    mapa_existente_solado = {}
    mapa_existente_eva = {}
    if not df_de_para_atual.empty:
        for _, r in df_de_para_atual.iterrows():
            ch = (str(r.get("linha", "")).strip().upper(), str(r.get("cor", "")).strip().upper())
            mapa_existente_solado[ch] = str(r.get("nome_solado", "")).strip().upper()
            mapa_existente_eva[ch] = str(r.get("cor_eva", "")).strip().upper()

    linhas_grid = []
    for _, row in df_filtrado.iterrows():
        ch = (row["Linha"], row["Cor"])
        linhas_grid.append({
            "Sel": False,
            "Linha": row["Linha"],
            "Modelo": row["Modelo"],
            "Cor": row["Cor"],
            "Descrição Cor": row["Descrição Cor"],
            "Solado": mapa_existente_solado.get(ch, ""),
            "Cor do EVA": mapa_existente_eva.get(ch, "")
        })

    df_grid_final = pd.DataFrame(linhas_grid)
    chave_df = f"grid_v7_{linha_selecionada}"
    chave_master = f"master_v7_{linha_selecionada}"

    colunas_esperadas = ["Sel", "Linha", "Modelo", "Cor", "Descrição Cor", "Solado", "Cor do EVA"]
    if chave_df not in st.session_state or list(st.session_state[chave_df].columns) != colunas_esperadas:
        st.session_state[chave_df] = df_grid_final

    # Carrega os cadastros base do SQLite antes de montar as listas
    cadastros_base = carregar_cadastros_base()
    solados_disp = cadastros_base.get("solados", [])
    cores_disp = [
        item["cor"]
        for item in cadastros_base.get("cores_eva", [])
        if isinstance(item, dict) and "cor" in item
    ]

    opcoes_solados_grid = [""] + solados_disp
    opcoes_cores_grid = [""] + cores_disp

    opcoes_solados_lote = ["ESCOLHA UMA OPÇÃO"] + solados_disp
    opcoes_cores_lote = ["ESCOLHA UMA OPÇÃO"] + cores_disp

    with st.expander("⚡ Preenchimento em LOTE para os itens marcados", expanded=True):
        col_l1, col_l2, col_l3 = st.columns([2, 2, 1])
        with col_l1:
            sol_lote = st.selectbox("Solado (Lote):", options=opcoes_solados_lote, index=0, key=f"sol_lote_{linha_selecionada}")
        with col_l2:
            eva_lote = st.selectbox("Cor do EVA (Lote):", options=opcoes_cores_lote, index=0, key=f"eva_lote_{linha_selecionada}")
        with col_l3:
            st.write("")
            st.write("")
            if st.button("Aplicar Lote", key=f"btn_lote_{linha_selecionada}"):
                marcados = st.session_state[chave_df]["Sel"] == True
                if marcados.any():
                    if sol_lote and sol_lote != "ESCOLHA UMA OPÇÃO":
                        st.session_state[chave_df].loc[marcados, "Solado"] = sol_lote
                    if eva_lote and eva_lote != "ESCOLHA UMA OPÇÃO":
                        st.session_state[chave_df].loc[marcados, "Cor do EVA"] = eva_lote
                    st.success(f"Aplicado a {marcados.sum()} item(ns)!")
                    st.rerun()
                else:
                    st.warning("Marque as caixas na coluna 'Sel' dos itens desejados.")

    def toggle_todos():
        st.session_state[chave_df]["Sel"] = st.session_state[chave_master]

    st.checkbox("Marcar / Desmarcar Todos", key=chave_master, on_change=toggle_todos)

    grid_editada = st.data_editor(
        st.session_state[chave_df],
        column_config={
            "Sel": st.column_config.CheckboxColumn("Sel", default=False, width="small"),
            "Linha": st.column_config.TextColumn("Linha", disabled=True, width="small"),
            "Modelo": st.column_config.TextColumn("Modelo", disabled=True, width="medium"),
            "Cor": st.column_config.TextColumn("Cor", disabled=True, width="small"),
            "Descrição Cor": st.column_config.TextColumn("Descrição Cor", disabled=True, width="large"),
            "Solado": st.column_config.SelectboxColumn("Solado", options=opcoes_solados_grid, width="medium", required=False),
            "Cor do EVA": st.column_config.SelectboxColumn("Cor do EVA", options=opcoes_cores_grid, width="medium", required=False),
        },
        hide_index=True,
        use_container_width=True,
        key=f"editor_grid_v7_{linha_selecionada}"
    )
    st.session_state[chave_df] = grid_editada

    if st.button("💾 Gravar Alterações no De-Para"):
        dados_salvar = grid_editada.rename(columns={
            "Linha": "linha",
            "Modelo": "modelo",
            "Cor": "cor",
            "Descrição Cor": "descricao_cor",
            "Solado": "nome_solado",
            "Cor do EVA": "cor_eva"
        })[["linha", "modelo", "cor", "descricao_cor", "nome_solado", "cor_eva"]].copy()

        salvar_de_para(dados_salvar)
        st.success("Configurações gravadas com sucesso no SQLite!")