import streamlit as st
import os
import re
import io
import pandas as pd
from datetime import datetime
import imap_reader
import fatura_parser
import database

st.subheader("📑 Conciliar Fatura")

# Estilos CSS com linhas divisórias sutis, badges de status e tag parcelada monoespaçada
st.markdown("""
    <style>
        hr {
            margin-top: 0.45rem !important;
            margin-bottom: 0.45rem !important;
            border: 0 !important;
            border-top: 1px solid rgba(120, 130, 140, 0.25) !important;
        }
        .status-badge-conciliado {
            background-color: #d1e7dd;
            color: #0f5132;
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 0.80rem;
            font-weight: 600;
            display: inline-block;
            white-space: nowrap;
            text-align: center;
        }
        .status-badge-pendente {
            background-color: #fff3cd;
            color: #664d03;
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 0.80rem;
            font-weight: 600;
            display: inline-block;
            white-space: nowrap;
            text-align: center;
        }
        .badge-parcelado {
            background-color: #e3f2fd;
            color: #0d47a1;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 0.74rem;
            font-family: monospace;
            font-weight: 600;
            display: inline-block;
            white-space: nowrap;
            margin-top: 3px;
            text-align: center;
        }
    </style>
""", unsafe_allow_html=True)

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

def extrair_email_limpo(remetente_str):
    if not remetente_str:
        return ""
    m = re.search(r"[\w\.-]+@[\w\.-]+", str(remetente_str).lower())
    return m.group(0).strip() if m else str(remetente_str).lower().strip()

mapa_compradores = database.listar_compradores()
recorrencias_ativas = database.listar_recorrencias()

def obter_nome_comprador(email_remetente):
    if not email_remetente:
        return "Não identificado"
    email_l = extrair_email_limpo(email_remetente)
    for k, v in mapa_compradores.items():
        if k.strip().lower() == email_l or k.strip().lower() in str(email_remetente).lower():
            return v
    return "Não identificado"

def sincronizar_compradores(lista_lancs):
    # 1. Puxa dos e-mails processados na sessão
    if st.session_state.get("emails_processados"):
        for e in st.session_state["emails_processados"]:
            rem_email = extrair_email_limpo(e.get("remetente", ""))
            nome_comp = obter_nome_comprador(rem_email)
            if nome_comp == "Não identificado":
                continue

            anexos_email = e.get("anexos_nf", [])
            v_pago = e.get("valor_pago", 0.0)

            for idx_it, it in enumerate(lista_lancs):
                anexos_it = it.get("anexos_nf", [])
                match_anexo = any(a in anexos_it for a in anexos_email) if (anexos_it and anexos_email) else False
                val_it = it.get("valor", 0.0)
                match_valor = abs(val_it - v_pago) < 0.05
                if not match_valor and e.get("parcelas", 1) > 1:
                    match_valor = abs(val_it - (v_pago / e["parcelas"])) < 0.08

                if match_anexo or match_valor:
                    it["email_remetente"] = rem_email
                    it["comprador"] = nome_comp
                    st.session_state[f"comp_{idx_it}"] = nome_comp

    # 2. Resolução direta em cada item da fatura
    for idx_it, it in enumerate(lista_lancs):
        comp_atual = it.get("comprador", "")
        if (not comp_atual or comp_atual == "Não identificado") and it.get("email_remetente"):
            resolved = obter_nome_comprador(it["email_remetente"])
            if resolved != "Não identificado":
                it["comprador"] = resolved
                st.session_state[f"comp_{idx_it}"] = resolved

        # Herança de parcelas anteriores salvas
        if (not it.get("comprador") or it.get("comprador") == "Não identificado") and it.get("num_parcela", 1) >= 2:
            _, comp_p1 = database.buscar_nf_parcela_1(it.get("fornecedor", it.get("descricao", "")))
            if comp_p1 and comp_p1 != "Não identificado":
                it["comprador"] = comp_p1
                st.session_state[f"comp_{idx_it}"] = comp_p1

def checar_parcelado(item):
    nome_f = (item.get("fornecedor") or item.get("descricao", "")).upper()
    tem_d = bool(re.search(r"(?:AUTO)?\d{1,2}D\d{1,2}", nome_f, re.IGNORECASE))
    return bool(item.get("parcela") or "PARC" in nome_f or tem_d)

