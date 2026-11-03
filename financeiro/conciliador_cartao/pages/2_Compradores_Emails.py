import streamlit as st
import pandas as pd
import database

st.title("👤 Vínculo de Compradores por E-mail")
st.write("Cadastre o e-mail de envio das notas para que o nome do comprador seja associado automaticamente.")

col1, col2 = st.columns([1, 1.4])
with col1:
    st.markdown("#### Cadastrar / Editar Comprador")
    with st.form("form_comprador"):
        email_in = st.text_input("E-mail corporativo (ex: luiz@tenislynd.com.br)").lower().strip()
        nome_in = st.text_input("Nome do Comprador (ex: Luiz Paulo)").strip()
        if st.form_submit_button("Salvar Vínculo"):
            if "@" in email_in and nome_in:
                database.salvar_comprador(email_in, nome_in)
                st.success(f"Vínculo cadastrado: {email_in} ➔ {nome_in}")
                st.rerun()
            else:
                st.error("Preencha um e-mail válido e o nome do comprador.")

with col2:
    st.markdown("#### Compradores Cadastrados")
    compradores = database.listar_compradores()
    if not compradores:
        st.info("Nenhum comprador vinculado ainda.")
    else:
        # 1 - Grid iniciando pelo número 1
        dados_tabela = [
            {"Nº": i, "E-mail": k, "Comprador": v}
            for i, (k, v) in enumerate(compradores.items(), start=1)
        ]
        df_comp = pd.DataFrame(dados_tabela).set_index("Nº")
        st.dataframe(df_comp, width='stretch')

        email_del = st.selectbox("Excluir Vínculo", options=list(compradores.keys()))
        if st.button("🗑 Excluir Comprador"):
            database.excluir_comprador(email_del)
            st.success("Excluído com sucesso!")
            st.rerun()