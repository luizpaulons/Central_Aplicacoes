import io
import os
import re
from datetime import datetime
import streamlit as st
import pandas as pd
import imap_reader
import fatura_parser
import database

st.subheader("📑 Conciliar Fatura")

# Estilização leve para manter divisórias visíveis e alinhamento limpo
st.markdown(
    """
<style>
    hr { margin-top: 0.4rem !important; margin-bottom: 0.4rem !important; border-color: rgba(128, 128, 128, 0.25) !important; }
    .badge-parc {
        font-family: monospace;
        font-size: 0.78rem;
        background-color: rgba(100, 149, 237, 0.15);
        color: #4a90e2;
        padding: 2px 6px;
        border-radius: 4px;
        display: inline-block;
        margin-top: 4px;
    }
</style>
""",
    unsafe_allow_html=True,
)

config_env = imap_reader.obter_configuracoes_env()

if "lancamentos" not in st.session_state:
    st.session_state["lancamentos"] = []
if "emails_processados" not in st.session_state:
    st.session_state["emails_processados"] = []
if "fatura_atual" not in st.session_state:
    st.session_state["fatura_atual"] = None
if "vencimento_atual" not in st.session_state:
    st.session_state["vencimento_atual"] = ""
if "valor_total_atual" not in st.session_state:
    st.session_state["valor_total_atual"] = 0.0


def extrair_email_limpo(texto_remetente):
    if not texto_remetente:
        return ""
    m = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", str(texto_remetente))
    return m.group(0).lower().strip() if m else str(texto_remetente).lower().strip()


def calcular_proximidade_datas(data_compra_str, data_fatura_str):
    if not data_compra_str or not data_fatura_str:
        return 50
    try:
        pc = data_compra_str.split("/")
        pf = data_fatura_str.split("/")
        dia_c, mes_c = int(pc[0]), int(pc[1])
        dia_f, mes_f = int(pf[0]), int(pf[1])
        if mes_c == mes_f:
            return abs(dia_f - dia_c)
        elif abs(mes_f - mes_c) == 1:
            return abs((dia_f + 30) - dia_c)
        return 999
    except:
        return 999


def parse_data_ordenacao(data_str):
    if not data_str:
        return datetime.min
    try:
        partes = str(data_str).strip().split("/")
        if len(partes) == 3:
            return datetime.strptime(
                f"{int(partes[0]):02d}/{int(partes[1]):02d}/{partes[2]}", "%d/%m/%Y"
            )
        elif len(partes) == 2:
            return datetime.strptime(
                f"{int(partes[0]):02d}/{int(partes[1]):02d}/2026", "%d/%m/%Y"
            )
        return datetime.min
    except:
        return datetime.min


# Normaliza mapa de compradores para busca rápida
mapa_compradores_raw = database.listar_compradores()
mapa_compradores = {
    extrair_email_limpo(k): v.strip() for k, v in mapa_compradores_raw.items() if k
}
recorrencias_ativas = database.listar_recorrencias()


def sincronizar_compradores(lista_itens):
    """Atualiza compradores apenas nos itens que ainda estão como 'Não identificado'."""
    for it in lista_itens:
        if it.get("comprador", "Não identificado") in ["Não identificado", ""]:
            em = extrair_email_limpo(it.get("email_remetente", ""))
            if em and em in mapa_compradores:
                it["comprador"] = mapa_compradores[em]