def extrair_texto_parcela(item):
    parc_info = item.get("parcela")
    if parc_info:
        return f"Parcelado ({parc_info})"
    nome_f = item.get("fornecedor") or item.get("descricao", "")
    m_d = re.search(r"(?:AUTO)?(\d{1,2})D(\d{1,2})", nome_f, re.IGNORECASE)
    if m_d:
        p_atual, p_total = int(m_d.group(1)), int(m_d.group(2))
        return f"Parcelado ({p_atual}/{p_total})"
    return "Parcelado"

def calcular_proximidade_datas(data_compra_str, data_fatura_str):
    if not data_compra_str or not data_fatura_str:
        return 50
    try:
        partes_compra = data_compra_str.split("/")
        partes_fatura = data_fatura_str.split("/")
        dia_c, mes_c = int(partes_compra[0]), int(partes_compra[1])
        dia_f, mes_f = int(partes_fatura[0]), int(partes_fatura[1])
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
            return datetime.strptime(f"{int(partes[0]):02d}/{int(partes[1]):02d}/{partes[2]}", "%d/%m/%Y")
        elif len(partes) == 2:
            return datetime.strptime(f"{int(partes[0]):02d}/{int(partes[1]):02d}/2026", "%d/%m/%Y")
        return datetime.min
    except:
        return datetime.min

def padronizar_anexos_fatura(vencimento_str, lista_lancamentos):
    prefixo = imap_reader.formatar_vencimento_aammdd(vencimento_str)
    if not prefixo:
        return

    for item in lista_lancamentos:
        anexos_atuais = item.get("anexos_nf", [])
        novos_anexos = []
        novos_numeros = []

        for nome_arq in anexos_atuais:
            caminho_orig = os.path.join(imap_reader.NOTAS_DIR, nome_arq)
            m_ja_formatado = re.match(r'^\d{6}-(NFSe?)(.+)\.pdf$', nome_arq, re.IGNORECASE)
            if m_ja_formatado and not nome_arq.endswith("NFSe4.pdf"):
                novos_anexos.append(nome_arq)
                novos_numeros.append(m_ja_formatado.group(2))
                continue

            num_nf, eh_servico = imap_reader.extrair_numero_e_tipo_nf(caminho_orig, nome_arq)

            if num_nf and num_nf != "-":
                # Limpa prefixo de data se já veio colado no número (ex: 26110536 -> 36)
                num_str = str(num_nf).strip()
                if prefixo and num_str.startswith(prefixo) and len(num_str) > len(prefixo):
                    num_limpo = num_str[len(prefixo):]
                else:
                    num_limpo = num_str

                # Remove zeros extras à esquerda
                num_final = num_limpo.lstrip("0") or "0"

                tipo_tag = "NFSe" if eh_servico else "NF"
                novo_nome = f"{prefixo}-{tipo_tag}{num_final}.pdf"
                caminho_novo = os.path.join(imap_reader.NOTAS_DIR, novo_nome)

                if os.path.exists(caminho_orig) and caminho_orig != caminho_novo:
                    try:
                        os.replace(caminho_orig, caminho_novo)
                        novos_anexos.append(novo_nome)
                    except:
                        novos_anexos.append(nome_arq)
                else:
                    novos_anexos.append(novo_nome if os.path.exists(caminho_novo) else nome_arq)
                    
                novos_numeros.append(num_final)
            else:
                novos_anexos.append(nome_arq)
                novos_numeros.append(num_nf)

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
            st.session_state["fatura_fechada"] = (status_db == "FECHADA")
            
            ano_fat = venc_rec.split("/")[2] if "/" in venc_rec else "2026"
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

            padronizar_anexos_fatura(venc_rec, dados_salvos)
            sincronizar_compradores(dados_salvos)
            st.session_state["lancamentos"] = dados_salvos

col1, col2 = st.columns([1.5, 1])
with col1:
    uploaded_file = st.file_uploader("1. Faça o upload da fatura (.xlsx)", type=["xlsx"], key="uploader_fatura_cartao")
    if uploaded_file is not None:
        st.session_state["fatura_bytes"] = uploaded_file.getvalue()
        st.session_state["fatura_nome_arquivo"] = uploaded_file.name

