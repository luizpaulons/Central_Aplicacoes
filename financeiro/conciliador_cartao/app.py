import streamlit as st
import os
import pandas as pd
from dotenv import load_dotenv
import imap_reader
import fatura_parser
import database

load_dotenv()

st.set_page_config(page_title="Conciliação de Cartão de Crédito", layout="wide")
database.init_db()

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

st.title("💳 Conciliação de Cartão de Crédito")

menu = st.sidebar.selectbox("Navegação", ["Conciliar Fatura", "Consulta de Faturas", "Configurações (.env)"])

if menu == "Configurações (.env)":
    st.subheader("⚙ Configurações de Conexão IMAP")
    st.info("Configurações lidas do arquivo **.env**:")
    st.write(f"**Servidor IMAP:** `{config_env['host']}`")
    st.write(f"**Porta:** `{config_env['port']}`")
    st.write(f"**Usuário:** `{config_env['user']}`")
    st.write(f"**Pasta:** `{config_env['folder']}`")
    st.write(f"**Senha definida:** `{'Sim' if config_env['password'] else 'Não'}`")

elif menu == "Conciliar Fatura":
    col1, col2 = st.columns([1, 1])
    with col1:
        uploaded_file = st.file_uploader("1. Faça o upload da fatura (.xlsx)", type=["xlsx"])
    with col2:
        st.write("2. Leitura dos E-mails Corporativos")
        ler_emails = st.button("📥 Buscar E-mails da Pasta 'Cartao de credito'")

    if uploaded_file and (st.session_state["fatura_atual"] != uploaded_file.name):
        vencimento, valor_total, lancs = fatura_parser.processar_fatura_xlsx(uploaded_file)
        st.session_state["fatura_atual"] = uploaded_file.name
        st.session_state["vencimento_atual"] = vencimento
        st.session_state["valor_total_atual"] = valor_total

        status_db, dados_salvos = database.carregar_fatura(vencimento)
        if dados_salvos:
            st.session_state["lancamentos"] = dados_salvos
            st.session_state["fatura_fechada"] = (status_db == "FECHADA")
        else:
            st.session_state["lancamentos"] = lancs
            st.session_state["fatura_fechada"] = False

    vencimento = st.session_state["vencimento_atual"]
    valor_total = st.session_state["valor_total_atual"]
    lancamentos = st.session_state["lancamentos"]
    fatura_fechada = st.session_state.get("fatura_fechada", False)

    if uploaded_file or lancamentos:
        st.info(f"**Vencimento:** {vencimento} | **Valor Total:** R$ {valor_total:,.2f}")

        # Busca e reconciliação dos e-mails
        if ler_emails and not fatura_fechada:
            host = config_env["host"]
            porta = config_env["port"]
            user = config_env["user"]
            pwd = config_env["password"]
            pasta = config_env["folder"]
            
            if not host or not user or not pwd:
                st.error("Credenciais incompletas no arquivo .env!")
            else:
                with st.spinner(f"Conectando a {host} e buscando e-mails..."):
                    sucesso, res = imap_reader.buscar_emails_imap(host, porta, user, pwd, pasta)
                    if not sucesso:
                        st.error(f"Erro na conexão IMAP: {res}")
                    else:
                        st.session_state["emails_processados"] = res
                        st.success(f"Conexão realizada com sucesso! {len(res)} e-mails processados.")
                        
                        # Reseta os vínculos para recalcular com precisão
                        for email_compra in st.session_state["emails_processados"]:
                            email_compra["vinculado"] = False

                        # Cruzamento inteligente
                        for email_compra in st.session_state["emails_processados"]:
                            valor_alvo = email_compra["valor_pago"]
                            
                            for item in lancamentos:
                                # Trata compra parcelada
                                val_comparar = valor_alvo
                                if email_compra["parcelas"] > 1 and item.get("parcela"):
                                    val_comparar = round(valor_alvo / email_compra["parcelas"], 2)
                                
                                # Verifica tolerância de centavos
                                if abs(item["valor"] - val_comparar) < 0.05:
                                    item["status"] = "CONCILIADO"
                                    item["tipo"] = email_compra["tipo"]
                                    item["anexos_nf"] = email_compra.get("anexos_nf", [])
                                    item["observacao"] = f"Conciliado com e-mail ({email_compra.get('data_compra')})"
                                    email_compra["vinculado"] = True
                                    break

        # Tabela de E-mails Lidos (Contagem começando em 1)
        if st.session_state["emails_processados"]:
            total_e = len(st.session_state["emails_processados"])
            vinc_e = sum(1 for e in st.session_state["emails_processados"] if e["vinculado"])
            nao_vinc_e = total_e - vinc_e
            
            with st.expander(f"📬 Ver Detalhes dos E-mails Lidos ({vinc_e} vinculados / {nao_vinc_e} não vinculados)", expanded=(nao_vinc_e > 0)):
                dados_tabela_email = []
                for idx, e in enumerate(st.session_state["emails_processados"], start=1):
                    anexos_str = ", ".join(e["anexos_nf"]) if e["anexos_nf"] else "Nenhum (PDF)"
                    dados_tabela_email.append({
                        "Nº": idx,
                        "Data Compra": e["data_compra"] or "N/D",
                        "Tipo": e["tipo"],
                        "Valor Pago": f"R$ {e['valor_pago']:,.2f}",
                        "Parcelas": f"{e['parcelas']}x",
                        "Vinculado à Fatura?": "SIM ✔" if e["vinculado"] else "NÃO ❌",
                        "Qtd NFs (PDF)": len(e["anexos_nf"]),
                        "NFs em PDF": anexos_str
                    })
                
                df_emails = pd.DataFrame(dados_tabela_email)
                df_emails.index = df_emails["Nº"]
                st.dataframe(df_emails.drop(columns=["Nº"]), use_container_width=True)

        if fatura_fechada:
            st.warning("🔒 Esta fatura está FECHADA e bloqueada para edições.")
            if st.button("🔓 Reabrir Fatura"):
                database.reabrir_fatura(vencimento)
                st.session_state["fatura_fechada"] = False
                st.rerun()

        st.subheader("Lançamentos da Fatura")
        
        for idx, item in enumerate(lancamentos):
            with st.container():
                c1, c2, c3, c4, c5, c6 = st.columns([1, 2.8, 1.2, 1.3, 2, 2])
                c1.write(f"**{item['data_fatura']}**")
                c2.write(f"{item['descricao']}")
                c3.write(f"R$ {item['valor']:,.2f}")
                
                # Coluna de Status
                if item["status"] == "CONCILIADO":
                    c4.success("✔ Conciliado")
                else:
                    c4.warning("⏳ Pendente")

                # Coluna de NFs (Somente PDFs baixados)
                anexos = item.get("anexos_nf") or []
                if not anexos and item.get("anexo_nf"):
                    anexos = [item["anexo_nf"]]

                with c5:
                    if anexos:
                        for idx_anexo, nome_arq in enumerate(anexos):
                            caminho_nf = os.path.join(imap_reader.NOTAS_DIR, nome_arq)
                            if os.path.exists(caminho_nf):
                                with open(caminho_nf, "rb") as f_pdf:
                                    st.download_button(
                                        label=f"📄 NF {idx_anexo+1}: {nome_arq[:15]}...",
                                        data=f_pdf.read(),
                                        file_name=nome_arq,
                                        mime="application/pdf",
                                        key=f"btn_nf_{idx}_{idx_anexo}"
                                    )
                    elif item.get("tipo") == "Gerencial":
                        st.info("Gerencial (S/ NF)")
                    else:
                        st.write("-")

                # Coluna de Ações Manuais
                with c6:
                    if not fatura_fechada:
                        if item["status"] == "PENDENTE":
                            acao = st.selectbox(
                                "Conciliação Manual", 
                                ["Pendente", "Despesa de Terceiro", "Aprovação Gerencial"], 
                                key=f"manual_{idx}"
                            )
                            if acao != "Pendente":
                                item["status"] = "CONCILIADO"
                                item["tipo"] = "Manual / Terceiro"
                                item["observacao"] = acao
                        else:
                            st.caption(item.get("observacao", ""))
                    else:
                        st.caption(item.get("observacao", ""))
                st.divider()

        # Botões de Fechamento e Salvamento
        if not fatura_fechada:
            pendentes = sum(1 for x in lancamentos if x["status"] == "PENDENTE")
            col_salvar, col_fechar = st.columns([1, 1])
            with col_salvar:
                if st.button("💾 Salvar Rascunho"):
                    database.salvar_fatura(uploaded_file.name, vencimento, valor_total, lancamentos)
                    st.success("Progresso salvo com sucesso!")
            with col_fechar:
                if pendentes > 0:
                    st.button(f"🔒 Fechar Fatura ({pendentes} pendentes)", disabled=True)
                else:
                    if st.button("🔒 Fechar Fatura Definitivamente", type="primary"):
                        database.fechar_fatura(vencimento, lancamentos)
                        st.session_state["fatura_fechada"] = True
                        st.success("Fatura fechada com sucesso!")
                        st.rerun()

elif menu == "Consulta de Faturas":
    st.subheader("Histórico de Faturas Importadas")
    faturas = database.listar_faturas()
    if not faturas:
        st.info("Nenhuma fatura registrada no banco até o momento.")
    else:
        df_historico = pd.DataFrame(faturas, columns=["ID", "Arquivo", "Vencimento", "Valor Total", "Status"])
        st.dataframe(df_historico, use_container_width=True)