# Carrega fatura mais recente do banco ao abrir ou dar F5
if not st.session_state["lancamentos"]:
    faturas_cadastradas = database.listar_faturas()
    if faturas_cadastradas:
        fat_recente = faturas_cadastradas[0]
        venc_rec = fat_recente[2]
        status_db, dados_salvos = database.carregar_fatura(venc_rec)
        if dados_salvos:
            st.session_state["fatura_atual"] = fat_recente[1]
            st.session_state["vencimento_atual"] = venc_rec
            st.session_state["valor_total_atual"] = fat_recente[3]
            st.session_state["fatura_fechada"] = status_db == "FECHADA"

            ano_fat = (
                venc_rec.split("/")[2]
                if "/" in venc_rec and len(venc_rec.split("/")) == 3
                else "2026"
            )
            for it in dados_salvos:
                if "fornecedor" not in it:
                    it["fornecedor"] = it.get("descricao", "")
                if "comprador" not in it:
                    it["comprador"] = "Não identificado"
                if "anexos_nf" not in it:
                    it["anexos_nf"] = [it["anexo_nf"]] if it.get("anexo_nf") else []
                dt = str(it.get("data_fatura", ""))
                if len(dt) == 5 and "/" in dt:
                    it["data_fatura"] = f"{dt}/{ano_fat}"
                if "numeros_nf" not in it:
                    anexos = it.get("anexos_nf", [])
                    it["numeros_nf"] = (
                        [imap_reader.extrair_numero_nf_pdf("", a) for a in anexos]
                        if anexos
                        else []
                    )

            sincronizar_compradores(dados_salvos)
            st.session_state["lancamentos"] = dados_salvos

# =============================================================
# 1. UPLOAD DA FATURA (COM VALIDAÇÃO DE LAYOUT) E LEITURA DE E-MAILS
# =============================================================
col1, col2 = st.columns([1.2, 1])
with col1:
    uploaded_file = st.file_uploader(
        "1. Faça o upload da fatura (.xlsx)",
        type=["xlsx"],
        key="uploader_fatura_principal",
    )
with col2:
    st.write("2. Leitura dos E-mails Corporativos")
    ler_emails = st.button("📥 Buscar E-mails da Pasta 'Cartao de credito'")

if uploaded_file is not None:
    arquivo_id = f"{uploaded_file.name}_{uploaded_file.size}"
    if st.session_state.get("ultimo_upload_id") != arquivo_id:
        sucesso_layout, ret_venc, valor_total, lancs = (
            fatura_parser.processar_fatura_xlsx(uploaded_file.getvalue())
        )
        st.session_state["ultimo_upload_id"] = arquivo_id

        if not sucesso_layout:
            st.error(f"🚫 **Arquivo fora do layout:** {ret_venc}")
        else:
            vencimento = ret_venc
            st.session_state["fatura_atual"] = uploaded_file.name
            st.session_state["vencimento_atual"] = vencimento
            st.session_state["valor_total_atual"] = valor_total

            status_db, dados_salvos = database.carregar_fatura(vencimento)
            if dados_salvos:
                ano_fat = (
                    vencimento.split("/")[2]
                    if "/" in vencimento and len(vencimento.split("/")) == 3
                    else "2026"
                )
                for it in dados_salvos:
                    if "fornecedor" not in it:
                        it["fornecedor"] = it.get("descricao", "")
                    if "comprador" not in it:
                        it["comprador"] = "Não identificado"
                    if "anexos_nf" not in it:
                        it["anexos_nf"] = [it["anexo_nf"]] if it.get("anexo_nf") else []
                    dt = str(it.get("data_fatura", ""))
                    if len(dt) == 5 and "/" in dt:
                        it["data_fatura"] = f"{dt}/{ano_fat}"
                sincronizar_compradores(dados_salvos)
                st.session_state["lancamentos"] = dados_salvos
                st.session_state["fatura_fechada"] = status_db == "FECHADA"
            else:
                ano_fat = (
                    vencimento.split("/")[2]
                    if "/" in vencimento and len(vencimento.split("/")) == 3
                    else "2026"
                )
                for it in lancs:
                    if len(it["data_fatura"]) == 5:
                        it["data_fatura"] = f"{it['data_fatura']}/{ano_fat}"

                    # Herança de Parcela >= 2
                    if it.get("num_parcela", 1) >= 2:
                        anexos_p1, comp_p1 = database.buscar_nf_parcela_1(
                            it["fornecedor"]
                        )
                        if anexos_p1:
                            it["anexos_nf"] = anexos_p1
                            it["numeros_nf"] = [
                                imap_reader.extrair_numero_nf_pdf("", a)
                                for a in anexos_p1
                            ]
                            it["status"] = "CONCILIADO"
                            it["tipo"] = "Fiscal (Parcela Recorrente)"
                            if comp_p1:
                                it["comprador"] = comp_p1

                # Validação automática de Assinaturas e Contratos cadastrados
                for it in lancs:
                    if it.get("status") == "CONCILIADO":
                        continue
                    for rec in recorrencias_ativas:
                        rec_tipo, rec_forn, rec_val, rec_comp = (
                            rec[1],
                            rec[2].upper().strip(),
                            float(rec[3]),
                            rec[4],
                        )
                        nome_forn = it.get("fornecedor", "").upper()
                        if rec_forn and rec_forn in nome_forn:
                            if abs(it["valor"] - rec_val) < 0.05:
                                it["status"] = "CONCILIADO"
                                it["tipo"] = rec_tipo
                                it["comprador"] = rec_comp or "Empresa"
                                it["recorrente_salvo"] = True
                            else:
                                it["status"] = "PENDENTE"
                                it["observacao"] = (
                                    f"ALERTA: {rec_tipo} com valor divergente! Esperado: R$ {rec_val:,.2f}"
                                )

                st.session_state["lancamentos"] = lancs
                st.session_state["fatura_fechada"] = False
                # Salva rascunho inicial no banco para não perder no F5
                database.salvar_fatura(
                    uploaded_file.name, vencimento, valor_total, lancs
                )
            st.rerun()

