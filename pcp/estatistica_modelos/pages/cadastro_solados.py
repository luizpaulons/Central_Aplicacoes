import streamlit as st
import pandas as pd
from utils.database import buscar_cores_pc10t
from utils.storage import carregar_cadastros_base, salvar_cadastros_base, carregar_de_para

st.title("⚙️ Cadastro Oficial de Solados e Cores de EVA")
st.info("Cadastre os itens oficiais ou marque na grid para excluir. Itens em uso no De-Para não podem ser excluídos.")

cadastros_base = carregar_cadastros_base()
df_de_para_atual = carregar_de_para()
solados_em_uso = set(df_de_para_atual["nome_solado"].dropna().astype(str).str.strip().str.upper()) if not df_de_para_atual.empty else set()
cores_em_uso = set(df_de_para_atual["cor_eva"].dropna().astype(str).str.strip().str.upper()) if not df_de_para_atual.empty else set()

# Callback para solado
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

# Callback para cor com limpeza de texto e código numérico
def callback_adicionar_cor(mapa_pc10):
    cod_raw = st.session_state.get("input_cod_cor", "").strip()
    if cod_raw:
        try:
            cod_num = int(cod_raw)
        except ValueError:
            st.session_state["msg_cor"] = ("aviso", "O código da cor deve ser numérico.")
            st.session_state["input_cod_cor"] = ""
            return

        cod_str = str(cod_num)
        desc_encontrada = mapa_pc10.get(cod_str, "").strip().upper()

        if not desc_encontrada:
            st.session_state["msg_cor"] = ("aviso", f"Código {cod_str} não encontrado na PC10T.")
        else:
            # Lista de códigos existentes como inteiros para validação
            codigos_existentes = []
            for item in cadastros_base.get("cores_eva", []):
                try:
                    codigos_existentes.append(int(item.get("codigo", -1)))
                except (ValueError, TypeError):
                    pass

            if cod_num in codigos_existentes:
                st.session_state["msg_cor"] = ("aviso", f"O código {cod_str} já está cadastrado.")
            else:
                cadastros_base["cores_eva"].append({
                    "codigo": cod_num,
                    "cor": desc_encontrada
                })
                # Ordena a lista sempre numericamente
                cadastros_base["cores_eva"] = sorted(
                    cadastros_base["cores_eva"], 
                    key=lambda x: int(x.get("codigo", 0)) if str(x.get("codigo", "")).isdigit() else 999999
                )
                salvar_cadastros_base(cadastros_base)
                st.session_state["msg_cor"] = ("sucesso", f"Cor '{cod_str} - {desc_encontrada}' cadastrada!")

    # Limpa o campo para a próxima digitação
    st.session_state["input_cod_cor"] = ""

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
        mapa_pc10 = dict(zip(df_cores_banco["PC10Codigo"].astype(str).str.strip(), df_cores_banco["PC10Descr"].astype(str).str.strip()))
    except Exception as e:
        st.error(f"Erro ao carregar PC10T: {e}")
        mapa_pc10 = {}

    if "msg_cor" in st.session_state:
        tipo, texto = st.session_state.pop("msg_cor")
        if tipo == "sucesso": st.success(texto)
        elif tipo == "aviso": st.warning(texto)

    col_add_c1, col_add_c2 = st.columns([3, 1])
    with col_add_c1:
        st.text_input("CÓDIGO DA COR (PC10T):", placeholder="EX: 545", key="input_cod_cor")
        cod_preview = st.session_state.get("input_cod_cor", "").strip()
        if cod_preview:
            desc_preview = mapa_pc10.get(cod_preview, "")
            if desc_preview:
                st.caption(f"✅ Descrição na PC10T: **{desc_preview}**")
            else:
                st.caption("⚠️ Código não localizado na PC10T.")

    with col_add_c2:
        st.write("")
        st.write("")
        st.button("➕ Adicionar", key="btn_add_cor", on_click=callback_adicionar_cor, args=(mapa_pc10,))

    # Grid com Código Numérico (int) para ordenação correta
    dados_grid_cor = []
    for i in cadastros_base.get("cores_eva", []):
        try:
            cod_val = int(i.get("codigo", 0))
        except (ValueError, TypeError):
            cod_val = 0

        dados_grid_cor.append({
            "Selecionar": False,
            "Codigo": cod_val,
            "Cor": str(i.get("cor", "")).upper()
        })

    df_grid_cor = pd.DataFrame(dados_grid_cor) if dados_grid_cor else pd.DataFrame(columns=["Selecionar", "Codigo", "Cor"])
    df_grid_cor["Selecionar"] = df_grid_cor["Selecionar"].astype(bool)
    df_grid_cor["Codigo"] = pd.to_numeric(df_grid_cor["Codigo"], errors="coerce").fillna(0).astype(int)
    df_grid_cor["Cor"] = df_grid_cor["Cor"].astype(str)

    # Ordenação padrão numérica crescente
    df_grid_cor = df_grid_cor.sort_values(by="Codigo", ascending=True)

    grid_cor_editada = st.data_editor(
        df_grid_cor,
        column_config={
            "Selecionar": st.column_config.CheckboxColumn("Selecionar", default=False, width="small"),
            "Codigo": st.column_config.NumberColumn("Codigo", format="%d", disabled=True, width="small"),
            "Cor": st.column_config.TextColumn("Cor", disabled=True, width="large"),
        },
        hide_index=True,
        use_container_width=True,
        key="grid_cores_exclusao"
    )

    if st.button("🗑️ Excluir Cores Selecionadas"):
        selecionadas = grid_cor_editada[grid_cor_editada["Selecionar"] == True] if not grid_cor_editada.empty else pd.DataFrame()
        if selecionadas.empty:
            st.warning("Marque ao menos uma cor.")
        else:
            # Lista de códigos e representações textuais para validação contra o De-Para
            excluir_codigos = selecionadas["Codigo"].tolist()
            excluir_textos = [f"{r['Codigo']} - {r['Cor']}".strip().upper() for _, r in selecionadas.iterrows()]
            excluir_cores = selecionadas["Cor"].tolist()

            bloqueadas = []
            permitidos_cods = []

            for cod_num, texto_fmt, cor_nome in zip(excluir_codigos, excluir_textos, excluir_cores):
                if texto_fmt in cores_em_uso or cor_nome in cores_em_uso:
                    bloqueadas.append(texto_fmt)
                else:
                    permitidos_cods.append(cod_num)

            if bloqueadas:
                st.error(f"❌ Bloqueada(s) pois estão em uso no De-Para: {', '.join(bloqueadas)}")
            if permitidos_cods:
                cadastros_base["cores_eva"] = [
                    item for item in cadastros_base["cores_eva"] 
                    if int(item.get("codigo", -1)) not in permitidos_cods
                ]
                salvar_cadastros_base(cadastros_base)
                st.success("Cor(es) removida(s) com sucesso!")
                st.rerun()