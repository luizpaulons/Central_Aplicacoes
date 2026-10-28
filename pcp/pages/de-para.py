import streamlit as st
import pandas as pd
from utils.database import buscar_dados_base_sql
from utils.storage import carregar_cadastros_base, carregar_de_para, salvar_de_para

st.set_page_config(page_title="Vínculo De-Para", layout="wide")
st.title("📝 Vínculo De-Para: Modelo e Cor x Solado e Cor do EVA")

cadastros_base = carregar_cadastros_base()
lista_solados_opcoes = [""] + cadastros_base.get("solados", [])
lista_cores_opcoes = [""] + [
    item["cor"] if isinstance(item, dict) else str(item) 
    for item in cadastros_base.get("cores_eva", [])
]

col_t1, col_t2 = st.columns([5, 1])
with col_t2:
    if st.button("🔄 Atualizar Banco"):
        st.cache_data.clear()
        st.rerun()

try:
    df_fonte = buscar_dados_base_sql()
except Exception as e:
    st.error(f"Erro ao conectar ao banco de dados: {e}")
    df_fonte = None

if df_fonte is not None and not df_fonte.empty:
    df_fonte["Linha"] = df_fonte["Linha"].astype(str).str.strip()
    df_fonte["Modelo"] = df_fonte["Modelo"].astype(str).str.strip()
    df_fonte["Cor"] = df_fonte["Cor"].astype(str).str.strip()
    df_fonte["Descrição Cor"] = df_fonte["Descrição Cor"].astype(str).str.strip()

    df_ref_mod = df_fonte[["Linha", "Modelo"]].drop_duplicates()
    df_ref_mod = df_ref_mod.sort_values(
        by=["Linha"], 
        key=lambda s: s.map(lambda x: (0, int(x)) if str(x).isdigit() else (1, str(x)))
    )
    df_ref_mod["opcao"] = df_ref_mod["Linha"] + " - " + df_ref_mod["Modelo"]
    lista_opcoes = df_ref_mod["opcao"].tolist()

    col_f1, col_f2 = st.columns([3, 3])
    with col_f1:
        item_selecionado = st.selectbox("Selecione a Referência / Modelo:", options=lista_opcoes)
        linha_selecionada = item_selecionado.split(" - ")[0].strip()

    with col_f2:
        modelos_encontrados = df_fonte[df_fonte["Linha"] == linha_selecionada]["Modelo"].unique()
        nome_modelo_sel = modelos_encontrados[0] if len(modelos_encontrados) > 0 else ""
        st.markdown(f"**REFERÊNCIA SELECIONADA:** `{linha_selecionada}`")
        st.markdown(f"**Modelo:** `{nome_modelo_sel}`")

    df_filtrado = df_fonte[df_fonte["Linha"] == linha_selecionada].drop_duplicates(subset=["Linha", "Cor"]).copy()

    df_de_para_atual = carregar_de_para()
    df_merge = pd.merge(
        df_filtrado, 
        df_de_para_atual.rename(columns={"linha": "Linha", "cor": "Cor", "nome_solado": "Solado", "cor_eva": "Cor do EVA"})[["Linha", "Cor", "Solado", "Cor do EVA"]], 
        on=["Linha", "Cor"], 
        how="left"
    )
    df_merge["Solado"] = df_merge["Solado"].fillna("")
    df_merge["Cor do EVA"] = df_merge["Cor do EVA"].fillna("")
    df_merge["Sel"] = False

    chave_df = f"grid_trabalho_{linha_selecionada}"
    chave_master = f"master_check_{linha_selecionada}"

    if chave_df not in st.session_state:
        st.session_state[chave_df] = df_merge

    with st.expander("⚡ Preenchimento em LOTE para os itens marcados", expanded=True):
        col_l1, col_l2, col_l3 = st.columns([2, 2, 1])
        with col_l1:
            sol_lote = st.selectbox(
                "Nome do Solado (Lote):", 
                options=["ESCOLHA UMA OPÇÃO"] + [s for s in lista_solados_opcoes if s],
                index=0,
                key=f"sol_lote_{linha_selecionada}"
            )
        with col_l2:
            eva_lote = st.selectbox(
                "Cor do EVA (Lote):", 
                options=["ESCOLHA UMA OPÇÃO"] + [c for c in lista_cores_opcoes if c],
                index=0,
                key=f"eva_lote_{linha_selecionada}"
            )
        with col_l3:
            st.write("")
            st.write("")
            if st.button("Aplicar Lote", key=f"btn_lote_{linha_selecionada}"):
                marcados = st.session_state[chave_df]["Sel"] == True
                if marcados.any():
                    if sol_lote != "ESCOLHA UMA OPÇÃO":
                        st.session_state[chave_df].loc[marcados, "Solado"] = sol_lote
                    if eva_lote != "ESCOLHA UMA OPÇÃO":
                        st.session_state[chave_df].loc[marcados, "Cor do EVA"] = eva_lote
                    st.success(f"Aplicado a {marcados.sum()} item(ns)!")
                    st.rerun()
                else:
                    st.warning("Marque as caixas na coluna 'Sel' dos itens desejados.")

    def toggle_todos_cb():
        st.session_state[chave_df]["Sel"] = st.session_state[chave_master]

    st.checkbox("Marcar / Desmarcar Todos na Tabela", key=chave_master, on_change=toggle_todos_cb)

    grid_amigavel = st.data_editor(
        st.session_state[chave_df],
        column_order=["Sel", "Linha", "Modelo", "Cor", "Descrição Cor", "Solado", "Cor do EVA"],
        column_config={
            "Sel": st.column_config.CheckboxColumn("Sel", default=False, width="small"),
            "Linha": st.column_config.TextColumn("Linha", disabled=True, width="small"),
            "Modelo": st.column_config.TextColumn("Modelo", disabled=True, width="medium"),
            "Cor": st.column_config.TextColumn("Cor", disabled=True, width="small"),
            "Descrição Cor": st.column_config.TextColumn("Descrição Cor", disabled=True, width="large"),
            "Solado": st.column_config.SelectboxColumn("Solado", options=lista_solados_opcoes, width="medium"),
            "Cor do EVA": st.column_config.SelectboxColumn("Cor do EVA", options=lista_cores_opcoes, width="medium"),
        },
        hide_index=True,
        use_container_width=True,
        key=f"editor_{linha_selecionada}"
    )
    st.session_state[chave_df] = grid_amigavel

    if st.button("💾 Gravar Alterações no De-Para"):
        dados_salvar = grid_amigavel[["Linha", "Modelo", "Cor", "Descrição Cor", "Solado", "Cor do EVA"]].copy()
        dados_salvar = dados_salvar.rename(columns={
            "Linha": "linha", "Modelo": "modelo", "Cor": "cor",
            "Descrição Cor": "descricao_cor", "Solado": "nome_solado", "Cor do EVA": "cor_eva"
        })
        salvar_de_para(dados_salvar)
        st.success("Configurações gravadas com sucesso no De-Para!")
else:
    st.warning("Nenhum dado retornado da consulta SQL ou falha na conexão.")