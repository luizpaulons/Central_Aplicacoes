import io
import os
import re
import streamlit as st
import pandas as pd
import database
import imap_reader

st.title("⚖ Confronto de Relatório (CHB x Fatura Consolidada)")
st.write(
    "Confronto entre notas/valores do CHB com a fatura consolidada e exibição do comprador."
)


def limpar_numero_nf(nf_str):
    if not nf_str:
        return ""
    d = re.sub(r"\D", "", str(nf_str))
    if len(d) == 44:
        d = d[25:34]
    return d.lstrip("0")


def converter_para_float(valor_obj):
    if valor_obj is None:
        return 0.0
    if isinstance(valor_obj, (int, float)):
        return float(valor_obj)
    val_str = (
        str(valor_obj)
        .strip()
        .replace("R$", "")
        .replace(" ", "")
        .replace(".", "")
        .replace(",", ".")
    )
    nums = re.findall(r"[-+]?\d*\.\d+|\d+", val_str)
    return float(nums[0]) if nums else 0.0


def extrair_dados_relatorio(arquivo_origem):
    if isinstance(arquivo_origem, bytes):
        fonte_dados = io.BytesIO(arquivo_origem)
    else:
        fonte_dados = arquivo_origem

    df_raw = pd.read_excel(fonte_dados, header=None)
    linha_inicio = 0
    for i in range(min(15, len(df_raw))):
        linha_texto = " ".join([str(v) for v in df_raw.iloc[i].values]).lower()
        if "título" in linha_texto or "titulo" in linha_texto:
            linha_inicio = i + 1
            break

    df_dados = df_raw.iloc[linha_inicio:].copy()
    itens_relatorio = []

    for _, row in df_dados.iterrows():
        val_nota = str(row.iloc[3]).strip() if pd.notna(row.iloc[3]) else ""
        val_saldo = row.iloc[15] if len(row) > 15 else None

        if not val_nota or val_nota.lower() in [
            "nan",
            "total",
            "subtotal",
            "vencidas",
            "nenhum",
            "título",
            "titulo",
        ]:
            continue

        nota_limpa = limpar_numero_nf(val_nota)
        if not nota_limpa:
            continue

        itens_relatorio.append(
            {
                "nota": nota_limpa,
                "nota_original": val_nota,
                "valor": round(converter_para_float(val_saldo), 2),
                "fornecedor_chb": (
                    str(row.iloc[2]).strip() if pd.notna(row.iloc[2]) else ""
                ),
            }
        )
    return itens_relatorio


# 1. Seleção da fatura
faturas_disponiveis = database.listar_faturas()
col_fat, _ = st.columns([2.5, 1.5])
with col_fat:
    if faturas_disponiveis:
        opcoes_venc = [f[2] for f in faturas_disponiveis]
        venc_atual_sessao = st.session_state.get("vencimento_atual")
        idx_padrao = (
            opcoes_venc.index(venc_atual_sessao)
            if venc_atual_sessao in opcoes_venc
            else 0
        )
        venc_selecionado = st.selectbox(
            "Fatura para confronto:", opcoes_venc, index=idx_padrao
        )
    else:
        st.warning("Nenhuma fatura encontrada. Importe uma primeiro.")
        venc_selecionado = None

# Usa prioritariamente os lançamentos em memória da sessão (iguais aos da tela Conciliar Fatura)
lancamentos_fatura = []
if venc_selecionado:
    if (
        st.session_state.get("lancamentos")
        and st.session_state.get("vencimento_atual") == venc_selecionado
    ):
        lancamentos_fatura = st.session_state["lancamentos"]
    else:
        status_db, dados_salvos = database.carregar_fatura(venc_selecionado)
        lancamentos_fatura = dados_salvos or []

# 2. Upload com persistência em st.session_state
col_up, col_atualizar, col_limpar = st.columns([2.6, 1.2, 1.2])
with col_up:
    upload_relatorio = st.file_uploader(
        "Upload do Relatório CHB (.xlsx - Coluna D: Nota | Coluna P: Saldo)",
        type=["xlsx"],
        key="uploader_relatorio_confronto",
    )

with col_atualizar:
    st.write("")
    st.write("")
    if st.button("🔄 Atualizar Confronto"):
        st.session_state.pop("confronto_resultado", None)
        st.rerun()

with col_limpar:
    st.write("")
    st.write("")
    if st.button("🗑 Limpar Relatório"):
        st.session_state.pop("relatorio_confronto_bytes", None)
        st.session_state.pop("confronto_resultado", None)
        st.rerun()

if upload_relatorio is not None:
    novo_bytes = upload_relatorio.getvalue()
    if st.session_state.get("relatorio_confronto_bytes") != novo_bytes:
        st.session_state["relatorio_confronto_bytes"] = novo_bytes
        st.session_state.pop("confronto_resultado", None)

bytes_salvos = st.session_state.get("relatorio_confronto_bytes")