with col2:
    st.write("2. Ações Rápidas")
    col_em, col_rst = st.columns(2)
    with col_em:
        ler_emails = st.button("📥 Buscar E-mails", width="stretch")
    with col_rst:
        if st.session_state.get("fatura_bytes") or st.session_state["lancamentos"]:
            if st.button("🗑 Limpar Sessão", width="stretch"):
                for k in ["fatura_bytes", "fatura_nome_arquivo", "lancamentos", "fatura_atual", "vencimento_atual", "valor_total_atual"]:
                    if k in st.session_state:
                        del st.session_state[k]
                for kw in list(st.session_state.keys()):
                    if kw.startswith("comp_"):
                        del st.session_state[kw]
                st.rerun()

nome_arq_sessao = st.session_state.get("fatura_nome_arquivo")
bytes_fatura_sessao = st.session_state.get("fatura_bytes")

if bytes_fatura_sessao and (st.session_state["fatura_atual"] != nome_arq_sessao):
    buffer_excel = io.BytesIO(bytes_fatura_sessao)
    vencimento, valor_total, lancs = fatura_parser.processar_fatura_xlsx(buffer_excel)
    st.session_state["fatura_atual"] = nome_arq_sessao
    st.session_state["vencimento_atual"] = vencimento
    st.session_state["valor_total_atual"] = valor_total

    for kw in list(st.session_state.keys()):
        if kw.startswith("comp_"):
            del st.session_state[kw]

    status_db, dados_salvos = database.carregar_fatura(vencimento)
    if dados_salvos:
        ano_fat = vencimento.split("/")[2] if "/" in vencimento else "2026"
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
        padronizar_anexos_fatura(vencimento, dados_salvos)
        sincronizar_compradores(dados_salvos)
        st.session_state["lancamentos"] = dados_salvos
        st.session_state["fatura_fechada"] = (status_db == "FECHADA")
    else:
        for it in lancs:
            if "fornecedor" not in it:
                it["fornecedor"] = it.get("descricao", "")
            
            # Reconhecimento Tokio Marine AUTO01D12 ou PARC convencional para herança de parcelas
            forn_txt = it["fornecedor"]
            m_tokio = re.search(r"(?:AUTO)?(\d{1,2})D(\d{1,2})", forn_txt, re.IGNORECASE)
            if m_tokio:
                it["num_parcela"] = int(m_tokio.group(1))
                it["parcela"] = f"{int(m_tokio.group(1))}/{int(m_tokio.group(2))}"

            if it.get("num_parcela", 1) >= 2:
                anexos_p1, comp_p1 = database.buscar_nf_parcela_1(it["fornecedor"])
                if anexos_p1:
                    it["anexos_nf"] = anexos_p1
                    it["numeros_nf"] = [imap_reader.extrair_numero_nf_pdf("", a) for a in anexos_p1]
                    it["status"] = "CONCILIADO"
                    it["tipo"] = "Fiscal (Parcela Recorrente)"
                    if comp_p1 and comp_p1 != "Não identificado":
                        it["comprador"] = comp_p1
                    it["observacao"] = "NF vinculada da Parcela 01"

        for it in lancs:
            if it.get("status") == "CONCILIADO":
                continue
            for rec in recorrencias_ativas:
                rec_tipo, rec_forn, rec_val, rec_comp = rec[1], rec[2].upper(), rec[3], rec[4]
                nome_forn = it.get("fornecedor", it.get("descricao", "")).upper()
                if rec_forn in nome_forn:
                    if abs(it["valor"] - rec_val) < 0.05:
                        it["status"] = "CONCILIADO"
                        it["tipo"] = rec_tipo
                        if rec_comp:
                            it["comprador"] = rec_comp
                        it["observacao"] = f"{rec_tipo} validada automaticamente"
                    else:
                        it["status"] = "PENDENTE"
                        it["observacao"] = f"ALERTA: {rec_tipo} com valor divergente! Esperado: R$ {rec_val:,.2f}"

        padronizar_anexos_fatura(vencimento, lancs)
        sincronizar_compradores(lancs)
        st.session_state["lancamentos"] = lancs
        st.session_state["fatura_fechada"] = False

vencimento = st.session_state["vencimento_atual"]
valor_total = st.session_state["valor_total_atual"]
lancamentos = st.session_state["lancamentos"]
fatura_fechada = st.session_state.get("fatura_fechada", False)

sincronizar_compradores(lancamentos)

