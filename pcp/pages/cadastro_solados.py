import streamlit as st
import pandas as pd
from utils.database import buscar_cores_pc10t
from utils.storage import carregar_cadastros_base, salvar_cadastros_base, carregar_de_para

st.set_page_config(page_title="Cadastro de Solados e Cores", layout="wide")
st.title("⚙️ Cadastro Oficial de Solados e Cores de EVA")
st.info("Cadastre os itens oficiais ou marque na grid para excluir. Itens em uso no De-Para não podem ser excluídos.")

cadastros_base = carregar_cadastros_base()
df_de_para_atual = carregar_de_para()
solados_em_uso = set(df_de_para_atual["nome_solado"].dropna().astype(str).str.strip().str.upper()) if not df_de_para_atual.empty else set()
cores_em_uso = set(df_de_para_atual["cor_eva"].dropna().astype(str).str.strip().str.upper()) if not df_de_para_atual.empty else set()

def callback_adicionar_solado():
    sol = st.session_state.get("input_novo_solado", "").strip().upper()
    if sol:
        if sol not in cadastros_base["solados"]:
            cadastros_base["solados"].append(sol)
            cadastros_base["solados"].sort()
            salvar_cadastros_base(cadastros_base)
            st.session_state["msg_solado"] = ("sucesso", f"Solado '{sol}' cadastrado!")
        else:
            st.session_state["msg_solado"] = ("aviso", "Este solado já existe.")
    st.session_state["input_novo_solado"] = ""

col_cad1, col_cad2 = st.columns(2)

# 1. SOLADOS
with col_cad1:
    st.markdown("### 👟 Solados")
    if "msg_solado" in st.session_state:
        tipo, texto = st.session_state.pop("msg_solado")
        if tipo == "sucesso": st.success(texto)
        elif tipo == "aviso": st.warning(texto)

    col_add_s1, col_add_s2 = st.columns([3, 1])
    with col_add_s1:
        st.text_input("NOVO SOLADO:", placeholder="DIGITE O NOME DO SOLADO", key="input_novo_solado")
    with col_add_s2:
        st.write("")
        st.write("")
        st.button("➕ Adicionar", key="btn_add_solado", on_click=callback_adicionar_solado)

    lista_solados = cadastros_base.get("solados", [])
    df_grid_sol = pd.DataFrame({
        "SELECIONAR": [False] * len(lista_solados),
        "NOME DO SOLADO": lista_solados
    }) if lista_solados else pd.DataFrame(columns=["SELECIONAR", "NOME DO SOLADO"])

    grid_sol_editada = st.data_editor(
        df_grid_sol,
        column_config={
            "SELECIONAR": st.column_config.CheckboxColumn("SELECIONAR", default=False, width="small"),
            "NOME DO SOLADO": st.column_config.TextColumn("NOME DO SOLADO", disabled=True, width="large"),
        },
        hide_index=True,
        use_container_width=True,
        key="grid_solados_exclusao"
    )

    if st.button("🗑️ Excluir Solados Selecionados"):
        selecionados = grid_sol_editada[grid_sol_editada["SELECIONAR"] == True]["NOME DO SOLADO"].tolist() if not grid_sol_editada.empty else []
        if not selecionados:
            st.warning("Marque ao menos um solado.")
        else:
            bloqueados = [s for s in selecionados if s in solados_em_uso]
            permitidos = [s for s in selecionados if s not in solados_em_uso]
            if bloqueados:
                st.error(f"❌ Bloqueado(s) pois estão em uso no De-Para: {', '.join(bloqueados)}")
            if permitidos:
                cadastros_base["solados"] = [s for s in cadastros_base["solados"] if s not in permitidos]
                salvar_cadastros_base(cadastros_base)
                st.success(f"Solado(s) removido(s): {', '.join(permitidos)}")
                st.rerun()

# 2. CORES DE EVA (BUSCA NA PC10T)
with col_cad2:
    st.markdown("### 🎨 Cores de EVA")
    try:
        df_cores_banco = buscar_cores_pc10t()
        mapa_pc10 = dict(zip(df_cores_banco["PC10Codigo"], df_cores_banco["PC10Descr"]))
    except Exception as e:
        st.error(f"Erro ao carregar PC10T: {e}")
        mapa_pc10 = {}

    if "msg_cor" in st.session_state:
        tipo, texto = st.session_state.pop("msg_cor")
        if tipo == "sucesso": st.success(texto)
        elif tipo == "aviso": st.warning(texto)

    col_add_c1, col_add_c2 = st.columns([3, 1])
    with col_add_c1:
        cod_digitado = st.text_input("CÓDIGO DA COR (PC10T):", placeholder="EX: 545", key="input_cod_cor").strip().upper()
        cor_encontrada = mapa_pc10.get(cod_digitado, "")
        if cod_digitado:
            if cor_encontrada:
                st.caption(f"✅ Descrição na PC10T: **{cor_encontrada}**")
            else:
                st.caption("⚠️ Código não localizado na PC10T.")

    with col_add_c2:
        st.write("")
        st.write("")
        if st.button("➕ Adicionar", key="btn_add_cor"):
            if not cod_digitado or not cor_encontrada:
                st.warning("Informe um código válido da tabela PC10T.")
            else:
                codigos_existentes = [str(item.get("codigo", "")).strip().upper() for item in cadastros_base["cores_eva"]]
                cores_existentes = [str(item.get("cor", "")).strip().upper() for item in cadastros_base["cores_eva"]]

                if cod_digitado in codigos_existentes or cor_encontrada in cores_existentes:
                    st.warning(f"A cor '{cor_encontrada}' já está cadastrada.")
                else:
                    cadastros_base["cores_eva"].append({"codigo": cod_digitado, "cor": cor_encontrada})
                    cadastros_base["cores_eva"] = sorted(cadastros_base["cores_eva"], key=lambda x: x["cor"])
                    salvar_cadastros_base(cadastros_base)
                    st.session_state["msg_cor"] = ("sucesso", f"Cor '{cor_encontrada}' cadastrada!")
                    st.rerun()

    dados_grid_cor = [{"Selecionar": False, "Codigo": str(i.get("codigo", "")).upper(), "Cor": str(i.get("cor", "")).upper()} for i in cadastros_base["cores_eva"]]
    df_grid_cor = pd.DataFrame(dados_grid_cor) if dados_grid_cor else pd.DataFrame(columns=["Selecionar", "Codigo", "Cor"])
    
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
        selecionadas = grid_cor_editada[grid_cor_editada["Selecionar"] == True]["Cor"].tolist() if not grid_cor_editada.empty else []
        if not selecionadas:
            st.warning("Marque ao menos uma cor.")
        else:
            bloqueadas = [c for c in selecionadas if c in cores_em_uso]
            permitidas = [c for c in selecionadas if c not in cores_em_uso]
            if bloqueadas:
                st.error(f"❌ Bloqueada(s) pois estão em uso no De-Para: {', '.join(bloqueadas)}")
            if permitidas:
                cadastros_base["cores_eva"] = [item for item in cadastros_base["cores_eva"] if item.get("cor") not in permitidas]
                salvar_cadastros_base(cadastros_base)
                st.success(f"Cor(es) removida(s): {', '.join(permitidas)}")
                st.rerun()