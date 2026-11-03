import streamlit as st
import pandas as pd
import database

st.title("📑 Assinaturas & Contratos Cadastrados")

if "item_para_excluir" not in st.session_state:
    st.session_state["item_para_excluir"] = None

# Diálogo de Confirmação de Exclusão
if st.session_state["item_para_excluir"] is not None:
    id_excluir, forn_excluir = st.session_state["item_para_excluir"]
    st.warning(f"⚠️ **Confirmação:** Deseja realmente excluir a recorrência de **{forn_excluir}**?")
    c_sim, c_nao, _ = st.columns([1, 1, 4])
    with c_sim:
        if st.button("✅ Sim, excluir", type="primary"):
            database.excluir_recorrencia(id_excluir)
            st.session_state["item_para_excluir"] = None
            st.success("Item excluído com sucesso!")
            st.rerun()
    with c_nao:
        if st.button("❌ Cancelar"):
            st.session_state["item_para_excluir"] = None
            st.rerun()
    st.divider()

recorrencias = database.listar_recorrencias()

if not recorrencias:
    st.info("Nenhuma assinatura ou contrato cadastrado.")
else:
    # 1 - Cabeçalho visual da Grid
    h1, h2, h3, h4, h5, h6, h7 = st.columns([0.6, 1.2, 2.5, 1.3, 1.8, 2.2, 0.8])
    h1.markdown("**Nº**")
    h2.markdown("**Tipo**")
    h3.markdown("**Fornecedor**")
    h4.markdown("**Valor (R$)**")
    h5.markdown("**Comprador**")
    h6.markdown("**Observação**")
    h7.markdown("**Ação**")
    st.divider()

    # 1 - Grid iniciando pelo número 1 | 2 - Lixeira na linha com confirmação
    for i, r in enumerate(recorrencias, start=1):
        rec_id, r_tipo, r_forn, r_val, r_comp, r_obs = r
        c1, c2, c3, c4, c5, c6, c7 = st.columns([0.6, 1.2, 2.5, 1.3, 1.8, 2.2, 0.8])
        c1.write(f"**{i}**")
        c2.write(r_tipo)
        c3.write(r_forn)
        c4.write(f"R$ {r_val:,.2f}")
        c5.write(r_comp or "-")
        c6.write(r_obs or "-")
        with c7:
            if st.button("🗑", key=f"btn_del_rec_{rec_id}", help="Excluir este item"):
                st.session_state["item_para_excluir"] = (rec_id, r_forn)
                st.rerun()
        st.divider()