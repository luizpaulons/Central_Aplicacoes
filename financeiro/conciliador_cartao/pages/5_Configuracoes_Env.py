import streamlit as st
import imap_reader

st.title("⚙ Configurações de Conexão IMAP")
config_env = imap_reader.obter_configuracoes_env()

st.info("Parâmetros carregados a partir do arquivo **.env** na raiz do projeto:")
st.write(f"**Servidor IMAP:** `{config_env['host']}`")
st.write(f"**Porta:** `{config_env['port']}`")
st.write(f"**Usuário:** `{config_env['user']}`")
st.write(f"**Pasta:** `{config_env['folder']}`")
st.write(f"**Senha configurada:** `{'Sim ✔' if config_env['password'] else 'Não ❌'}`")