if lancamentos:
    st.info(f"**Fatura:** {st.session_state.get('fatura_atual', '')} | **Vencimento:** {vencimento} | **Valor Total:** R$ {valor_total:,.2f}")

    if ler_emails and not fatura_fechada:
        host = config_env["host"]
        porta = config_env["port"]
        user = config_env["user"]
        pwd = config_env["password"]
        pasta = config_env["folder"]
        
        with st.spinner("Buscando e cruzando e-mails..."):
            sucesso, res = imap_reader.buscar_emails_imap(
                host, porta, user, pwd, pasta, data_vencimento_fatura=vencimento
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
                    nome_comp = obter_nome_comprador(email_rem)
                    
                    data_compra_email = email_compra.get("data_compra", "")
                    anexos_email = email_compra.get("anexos_nf", [])
                    numeros_nf_email = email_compra.get("numeros_nf", [])

                    vinculo_anterior = False
                    if anexos_email:
                        for idx_it, it in enumerate(lancamentos):
                            if idx_it in itens_usados:
                                continue
                            anexos_it = it.get("anexos_nf", [])
                            if any(a in anexos_it for a in anexos_email):
                                email_compra["vinculado"] = True
                                it["status"] = "CONCILIADO"
                                it["email_remetente"] = email_rem
                                if nome_comp != "Não identificado":
                                    it["comprador"] = nome_comp
                                    st.session_state[f"comp_{idx_it}"] = nome_comp
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
                        elif email_compra["parcelas"] > 1:
                            val_div = valor_pago / email_compra["parcelas"]
                            if abs(valor_item - val_div) < 0.08:
                                match_valor = True

                        if match_valor:
                            diff_dias = calcular_proximidade_datas(data_compra_email, it.get("data_fatura", ""))
                            forn_it = (it.get("fornecedor") or it.get("descricao", "")).upper()
                            prio_parc = 0 if (email_compra["parcelas"] > 1 and ("PARC" in forn_it or re.search(r"\d{1,2}D\d{1,2}", forn_it))) else 10
                            candidatos.append((prio_parc, diff_dias, idx_it, it))

                    if candidatos:
                        candidatos.sort(key=lambda x: (x[0], x[1]))
                        _, _, idx_esc, melhor_item = candidatos[0]
                        melhor_item["status"] = "CONCILIADO"
                        melhor_item["tipo"] = email_compra["tipo"]
                        melhor_item["email_remetente"] = email_rem
                        
                        if nome_comp != "Não identificado":
                            melhor_item["comprador"] = nome_comp
                            st.session_state[f"comp_{idx_esc}"] = nome_comp
                            
                        melhor_item["anexos_nf"] = anexos_email
                        melhor_item["numeros_nf"] = numeros_nf_email
                        obs_p = f" (Parcela {melhor_item.get('parcela')})" if melhor_item.get('parcela') else ""
                        melhor_item["observacao"] = f"Conciliado com e-mail de {data_compra_email}{obs_p}"
                        email_compra["vinculado"] = True
                        itens_usados.add(idx_esc)
                    else:
                        if email_compra["parcelas"] > 1:
                            val_calc = valor_pago / email_compra["parcelas"]
                            email_compra["motivo_falha"] = f"Parcela (~R$ {val_calc:,.2f}) não encontrada na fatura"
                        else:
                            email_compra["motivo_falha"] = f"Valor (R$ {valor_pago:,.2f}) não encontrado na fatura"

                padronizar_anexos_fatura(vencimento, lancamentos)
                sincronizar_compradores(lancamentos)
                st.success(f"{len(res)} e-mails processados.")
                st.rerun()

    # Detalhes dos E-mails
    if st.session_state["emails_processados"]:
        tot_e = len(st.session_state["emails_processados"])
        vinc_e = sum(1 for e in st.session_state["emails_processados"] if e["vinculado"])
        with st.expander(f"📬 Detalhes dos E-mails Lidos ({vinc_e} vinculados / {tot_e - vinc_e} não vinculados)"):
            dados_tabela_email = []
            for idx_e, e in enumerate(st.session_state["emails_processados"], start=1):
                motivo = "Vinculado com Sucesso ✔" if e["vinculado"] else (e.get("motivo_falha") or "Pendente de correspondência")
                dados_tabela_email.append({
                    "Nº": idx_e,
                    "E-mail": e["remetente"],
                    "Comprador": obter_nome_comprador(e["remetente"]),
                    "Data": e["data_compra"] or "-",
                    "Valor": f"R$ {e['valor_pago']:,.2f}",
                    "NF": ", ".join(e.get("numeros_nf", [])) or "-",
                    "Vinculado?": "SIM ✔" if e["vinculado"] else "NÃO ❌",
                    "Motivo / Diagnóstico": motivo
                })
            df_em = pd.DataFrame(dados_tabela_email).set_index("Nº")
            st.dataframe(df_em, width="stretch")

    # Contadores e Filtro com opção de Parcelados
    st.markdown("### Lançamentos da Fatura")
    total_itens = len(lancamentos)
    conciliados_count = sum(1 for x in lancamentos if str(x.get("status", "")).upper() == "CONCILIADO")
    pendentes_count = total_itens - conciliados_count
    parcelados_count = sum(1 for x in lancamentos if checar_parcelado(x))

    rotulos_filtro = {
        "TODOS": f"Todos ({total_itens})",
        "PENDENTES": f"⏳ Pendentes ({pendentes_count})",
        "CONCILIADOS": f"✔ Conciliados ({conciliados_count})",
        "PARCELADOS": f"💳 Parcelados ({parcelados_count})"
    }

    col_f, col_ord = st.columns([1.8, 1])
    with col_f:
        filtro_sel = st.radio(
            "Filtrar lançamentos:",
            options=["TODOS", "PENDENTES", "CONCILIADOS", "PARCELADOS"],
            format_func=lambda x: rotulos_filtro[x],
            key="filtro_ativo",
            horizontal=True
        )
    with col_ord:
        ordem_sel = st.selectbox(
            "Ordenar por:", 
            ["Ordem da Fatura", "Data (Crescente)", "Data (Decrescente)", "Valor (Maior)", "Valor (Menor)", "Fornecedor"]
        )

    indices = list(range(len(lancamentos)))
    if ordem_sel == "Data (Crescente)":
        indices.sort(key=lambda i: parse_data_ordenacao(lancamentos[i].get("data_fatura", "")))
    elif ordem_sel == "Data (Decrescente)":
        indices.sort(key=lambda i: parse_data_ordenacao(lancamentos[i].get("data_fatura", "")), reverse=True)
    elif ordem_sel == "Valor (Maior)":
        indices.sort(key=lambda i: lancamentos[i].get("valor", 0.0), reverse=True)
    elif ordem_sel == "Valor (Menor)":
        indices.sort(key=lambda i: lancamentos[i].get("valor", 0.0))
    elif ordem_sel == "Fornecedor":
        indices.sort(key=lambda i: (lancamentos[i].get("fornecedor") or lancamentos[i].get("descricao", "")).lower())

    larguras_cols = [1.0, 2.5, 1.2, 1.8, 1.3, 1.1, 1.8, 1.5]

    h1, h2, h3, h4, h5, h6, h7, h8 = st.columns(larguras_cols)
    h1.markdown("**Data**")
    h2.markdown("**Fornecedor**")
    h3.markdown("**Valor**")
    h4.markdown("**Comprador**")
    h5.markdown("**Anexos**")
    h6.markdown("**Nº da NF**")
    h7.markdown("**Conciliação Manual**")
    h8.markdown("**Status**")
    
    st.markdown("---")

    lista_opcoes_compradores = sorted(list(set(list(mapa_compradores.values()) + ["Não identificado", "Terceiros", "Empresa"])))

    for idx in indices:
        item = lancamentos[idx]
        status_item = str(item.get("status", "PENDENTE")).upper().strip()
        eh_parcelado = checar_parcelado(item)
        
        if filtro_sel == "PENDENTES" and status_item == "CONCILIADO":
            continue
        if filtro_sel == "CONCILIADOS" and status_item != "CONCILIADO":
            continue
        if filtro_sel == "PARCELADOS" and not eh_parcelado:
            continue

        with st.container():
            c1, c2, c3, c4, c5, c6, c7, c8 = st.columns(larguras_cols)
            
            # 1. Data
            dt_fat = item.get('data_fatura', '')
            c1.write(f"**{dt_fat}**")
            
            # 2. Fornecedor
            forn_nome = item.get("fornecedor") or item.get("descricao", "")
            c2.write(forn_nome)
            
            # 3. Valor
            c3.write(f"R$ {item.get('valor', 0.0):,.2f}")
            
            # 4. Comprador
            with c4:
                comp_atual = item.get("comprador", "Não identificado")
                
                if comp_atual != "Não identificado":
                    st.session_state[f"comp_{idx}"] = comp_atual

                if not fatura_fechada:
                    if comp_atual not in lista_opcoes_compradores:
                        lista_opcoes_compradores.append(comp_atual)
                    
                    idx_selectbox = lista_opcoes_compradores.index(comp_atual) if comp_atual in lista_opcoes_compradores else 0
                    escolha = st.selectbox(
                        "Comprador",
                        options=lista_opcoes_compradores,
                        index=idx_selectbox,
                        key=f"comp_{idx}",
                        label_visibility="collapsed"
                    )
                    item["comprador"] = escolha
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
                                    label=f"📄 {n_arq[:10]}...",
                                    data=f_pdf.read(),
                                    file_name=n_arq,
                                    mime="application/pdf",
                                    key=f"btn_nf_{idx}_{id_a}"
                                )
                elif item.get("tipo") == "Gerencial":
                    st.caption("Gerencial")
                else:
                    st.write("-")

            # 6. Nº NF
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
                elif tem_nf or item.get("tipo") in ["Fiscal", "Fiscal (Parcela Recorrente)"]:
                    st.caption("✔ Automático (NF)")
                else:
                    opcoes_m = ["Pendente", "Assinatura", "Contrato", "Despesa de Terceiro", "Aprovação Gerencial"]
                    idx_pad = opcoes_m.index(item["tipo"]) if item.get("tipo") in opcoes_m else 0
                    acao = st.selectbox("Ação", opcoes_m, index=idx_pad, key=f"manual_{idx}", label_visibility="collapsed")
                    
                    if acao in ["Assinatura", "Contrato"]:
                        item["status"] = "CONCILIADO"
                        item["tipo"] = acao
                        if not item.get("recorrente_salvo", False):
                            salvar_rec = st.checkbox(f"💾 Salvar {acao}?", key=f"chk_{idx}")
                            if salvar_rec:
                                database.salvar_recorrencia(
                                    tipo=acao, fornecedor=forn_nome, valor=item.get("valor", 0.0),
                                    comprador=item.get("comprador", "Empresa"), obs=f"Salvo da fatura de {vencimento}"
                                )
                                item["recorrente_salvo"] = True
                                st.success("Salvo!")
                                st.rerun()
                        else:
                            st.caption("✔ Recorrência salva")
                    elif acao != "Pendente":
                        item["status"] = "CONCILIADO"
                        item["tipo"] = acao
                    else:
                        item["status"] = "PENDENTE"
                        item["tipo"] = ""

            # 8. Status + Tag Parcelado logo abaixo
            with c8:
                if status_item == "CONCILIADO":
                    st.markdown("<span class='status-badge-conciliado'>✔ Conciliado</span>", unsafe_allow_html=True)
                else:
                    st.markdown("<span class='status-badge-pendente'>⏳ Pendente</span>", unsafe_allow_html=True)
                
                if eh_parcelado:
                    texto_parc = extrair_texto_parcela(item)
                    st.markdown(f"<div><span class='badge-parcelado'>{texto_parc}</span></div>", unsafe_allow_html=True)

            st.markdown("---")

    if not fatura_fechada:
        pendentes = sum(1 for x in lancamentos if str(x.get("status", "")).upper() != "CONCILIADO")
        col_s, col_f = st.columns([1, 1])
        with col_s:
            if st.button("💾 Salvar Rascunho", width="stretch"):
                database.salvar_fatura(st.session_state["fatura_atual"] or "Fatura", vencimento, valor_total, lancamentos)
                st.success("Progresso salvo com sucesso!")
        with col_f:
            if pendentes > 0:
                st.button(f"🔒 Fechar Fatura ({pendentes} pendentes)", disabled=True, width="stretch")
            else:
                if st.button("🔒 Fechar Fatura Definitivamente", type="primary", width="stretch"):
                    database.fechar_fatura(vencimento, lancamentos)
                    st.session_state["fatura_fechada"] = True
                    st.success("Fatura fechada e consolidada com sucesso!")
                    st.rerun()
else:
    st.info("Nenhuma fatura carregada. Faça o upload do arquivo .xlsx acima para visualizar os lançamentos.")