vencimento = st.session_state["vencimento_atual"]
valor_total = st.session_state["valor_total_atual"]
lancamentos = st.session_state["lancamentos"]
fatura_fechada = st.session_state.get("fatura_fechada", False)

if lancamentos:
    st.info(
        f"**Fatura:** {st.session_state.get('fatura_atual', '')} | **Vencimento:** {vencimento} | **Valor Total:** R$ {valor_total:,.2f}"
    )

    # =============================================================
    # 2. BUSCA E CRUZAMENTO DE E-MAILS
    # =============================================================
    if ler_emails and not fatura_fechada:
        with st.spinner("Buscando e cruzando e-mails..."):
            sucesso, res = imap_reader.buscar_emails_imap(
                config_env["host"],
                config_env["port"],
                config_env["user"],
                config_env["password"],
                config_env["folder"],
            )
            if not sucesso:
                st.error(f"Erro: {res}")
            else:
                st.session_state["emails_processados"] = res
                for e in st.session_state["emails_processados"]:
                    e["vinculado"] = False
                    e["motivo_falha"] = ""

                itens_usados = set()

                for email_compra in st.session_state["emails_processados"]:
                    valor_pago = email_compra["valor_pago"]
                    email_rem = extrair_email_limpo(email_compra.get("remetente", ""))
                    nome_comp = mapa_compradores.get(email_rem, "Não identificado")
                    data_compra_email = email_compra.get("data_compra", "")
                    anexos_email = email_compra.get("anexos_nf", [])
                    numeros_nf_email = email_compra.get("numeros_nf", [])

                    # Verifica vínculo prévio por anexo
                    vinculo_anterior = False
                    if anexos_email:
                        for idx_it, it in enumerate(lancamentos):
                            if idx_it in itens_usados:
                                continue
                            if any(a in it.get("anexos_nf", []) for a in anexos_email):
                                email_compra["vinculado"] = True
                                it["status"] = "CONCILIADO"
                                it["email_remetente"] = email_rem
                                if nome_comp != "Não identificado":
                                    it["comprador"] = nome_comp
                                it["numeros_nf"] = numeros_nf_email
                                itens_usados.add(idx_it)
                                vinculo_anterior = True
                                break
                    if vinculo_anterior:
                        continue

                    candidatos = []
                    for idx_it, it in enumerate(lancamentos):
                        if idx_it in itens_usados:
                            continue
                        valor_item = it.get("valor", 0.0)
                        match_valor = False

                        if abs(valor_item - valor_pago) < 0.05:
                            match_valor = True
                        elif email_compra.get("parcelas", 1) > 1:
                            val_div = valor_pago / email_compra["parcelas"]
                            if abs(valor_item - val_div) < 0.08:
                                match_valor = True

                        if match_valor:
                            diff_dias = calcular_proximidade_datas(
                                data_compra_email, it.get("data_fatura", "")
                            )
                            forn_it = (it.get("fornecedor") or "").upper()
                            prio_parc = (
                                0
                                if (
                                    email_compra.get("parcelas", 1) > 1
                                    and (
                                        "PARC" in forn_it
                                        or re.search(r"\d+D\d+", forn_it)
                                    )
                                )
                                else 10
                            )
                            candidatos.append((prio_parc, diff_dias, idx_it, it))

                    if candidatos:
                        candidatos.sort(key=lambda x: (x[0], x[1]))
                        _, _, idx_esc, melhor_item = candidatos[0]
                        melhor_item["status"] = "CONCILIADO"
                        melhor_item["tipo"] = email_compra.get("tipo", "Fiscal")
                        melhor_item["email_remetente"] = email_rem
                        if nome_comp != "Não identificado":
                            melhor_item["comprador"] = nome_comp
                        melhor_item["anexos_nf"] = anexos_email
                        melhor_item["numeros_nf"] = numeros_nf_email
                        email_compra["vinculado"] = True
                        itens_usados.add(idx_esc)
                    else:
                        if email_compra.get("parcelas", 1) > 1:
                            val_calc = valor_pago / email_compra["parcelas"]
                            email_compra["motivo_falha"] = (
                                f"Parcela (~R$ {val_calc:,.2f}) não encontrada na fatura"
                            )
                        else:
                            email_compra["motivo_falha"] = (
                                f"Valor (R$ {valor_pago:,.2f}) não encontrado na fatura"
                            )

                database.salvar_fatura(
                    st.session_state["fatura_atual"] or "Fatura",
                    vencimento,
                    valor_total,
                    lancamentos,
                )
                st.success(f"{len(res)} e-mails processados.")

    # Detalhes dos E-mails Lidos
    if st.session_state["emails_processados"]:
        tot_e = len(st.session_state["emails_processados"])
        vinc_e = sum(
            1 for e in st.session_state["emails_processados"] if e["vinculado"]
        )
        with st.expander(
            f"📬 Detalhes dos E-mails Lidos ({vinc_e} vinculados / {tot_e - vinc_e} não vinculados)"
        ):
            dados_tabela_email = []
            for idx_e, e in enumerate(st.session_state["emails_processados"], start=1):
                em_l = extrair_email_limpo(e["remetente"])
                motivo = (
                    "Vinculado com Sucesso ✔"
                    if e["vinculado"]
                    else (e.get("motivo_falha") or "Pendente de correspondência")
                )
                dados_tabela_email.append(
                    {
                        "Nº": idx_e,
                        "E-mail": em_l,
                        "Comprador": mapa_compradores.get(em_l, "Não cadastrado"),
                        "Data": e["data_compra"] or "-",
                        "Valor": f"R$ {e['valor_pago']:,.2f}",
                        "NF": ", ".join(e.get("numeros_nf", [])) or "-",
                        "Vinculado?": "SIM ✔" if e["vinculado"] else "NÃO ❌",
                        "Motivo / Diagnóstico": motivo,
                    }
                )
            st.dataframe(
                pd.DataFrame(dados_tabela_email).set_index("Nº"),
                use_container_width=True,
            )

    # =============================================================
    # 3. FILTROS E ORDENAÇÃO
    # =============================================================
    st.markdown("### Lançamentos da Fatura")
    total_itens = len(lancamentos)
    conciliados_count = sum(
        1 for x in lancamentos if str(x.get("status", "")).upper() == "CONCILIADO"
    )
    pendentes_count = total_itens - conciliados_count

    def checar_parcelado(it):
        nome_f = (it.get("fornecedor") or it.get("descricao", "")).upper()
        tem_d = bool(re.search(r"(?:AUTO)?\d{1,2}D\d{1,2}", nome_f, re.IGNORECASE))
        return bool(it.get("parcela") or "PARC" in nome_f or tem_d)

    parcelados_count = sum(1 for x in lancamentos if checar_parcelado(x))

    rotulos_filtro = {
        "TODOS": f"Todos ({total_itens})",
        "PENDENTES": f"⏳ Pendentes ({pendentes_count})",
        "CONCILIADOS": f"✔ Conciliados ({conciliados_count})",
        "PARCELADOS": f"💳 Parcelados ({parcelados_count})",
    }

    col_f, col_ord = st.columns([2.0, 1])
    with col_f:
        filtro_sel = st.radio(
            "Filtrar lançamentos:",
            options=["TODOS", "PENDENTES", "CONCILIADOS", "PARCELADOS"],
            format_func=lambda x: rotulos_filtro[x],
            key="filtro_ativo",
            horizontal=True,
        )
    with col_ord:
        ordem_sel = st.selectbox(
            "Ordenar por:",
            [
                "Ordem da Fatura",
                "Data (Crescente)",
                "Data (Decrescente)",
                "Valor (Maior)",
                "Valor (Menor)",
                "Fornecedor",
            ],
        )

    indices = list(range(len(lancamentos)))
    if ordem_sel == "Data (Crescente)":
        indices.sort(
            key=lambda i: parse_data_ordenacao(lancamentos[i].get("data_fatura", ""))
        )
    elif ordem_sel == "Data (Decrescente)":
        indices.sort(
            key=lambda i: parse_data_ordenacao(lancamentos[i].get("data_fatura", "")),
            reverse=True,
        )
    elif ordem_sel == "Valor (Maior)":
        indices.sort(key=lambda i: lancamentos[i].get("valor", 0.0), reverse=True)
    elif ordem_sel == "Valor (Menor)":
        indices.sort(key=lambda i: lancamentos[i].get("valor", 0.0))
    elif ordem_sel == "Fornecedor":
        indices.sort(key=lambda i: (lancamentos[i].get("fornecedor") or "").lower())

    # =============================================================
    # 4. CABEÇALHO E GRID DOS LANÇAMENTOS
    # =============================================================
    col_widths = [1.0, 2.5, 1.1, 1.7, 1.3, 1.0, 1.9, 1.4]
    h1, h2, h3, h4, h5, h6, h7, h8 = st.columns(col_widths)
    h1.markdown("**Data**")
    h2.markdown("**Fornecedor**")
    h3.markdown("**Valor**")
    h4.markdown("**Comprador**")
    h5.markdown("**Anexos**")
    h6.markdown("**Nº da NF**")
    h7.markdown("**Conciliação Manual**")
    h8.markdown("**Status**")
    st.divider()

    lista_base_compradores = sorted(
        list(
            set(
                list(mapa_compradores.values())
                + ["Não identificado", "Terceiros", "Empresa"]
            )
        )
    )

    # Callback para atualizar comprador sem travar ou reverter
    def on_change_comprador(indice_item):
        novo_valor = st.session_state[f"sel_comp_{indice_item}"]
        st.session_state["lancamentos"][indice_item]["comprador"] = novo_valor

    for idx in indices:
        item = lancamentos[idx]
        status_item = str(item.get("status", "PENDENTE")).upper().strip()
        forn_nome = item.get("fornecedor") or item.get("descricao", "")

        # Info de parcelamento
        parc_info = item.get("parcela")
        m_d = re.search(r"(?:AUTO)?(\d{1,2})D(\d{1,2})", forn_nome, re.IGNORECASE)
        if not parc_info and m_d:
            parc_info = f"{int(m_d.group(1))}/{int(m_d.group(2))}"
        eh_parcelado = bool(parc_info or "PARC" in forn_nome.upper() or m_d)

        if filtro_sel == "PENDENTES" and status_item == "CONCILIADO":
            continue
        if filtro_sel == "CONCILIADOS" and status_item != "CONCILIADO":
            continue
        if filtro_sel == "PARCELADOS" and not eh_parcelado:
            continue

        with st.container():
            c1, c2, c3, c4, c5, c6, c7, c8 = st.columns(col_widths)

            # 1. Data
            c1.write(f"**{item.get('data_fatura', '')}**")

            # 2. Fornecedor
            c2.write(forn_nome)
            if item.get("observacao") and "ALERTA" in item["observacao"]:
                c2.caption(f"⚠️ {item['observacao']}")

            # 3. Valor
            c3.write(f"R$ {item.get('valor', 0.0):,.2f}")

            # 4. Comprador (Livre para alteração manual sem reverter)
            with c4:
                comp_atual = item.get("comprador") or "Não identificado"
                if not fatura_fechada:
                    opcoes_comp = list(lista_base_compradores)
                    if comp_atual not in opcoes_comp:
                        opcoes_comp.append(comp_atual)

                    st.selectbox(
                        "Comprador",
                        options=opcoes_comp,
                        index=opcoes_comp.index(comp_atual),
                        key=f"sel_comp_{idx}",
                        on_change=on_change_comprador,
                        args=(idx,),
                        label_visibility="collapsed",
                    )
                else:
                    st.write(comp_atual)

            # 5. Anexos
            anexos = item.get("anexos_nf", [])
            with c5:
                if anexos:
                    for id_a, n_arq in enumerate(anexos):
                        caminho_nf = os.path.join(imap_reader.NOTAS_DIR, n_arq)
                        if os.path.exists(caminho_nf):
                            with open(caminho_nf, "rb") as f_pdf:
                                st.download_button(
                                    label=f"📄 {n_arq[:12]}...",
                                    data=f_pdf.read(),
                                    file_name=n_arq,
                                    mime="application/pdf",
                                    key=f"btn_nf_{idx}_{id_a}",
                                )
                else:
                    st.write("-")

            # 6. Nº da NF
            with c6:
                nums = [n for n in item.get("numeros_nf", []) if n and n != "-"]
                if nums:
                    for n in nums:
                        st.markdown(f"`{n}`")
                else:
                    st.write("-")

            # 7. Conciliação Manual
            with c7:
                tem_nf = len(anexos) > 0
                if fatura_fechada:
                    st.caption(f"🔒 {item.get('tipo', 'Consolidado')}")
                elif tem_nf or item.get("tipo") in [
                    "Fiscal",
                    "Fiscal (Parcela Recorrente)",
                ]:
                    st.caption("✔ Automático (NF Vinculada)")
                else:
                    opcoes_m = [
                        "Pendente",
                        "Assinatura",
                        "Contrato",
                        "Despesa de Terceiro",
                        "Aprovação Gerencial",
                    ]
                    tipo_atual = (
                        item.get("tipo") if item.get("tipo") in opcoes_m else "Pendente"
                    )
                    acao = st.selectbox(
                        "Ação",
                        opcoes_m,
                        index=opcoes_m.index(tipo_atual),
                        key=f"manual_{idx}",
                        label_visibility="collapsed",
                    )

                    if acao in ["Assinatura", "Contrato"]:
                        # Atualiza o status e tipo no item
                        mudou_estado = (
                            item.get("status") != "CONCILIADO"
                            or item.get("tipo") != acao
                        )
                        item["status"] = "CONCILIADO"
                        item["tipo"] = acao

                        if not item.get("recorrente_salvo", False):
                            salvar_rec = st.checkbox(
                                f"💾 Salvar {acao}?", key=f"chk_rec_{idx}"
                            )
                            if salvar_rec:
                                comp_para_salvar = item.get("comprador")
                                if (
                                    not comp_para_salvar
                                    or comp_para_salvar == "Não identificado"
                                ):
                                    comp_para_salvar = "Empresa"
                                    item["comprador"] = "Empresa"

                                database.salvar_recorrencia(
                                    tipo=acao,
                                    fornecedor=forn_nome,
                                    valor=float(item.get("valor", 0.0)),
                                    comprador=comp_para_salvar,
                                    obs=f"Salvo da fatura de {vencimento}",
                                )
                                item["recorrente_salvo"] = True
                                # Salva a fatura no banco imediatamente para persistir após F5!
                                database.salvar_fatura(
                                    st.session_state["fatura_atual"] or "Fatura",
                                    vencimento,
                                    valor_total,
                                    lancamentos,
                                )
                                st.toast(
                                    f"{acao} salva em Assinaturas e Contratos!",
                                    icon="✅",
                                )
                                st.rerun()
                        else:
                            st.caption(f"✔ {acao} salva")

                        # Se marcou como Assinatura/Contrato sem marcar o checkbox ainda, persiste o status
                        if mudou_estado:
                            database.salvar_fatura(
                                st.session_state["fatura_atual"] or "Fatura",
                                vencimento,
                                valor_total,
                                lancamentos,
                            )
                            st.rerun()

                    elif acao != "Pendente":
                        mudou_estado = (
                            item.get("status") != "CONCILIADO"
                            or item.get("tipo") != acao
                        )
                        item["status"] = "CONCILIADO"
                        item["tipo"] = acao
                        if mudou_estado:
                            database.salvar_fatura(
                                st.session_state["fatura_atual"] or "Fatura",
                                vencimento,
                                valor_total,
                                lancamentos,
                            )
                            st.rerun()
                    else:
                        if item.get("status") == "CONCILIADO" and not tem_nf:
                            item["status"] = "PENDENTE"
                            item["tipo"] = ""
                            item["recorrente_salvo"] = False
                            database.salvar_fatura(
                                st.session_state["fatura_atual"] or "Fatura",
                                vencimento,
                                valor_total,
                                lancamentos,
                            )
                            st.rerun()

            # 8. Status + Parcelado abaixo
            with c8:
                if item.get("status") == "CONCILIADO":
                    st.success("✔ Conciliado")
                else:
                    st.warning("⏳ Pendente")

                if eh_parcelado:
                    label_p = f"Parcelado ({parc_info})" if parc_info else "Parcelado"
                    st.markdown(
                        f"<span class='badge-parc'>{label_p}</span>",
                        unsafe_allow_html=True,
                    )

            st.divider()

    # =============================================================
    # 5. BOTÕES DE SALVAMENTO E FECHAMENTO
    # =============================================================
    if not fatura_fechada:
        pendentes = sum(1 for x in lancamentos if x.get("status") == "PENDENTE")
        col_s, col_f = st.columns([1, 1])
        with col_s:
            if st.button("💾 Salvar Rascunho"):
                database.salvar_fatura(
                    st.session_state["fatura_atual"] or "Fatura",
                    vencimento,
                    valor_total,
                    lancamentos,
                )
                st.success("Progresso salvo com sucesso!")
        with col_f:
            if pendentes > 0:
                st.button(f"🔒 Fechar Fatura ({pendentes} pendentes)", disabled=True)
            else:
                if st.button("🔒 Fechar Fatura Definitivamente", type="primary"):
                    database.fechar_fatura(vencimento, lancamentos)
                    st.session_state["fatura_fechada"] = True
                    st.success("Fatura fechada e consolidada com sucesso!")
                    st.rerun()
else:
    st.info(
        "Nenhuma fatura carregada. Faça o upload do arquivo .xlsx acima para visualizar os lançamentos."
    )