# 3. Processamento e Exibição do Confronto
if bytes_salvos and lancamentos_fatura:
    # Cria assinatura dos dados da fatura para recalcular automaticamente se algo mudou na tela 1
    assinatura_fatura = str(
        [
            (
                x.get("fornecedor"),
                x.get("valor"),
                x.get("numeros_nf"),
                x.get("comprador"),
            )
            for x in lancamentos_fatura
        ]
    )

    if (
        "confronto_resultado" not in st.session_state
        or st.session_state.get("confronto_vencimento") != venc_selecionado
        or st.session_state.get("confronto_assinatura") != assinatura_fatura
    ):
        itens_rel = extrair_dados_relatorio(bytes_salvos)
        rel_disponiveis = list(itens_rel)
        encontrados = []
        nao_encontrados = []

        soma_fat_total = 0.0
        soma_chb_localizados = 0.0
        soma_fat_nao_localizados = 0.0
        soma_divergencias = 0.0
        qtd_divergencias = 0

        mapa_compradores = database.listar_compradores()

        for item in lancamentos_fatura:
            val_fat = round(converter_para_float(item.get("valor", 0.0)), 2)
            soma_fat_total += val_fat
            forn_fat = item.get("fornecedor") or item.get("descricao", "")
            data_fat = item.get("data_fatura", "")

            comprador_fat = item.get("comprador", "Não identificado")
            if comprador_fat in ["Não identificado", ""] and item.get(
                "email_remetente"
            ):
                email_l = item["email_remetente"].lower().strip()
                comprador_fat = mapa_compradores.get(email_l, "Não identificado")

            # Mantém exatamente as mesmas notas exibidas na coluna "Nº da NF" da tela Conciliar Fatura
            notas_oficiais = []
            for n in item.get("numeros_nf", []):
                n_str = str(n).strip()
                if not n_str or n_str in ["-", "None"]:
                    continue
                nl = limpar_numero_nf(n_str)
                if nl and nl not in notas_oficiais:
                    notas_oficiais.append(nl)

            # Fallback apenas se numeros_nf estiver vazio, mas houver PDFs anexados
            if not notas_oficiais:
                anexos = item.get("anexos_nf", [])
                if item.get("anexo_nf") and item["anexo_nf"] not in anexos:
                    anexos.append(item["anexo_nf"])

                for a in anexos:
                    if not a:
                        continue
                    num_extraido = imap_reader.extrair_numero_nf_pdf(
                        os.path.join(imap_reader.NOTAS_DIR, a), a
                    )
                    nl = limpar_numero_nf(num_extraido)
                    if nl and nl not in notas_oficiais:
                        notas_oficiais.append(nl)

            candidatos_nf = set(notas_oficiais)
            matches_encontrados = []
            tipo_match = ""

            # 1. Confronto por NF (Coluna D) - Captura todas as notas vinculadas à mesma compra para somar
            if candidatos_nf:
                for r in list(rel_disponiveis):
                    if r["nota"] in candidatos_nf:
                        matches_encontrados.append(r)
                        rel_disponiveis.remove(r)

            if matches_encontrados:
                notas_ident = [m["nota"] for m in matches_encontrados]
                if len(notas_ident) > 1:
                    tipo_match = (
                        f"Soma de {len(notas_ident)} notas ({', '.join(notas_ident)})"
                    )
                else:
                    tipo_match = f"Nota {notas_ident[0]} identificada"
            else:
                # 2. Confronto por Valor (Coluna P) caso não tenha encontrado pela NF
                for r in list(rel_disponiveis):
                    if abs(val_fat - r["valor"]) <= 0.08:
                        matches_encontrados.append(r)
                        rel_disponiveis.remove(r)
                        tipo_match = f"Valor correspondente (~R$ {val_fat:,.2f})"
                        break

            nf_fatura_exibicao = ", ".join(notas_oficiais) if notas_oficiais else "-"

            if matches_encontrados:
                val_chb_somado = round(sum(m["valor"] for m in matches_encontrados), 2)
                fornecedores_chb = " / ".join(
                    dict.fromkeys(
                        [
                            m["fornecedor_chb"]
                            for m in matches_encontrados
                            if m["fornecedor_chb"]
                        ]
                    )
                )
                notas_chb = ", ".join([m["nota_original"] for m in matches_encontrados])
                diff = round(abs(val_fat - val_chb_somado), 2)
                eh_divergente = diff > 0.009

                soma_chb_localizados += val_chb_somado
                if eh_divergente:
                    soma_divergencias += diff
                    qtd_divergencias += 1

                encontrados.append(
                    {
                        "Data": data_fat,  # Col 1
                        "Fornecedor Fatura": forn_fat,  # Col 2
                        "Comprador": comprador_fat,  # Col 3
                        "Fornecedor CHB": fornecedores_chb,  # Col 4
                        "NF Fatura": nf_fatura_exibicao,  # Col 5
                        "Valor Fatura": f"R$ {val_fat:,.2f}",  # Col 6
                        "NF CHB": notas_chb,  # Col 7
                        "Divergência": (
                            f"R$ {diff:,.2f}" if eh_divergente else "Exato ✔"
                        ),  # Col 8
                        "Valor CHB": f"R$ {val_chb_somado:,.2f}",  # Col 9
                        "Critério": tipo_match,  # Col 10
                        "_divergente": eh_divergente,  # Flag interna para filtro
                    }
                )
            else:
                soma_fat_nao_localizados += val_fat
                nao_encontrados.append(
                    {
                        "Data": data_fat,
                        "Fornecedor Fatura": forn_fat,
                        "Comprador": comprador_fat,
                        "Valor Fatura": f"R$ {val_fat:,.2f}",
                        "NF Fatura": (
                            nf_fatura_exibicao
                            if nf_fatura_exibicao != "-"
                            else "Sem NF vinculada"
                        ),
                        "Status na Fatura": item.get("status", "PENDENTE"),
                    }
                )

        st.session_state["confronto_resultado"] = {
            "encontrados": encontrados,
            "nao_encontrados": nao_encontrados,
            "total_fatura": len(lancamentos_fatura),
            "soma_fat_total": round(soma_fat_total, 2),
            "soma_chb_localizados": round(soma_chb_localizados, 2),
            "soma_fat_nao_localizados": round(soma_fat_nao_localizados, 2),
            "soma_divergencias": round(soma_divergencias, 2),
            "qtd_divergencias": qtd_divergencias,
        }
        st.session_state["confronto_vencimento"] = venc_selecionado
        st.session_state["confronto_assinatura"] = assinatura_fatura

    res = st.session_state["confronto_resultado"]
    encontrados = res["encontrados"]
    nao_encontrados = res["nao_encontrados"]

    # Métricas principais (4 colunas)
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric(
            label="Itens na Fatura",
            value=f"{res['total_fatura']} itens",
            delta=f"Total Fatura: R$ {res['soma_fat_total']:,.2f}",
            delta_color="off",
        )
    with m2:
        st.metric(
            label="Localizados no CHB",
            value=f"{len(encontrados)} itens",
            delta=f"Total CHB: R$ {res['soma_chb_localizados']:,.2f}",
        )
    with m3:
        st.metric(
            label="Não Localizados",
            value=f"{len(nao_encontrados)} itens",
            delta=f"Total Fatura: R$ {res['soma_fat_nao_localizados']:,.2f}",
            delta_color="inverse",
        )
    with m4:
        st.metric(
            label="Total Divergências",
            value=f"R$ {res['soma_divergencias']:,.2f}",
            delta=(
                f"{res['qtd_divergencias']} item(ns) divergente(s)"
                if res["qtd_divergencias"] > 0
                else "Sem divergências ✔"
            ),
            delta_color="inverse" if res["qtd_divergencias"] > 0 else "normal",
        )

    st.divider()

    tab1, tab2 = st.tabs(
        [
            f"✔ Localizados no CHB ({len(encontrados)} | R$ {res['soma_chb_localizados']:,.2f})",
            f"❌ Na Fatura, mas NÃO no CHB ({len(nao_encontrados)} | R$ {res['soma_fat_nao_localizados']:,.2f})",
        ]
    )

    with tab1:
        if encontrados:
            qtd_div = res["qtd_divergencias"]
            qtd_exatos = len(encontrados) - qtd_div

            rotulos_filtro_chb = {
                "TODOS": f"Todos ({len(encontrados)})",
                "DIVERGENTES": f"⚠️ Somente Divergentes ({qtd_div})",
                "EXATOS": f"✔ Exatos ({qtd_exatos})",
            }

            filtro_chb = st.radio(
                "Filtrar itens localizados:",
                options=["TODOS", "DIVERGENTES", "EXATOS"],
                format_func=lambda x: rotulos_filtro_chb[x],
                key="filtro_confronto_chb",
                horizontal=True,
            )

            if filtro_chb == "DIVERGENTES":
                lista_exibicao = [x for x in encontrados if x.get("_divergente", False)]
            elif filtro_chb == "EXATOS":
                lista_exibicao = [
                    x for x in encontrados if not x.get("_divergente", False)
                ]
            else:
                lista_exibicao = encontrados

            if lista_exibicao:
                df_ok = pd.DataFrame(lista_exibicao).drop(
                    columns=["_divergente"], errors="ignore"
                )
                df_ok.index = range(1, len(df_ok) + 1)
                st.dataframe(df_ok, use_container_width=True)
            else:
                st.info("Nenhum item encontrado para o filtro selecionado.")
        else:
            st.info("Nenhum item foi confrontado.")

    with tab2:
        if nao_encontrados:
            st.warning("Itens da fatura não localizados no relatório do CHB:")
            df_pend = pd.DataFrame(nao_encontrados)
            df_pend.index = range(1, len(df_pend) + 1)
            st.dataframe(df_pend, use_container_width=True)
        else:
            st.success(
                "Todos os itens da fatura foram identificados no relatório do CHB!"
            )

elif not bytes_salvos:
    st.info("Envie o relatório financeiro `.xlsx` acima para gerar o confronto.")
