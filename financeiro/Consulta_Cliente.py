from financeiro.dashboard_geral import renderizar_dashboard
import streamlit as st
import pandas as pd
import numpy as np
import pyodbc
from io import BytesIO
from datetime import date
from dateutil.relativedelta import relativedelta

#st.set_page_config(page_title="Painel Financeiro de Clientes", layout="wide")
st.title("📊 Painel Financeiro e Títulos por Cliente")

# --- CONEXÃO COM O BANCO DE DADOS ---
def get_connection():
    # 1. Lê as credenciais do secrets
    if "sql_server_CHB" in st.secrets:
        cfg = st.secrets["sql_server_CHB"]
    elif "sql_server" in st.secrets:
        cfg = st.secrets["sql_server"]
    else:
        cfg = {
            "host": "SEU_SERVIDOR_OU_IP",
            "port": 1433,
            "database": "CHB",
            "username": "SEU_USUARIO",
            "password": "SUA_SENHA",
            "driver": "SQL Server",
        }

    # 2. Resolução do Host/Porta
    host = cfg.get("host") or cfg.get("server", "localhost")
    port = cfg.get("port", 1433)
    server_str = f"{host},{port}" if port else host

    # 3. Mapeamento e validação do Driver ODBC
    drivers_disponiveis = pyodbc.drivers()
    driver_solicitado = cfg.get("driver", "").replace("+", " ").strip()
    
    driver_escolhido = None

    # Tenta usar o driver especificado no secrets se estiver instalado
    if driver_solicitado and driver_solicitado in drivers_disponiveis:
        driver_escolhido = f"{{{driver_solicitado}}}"
    else:
        # Fallback de drivers por ordem de preferência
        for d in ["ODBC Driver 18 for SQL Server", "ODBC Driver 17 for SQL Server", "SQL Server Native Client 11.0", "SQL Server"]:
            if d in drivers_disponiveis:
                driver_escolhido = f"{{{d}}}"
                break
                
    if not driver_escolhido:
        raise RuntimeError(f"Nenhum driver compatível com SQL Server encontrado. Drivers instalados: {drivers_disponiveis}")

    # 4. Montagem da connection string do pyodbc
    conn_str = (
        f"DRIVER={driver_escolhido};"
        f"SERVER={server_str};"
        f"DATABASE={cfg['database']};"
        f"UID={cfg['username']};"
        f"PWD={cfg['password']};"
    )
    
    # Flags de segurança para ODBC Driver 18/17
    if "ODBC Driver" in driver_escolhido:
        conn_str += "TrustServerCertificate=yes;"
        
    return pyodbc.connect(conn_str)

def calcular_dias_atraso_real(dt_venc, dt_pgto):
    """
    Calcula os dias de atraso considerando a tolerância bancária de final de semana.
    - Se vencer no sábado (weekday=5) e pagar até segunda (2 dias): 0 dias.
    - Se vencer no domingo (weekday=6) e pagar na segunda (1 dia): 0 dias.
    - Se pagar após a segunda-feira: conta os dias corridos a partir do vencimento.
    """
    if pd.isnull(dt_venc) or pd.isnull(dt_pgto):
        return 0
    
    dias_corridos = (dt_pgto.normalize() - dt_venc.normalize()).days
    if dias_corridos <= 0:
        return 0
    
    dia_semana_venc = dt_venc.weekday()  # 5 = Sábado, 6 = Domingo
    
    if dia_semana_venc == 5 and dias_corridos <= 2:
        return 0
    elif dia_semana_venc == 6 and dias_corridos <= 1:
        return 0
    
    return dias_corridos

def classificar_tipo_cliente(media_atraso):
    """
    Classifica o tipo/conceito do cliente de acordo com a média de atraso em dias:
    - 0 dia = AA
    - 1 a 6 dias = A
    - 7 a 15 dias = AB
    - 16 a 30 dias = B
    - 31 a 45 dias = C
    - 46 a 60 dias = D
    - Acima de 61 dias = E
    """
    if media_atraso <= 0:
        return "AA", "#198754", "#d1e7dd"  # Verde escuro / fundo claro
    elif media_atraso <= 6:
        return "A", "#0d6efd", "#cfe2ff"   # Azul
    elif media_atraso <= 15:
        return "AB", "#0dcaf0", "#cff4fc"  # Ciano/Turquesa
    elif media_atraso <= 30:
        return "B", "#ffc107", "#fff3cd"   # Amarelo/Atenção
    elif media_atraso <= 45:
        return "C", "#fd7e14", "#ffe5d0"   # Laranja
    elif media_atraso <= 60:
        return "D", "#dc3545", "#f8d7da"   # Vermelho
    else:
        return "E", "#842029", "#f5c2c7"   # Vinho/Crítico

def consultar_titulos(cod_cliente: int, num_titulo: int = None, 
                      dt_emis_ini: date = None, dt_emis_fim: date = None,
                      dt_venc_ini: date = None, dt_venc_fim: date = None):
    cod_cli = int(cod_cliente)
    filtro_titulo = f"AND A.[Fn06NumTit] = {int(num_titulo)}" if num_titulo else ""
    
    str_emis_ini = dt_emis_ini.strftime("%Y-%m-%d")
    str_emis_fim = dt_emis_fim.strftime("%Y-%m-%d")
    str_venc_ini = dt_venc_ini.strftime("%Y-%m-%d")
    str_venc_fim = dt_venc_fim.strftime("%Y-%m-%d")

    query = f"""
    WITH Pagamentos AS (
        SELECT 
            [Fn06Emp07],
            [Fn06TipTit],
            [Fn06NumTit],
            [Fn06Desdob],
            [Fn06cCli1],
            MAX([Fn06DtDig]) AS DataPagamento,
            SUM(COALESCE([Fn06VrRecB], 0)) AS TotalRecebido,
            SUM(COALESCE([Fn06VrJuro], 0)) AS TotalJuros
        FROM [FN06T2]
        WHERE [Fn06Desdob] IS NOT NULL
        GROUP BY 
            [Fn06Emp07],
            [Fn06TipTit],
            [Fn06NumTit],
            [Fn06Desdob],
            [Fn06cCli1]
    )
    SELECT 
        A.[Fn06NumTit]                   AS Titulo, 
        A.[Fn06Desdob]                   AS Desdob, 
        A.[Fn06cCli1]                    AS CodCliente,
        C.[fi15nome]                     AS NomeCliente,
        C.[fi15uf]                       AS UF,
        C.[fi15limcre]                   AS LimiteCredito,
        C.[fi15cRep]                     AS CodRepresentante,
        R.[fi13nome]                     AS NomeRepresentante,
        A.[Fn06Dtemis]                   AS Emissao, 
        A.[FN06VrTitu]                   AS Valor, 
        A.[Fn06DtVenc]                   AS Vencimento,
        COALESCE(P.TotalRecebido, 0)     AS ValorRecebido,
        COALESCE(P.TotalJuros, 0)        AS ValorJuros,
        P.DataPagamento                  AS DataPagamento,
        CASE 
            WHEN P.[Fn06Desdob] IS NOT NULL AND P.TotalRecebido > 0 THEN 'PAGO' 
            ELSE 'PENDENTE' 
        END AS Status
    FROM [FN06T] A
    LEFT JOIN Pagamentos P ON (
        A.[Fn06Emp07]  = P.[Fn06Emp07]
        AND A.[Fn06TipTit] = P.[Fn06TipTit]
        AND A.[Fn06NumTit] = P.[Fn06NumTit]
        AND A.[Fn06Desdob] = P.[Fn06Desdob]
        AND A.[Fn06cCli1]  = P.[Fn06cCli1]
    )
    LEFT JOIN [FI15T] C ON (
        C.[fi15emp05]  = 1 
        AND C.[fi15codcf]  = A.[Fn06cCli1]
    )
    LEFT JOIN [FI13T] R ON (
        R.[fi13emp05]  = 1 
        AND R.[fi13codrep] = C.[fi15cRep]
    )
    WHERE A.[Fn06Emp07] = 1
      AND A.[Fn06tCli1] = 'C'
      AND A.[Fn06TipTit] = 'R'
      AND A.[Fn06cCli1] = {cod_cli}
      AND A.[Fn06Dtemis] BETWEEN '{str_emis_ini}' AND '{str_emis_fim}'
      AND A.[Fn06DtVenc] BETWEEN '{str_venc_ini}' AND '{str_venc_fim}'
      {filtro_titulo}
    ORDER BY A.[Fn06NumTit], A.[Fn06Desdob];
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        colunas = [col[0].strip() for col in cursor.description]
        registros = cursor.fetchall()
        dados = [tuple(row) for row in registros]
        return pd.DataFrame(dados, columns=colunas)

def calcular_pico_historico(df):
    """Calcula a máxima exposição de saldo acumulado simultâneo e a data do pico."""
    eventos = []
    for _, row in df.iterrows():
        if pd.notnull(row["Emissao"]):
            eventos.append((row["Emissao"], row["Valor"]))
        if str(row["Status"]).startswith("PAGO") and pd.notnull(row["DataPagamento"]):
            eventos.append((row["DataPagamento"], -row["Valor"]))
    
    if not eventos:
        return 0.0, None

    df_eventos = pd.DataFrame(eventos, columns=["Data", "Movimento"])
    df_eventos = df_eventos.sort_values(by=["Data", "Movimento"], ascending=[True, False])
    df_eventos["SaldoAcumulado"] = df_eventos["Movimento"].cumsum()

    max_saldo = df_eventos["SaldoAcumulado"].max()
    if pd.isnull(max_saldo) or max_saldo <= 0:
        return 0.0, None

    # Obtém a linha onde o saldo acumulado atinge o maior valor pela primeira vez
    linha_pico = df_eventos.loc[df_eventos["SaldoAcumulado"].idxmax()]
    return float(max_saldo), linha_pico["Data"]

# --- SIDEBAR (FILTROS) ---
with st.sidebar:
    st.header("Filtros de Pesquisa")
    cliente_input = st.number_input("Código do Cliente:", min_value=1, step=1, value=None, placeholder="Digite o código...")
    titulo_input = st.number_input("Número do Título / NF (Opcional):", min_value=0, step=1, value=None, placeholder="Todos os títulos")
    
    hoje_data = date.today()

    # --- PERÍODO DE EMISSÃO ---
    st.subheader("Período de Emissão")
    filtrar_emis_anos = st.checkbox("Emissão: analisar por anos", value=False)
    
    if filtrar_emis_anos:
        anos_emis = st.number_input(
            "Anos retroativos (Emissão):",
            min_value=1,
            max_value=30,
            value=2,
            step=1,
            key="anos_emis"
        )
        dt_emis_ini = hoje_data - relativedelta(years=anos_emis)
        dt_emis_fim = hoje_data
        st.caption(f"📅 **De:** {dt_emis_ini.strftime('%d/%m/%Y')} **até** {dt_emis_fim.strftime('%d/%m/%Y')}")
    else:
        col_em1, col_em2 = st.columns(2)
        dt_emis_ini = col_em1.date_input(
            "Emissão De:",
            value=date(2019, 1, 1),
            min_value=date(2000, 1, 1),
            max_value=date(2035, 12, 31),
            format="DD/MM/YYYY"
        )
        dt_emis_fim = col_em2.date_input(
            "Emissão Até:",
            value=date(2027, 12, 31),
            min_value=date(2000, 1, 1),
            max_value=date(2035, 12, 31),
            format="DD/MM/YYYY"
        )

    # --- PERÍODO DE VENCIMENTO ---
    st.subheader("Período de Vencimento")
    filtrar_venc_anos = st.checkbox("Vencimento: analisar por anos", value=False)
    
    if filtrar_venc_anos:
        anos_venc = st.number_input(
            "Anos retroativos (Vencimento):",
            min_value=1,
            max_value=30,
            value=2,
            step=1,
            key="anos_venc"
        )
        dt_venc_ini = hoje_data - relativedelta(years=anos_venc)
        dt_venc_fim = hoje_data + relativedelta(years=2)
        st.caption(f"📅 **De:** {dt_venc_ini.strftime('%d/%m/%Y')} **até** {dt_venc_fim.strftime('%d/%m/%Y')}")
    else:
        col_vc1, col_vc2 = st.columns(2)
        dt_venc_ini = col_vc1.date_input(
            "Venc. De:",
            value=date(2019, 1, 1),
            min_value=date(2000, 1, 1),
            max_value=date(2035, 12, 31),
            format="DD/MM/YYYY"
        )
        dt_venc_fim = col_vc2.date_input(
            "Venc. Até:",
            value=date(2027, 12, 31),
            min_value=date(2000, 1, 1),
            max_value=date(2035, 12, 31),
            format="DD/MM/YYYY"
        )

    filtro_status = st.selectbox(
        "Status dos Títulos:", 
        ["TODOS", "PENDENTE (A VENCER)", "ATRASADO", "PAGO", "PAGO EM ATRASO"]
    )
    btn_consultar = st.button("Consultar Cliente", type="primary")

# --- CONTEÚDO PRINCIPAL ---
if btn_consultar:
    if not cliente_input:
        st.warning("⚠️ Por favor, informe o Código do Cliente para realizar a consulta.")
    else:
        num_tit = int(titulo_input) if (titulo_input and titulo_input > 0) else None
        
        with st.spinner("Realizando levantamento financeiro..."):
            try:
                df = consultar_titulos(
                    cod_cliente=int(cliente_input), 
                    num_titulo=num_tit,
                    dt_emis_ini=dt_emis_ini,
                    dt_emis_fim=dt_emis_fim,
                    dt_venc_ini=dt_venc_ini,
                    dt_venc_fim=dt_venc_fim
                )
                
                if df.empty:
                    st.warning("Nenhum registro encontrado para este cliente com os filtros informados.")
                else:
                    # Normalização dos tipos
                    df["Valor"] = pd.to_numeric(df["Valor"], errors="coerce").fillna(0.0)
                    df["ValorRecebido"] = pd.to_numeric(df["ValorRecebido"], errors="coerce").fillna(0.0)
                    df["ValorJuros"] = pd.to_numeric(df["ValorJuros"], errors="coerce").fillna(0.0)
                    df["Emissao"] = pd.to_datetime(df["Emissao"], errors="coerce")
                    df["Vencimento"] = pd.to_datetime(df["Vencimento"], errors="coerce")
                    df["DataPagamento"] = pd.to_datetime(df["DataPagamento"], errors="coerce")
                    
                    hoje = pd.Timestamp.now().normalize()

                    # Cálculo de dias de atraso
                    df["DiasAtraso"] = df.apply(
                    lambda r: calcular_dias_atraso_real(r["Vencimento"], r["DataPagamento"]) 
                    if r["Status"] == "PAGO" else 0,
                    axis=1
                    )

                    # Classificação refinada do Status
                    # Normalização dos tipos
                    df["Valor"] = pd.to_numeric(df["Valor"], errors="coerce").fillna(0.0)
                    df["Emissao"] = pd.to_datetime(df["Emissao"], errors="coerce")
                    df["Vencimento"] = pd.to_datetime(df["Vencimento"], errors="coerce")
                    df["DataPagamento"] = pd.to_datetime(df["DataPagamento"], errors="coerce")
                    
                    hoje = pd.Timestamp.now().normalize()

                    # Calcula os dias de atraso histórico considerando a tolerância de fins de semana
                    df["DiasAtraso"] = df.apply(
                        lambda r: calcular_dias_atraso_real(r["Vencimento"], r["DataPagamento"]) 
                        if r["Status"] == "PAGO" else 0,
                        axis=1
                    )

                    # Classificação refinada do Status com a indentação correta:
                    def classificar_status(row):
                        if row["Status"] == "PAGO":
                            if row["DiasAtraso"] > 0:
                                return "PAGO EM ATRASO"
                            return "PAGO"
                        elif pd.notnull(row["Vencimento"]) and row["Vencimento"] < hoje:
                            return "ATRASADO"
                        return "PENDENTE (A VENCER)"

                    df["Status"] = df.apply(classificar_status, axis=1)

                    # --- DADOS DE IDENTIFICAÇÃO DO CLIENTE (CABEÇALHO) ---
                    nome_cliente = df["NomeCliente"].dropna().iloc[0] if not df["NomeCliente"].dropna().empty else "Não informado"
                    uf_cliente = df["UF"].dropna().iloc[0] if not df["UF"].dropna().empty else "-"
                    cod_rep = df["CodRepresentante"].dropna().iloc[0] if not df["CodRepresentante"].dropna().empty else "-"
                    nome_rep = df["NomeRepresentante"].dropna().iloc[0] if not df["NomeRepresentante"].dropna().empty else "Não informado"
                    
                    limite_credito = 0.0
                    if "LimiteCredito" in df.columns and not df["LimiteCredito"].dropna().empty:
                        try:
                            limite_credito = float(df["LimiteCredito"].dropna().iloc[0])
                        except (ValueError, TypeError):
                            limite_credito = 0.0

                    if pd.notnull(cod_rep) and str(cod_rep).strip() != "-":
                        rep_formatado = f"{int(cod_rep)} - {nome_rep}"
                    else:
                        rep_formatado = nome_rep

# Determina o conceito do cliente pela média de atraso
                    conceito_cliente, cor_texto, cor_fundo = classificar_tipo_cliente(atraso_medio_historico)

                    # Renderiza o cabeçalho com o Tipo de Cliente destacado à direita
                    st.markdown(
                        f"""
                        <div style="
                            background-color: #f1f3f5; 
                            padding: 16px 20px; 
                            border-radius: 8px; 
                            border-left: 5px solid #0d6efd; 
                            margin-bottom: 20px;
                            display: flex;
                            justify-content: space-between;
                            align-items: center;
                        ">
                            <div>
                                <h3 style="margin: 0; color: #212529;">👤 {int(cliente_input)} - {nome_cliente} ({uf_cliente})</h3>
                                <p style="margin: 5px 0 0 0; color: #495057; font-size: 15px;">
                                    <strong>Representante:</strong> {rep_formatado}
                                </p>
                            </div>
                            <div style="
                                background-color: {cor_fundo};
                                border: 1.5px solid {cor_texto};
                                border-radius: 8px;
                                padding: 6px 16px;
                                text-align: center;
                                min-width: 110px;
                            ">
                                <div style="font-size: 11px; font-weight: 600; color: {cor_texto}; text-transform: uppercase; letter-spacing: 0.5px;">
                                    Tipo / Conceito
                                </div>
                                <div style="font-size: 22px; font-weight: 800; color: {cor_texto}; line-height: 1.1;">
                                    {conceito_cliente}
                                </div>
                                <div style="font-size: 10px; color: #6c757d; margin-top: 2px;">
                                    Méd. {atraso_medio_historico:.1f} d
                                </div>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                    # --- SEPARAÇÃO DAS BASES ---
                    total_nfs = df["Titulo"].nunique()
                    total_parcelas = len(df)
                    
                    df_pagos_em_dia = df[df["Status"] == "PAGO"].copy()
                    df_pagos_atraso = df[df["Status"] == "PAGO EM ATRASO"].copy()
                    df_atrasados = df[df["Status"] == "ATRASADO"].copy()
                    df_pendentes_a_vencer = df[df["Status"] == "PENDENTE (A VENCER)"].copy()
                    df_abertos_geral = df[df["Status"].isin(["PENDENTE (A VENCER)", "ATRASADO"])].copy()

                    # --- ÚLTIMAS 5 NOTAS FISCAIS FATURADAS ---
                    df_ultimas_nfs = (
                        df.groupby("Titulo", as_index=False)
                        .agg({
                            "Emissao": "max",
                            "Valor": "sum"
                        })
                        .sort_values(by=["Emissao", "Titulo"], ascending=[False, False])
                        .head(5)
                    )

                    # --- ANÁLISE DE ATRASO HISTÓRICO (PAGOS EM ATRASO) ---
                    maior_atraso_hist_dias = 0
                    maior_atraso_hist_detalhe = "Nenhum atraso registrado"
                    atraso_medio_historico = 0.0

                    if not df_pagos_atraso.empty:
                        atraso_medio_historico = df_pagos_atraso["DiasAtraso"].mean()
                        top_hist = df_pagos_atraso.loc[df_pagos_atraso["DiasAtraso"].idxmax()]
                        maior_atraso_hist_dias = int(top_hist["DiasAtraso"])
                        dt_pgto_str = top_hist["DataPagamento"].strftime("%d/%m/%Y")
                        maior_atraso_hist_detalhe = f"NF {top_hist['Titulo']}/{top_hist['Desdob']} (Pago em {dt_pgto_str})"

                    # --- ANÁLISE DE ATRASO ATUAL (PARCELAS ATRASADAS) ---
                    saldo_em_aberto = df_abertos_geral["Valor"].sum()
                    maior_atraso_atual_dias = 0
                    maior_atraso_atual_detalhe = "Sem títulos vencidos"
                    total_valor_atraso_atual = 0.0
                    detalhe_titulos_atraso = "Nenhum título em atraso"

                    if not df_atrasados.empty:
                        # 1. Soma todos os títulos/parcelas vencidos
                        total_valor_atraso_atual = df_atrasados["Valor"].sum()

                        # 2. Monta a lista com os títulos em atraso
                        lista_titulos = [
                            f"NF {int(row['Titulo'])}/{row['Desdob']}" 
                            for _, row in df_atrasados.iterrows()
                        ]
                        
                        if len(lista_titulos) <= 4:
                            detalhe_titulos_atraso = ", ".join(lista_titulos)
                        else:
                            detalhe_titulos_atraso = f"{', '.join(lista_titulos[:3])} e mais {len(lista_titulos) - 3} título(s)"

                        # 3. Calcula os dias do maior atraso atual
                        df_atrasados["DiasVencido"] = (hoje - df_atrasados["Vencimento"]).dt.days
                        top_atual = df_atrasados.loc[df_atrasados["DiasVencido"].idxmax()]
                        maior_atraso_atual_dias = int(top_atual["DiasVencido"])
                        dt_venc_str = top_atual["Vencimento"].strftime("%d/%m/%Y")
                        maior_atraso_atual_detalhe = f"NF {top_atual['Titulo']}/{top_atual['Desdob']} (Venc: {dt_venc_str})"

                    # --- VISÃO GERAL DO CLIENTE ---
                    st.subheader("📌 Visão Geral")
                    col_metr, col_ultimas = st.columns([1.8, 1.2])

                    with col_metr:
                        m1, m2 = st.columns(2)
                        m1.metric("Qtd. de Notas Fiscais", total_nfs)
                        m2.metric("Total de Parcelas", total_parcelas)
                        
                        m3, m4, m5, m6 = st.columns(4)
                        m3.metric("Pagas em Dia", len(df_pagos_em_dia))
                        m4.metric("Pagas em Atraso", len(df_pagos_atraso))
                        m5.metric("A Vencer", len(df_pendentes_a_vencer))
                        m6.metric("Atrasadas", len(df_atrasados))

                        m_lim1, m_lim2 = st.columns(2)
                        saldo_disponivel = max(0.0, limite_credito - saldo_em_aberto)
                        m_lim1.metric("Limite de Crédito", f"R$ {limite_credito:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                        m_lim2.metric(
                            "Crédito Disponível", 
                            f"R$ {saldo_disponivel:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                            delta=f"R$ {(limite_credito - saldo_em_aberto):,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                            delta_color="normal" if (limite_credito - saldo_em_aberto) >= 0 else "inverse"
                        )

                    with col_ultimas:
                        st.markdown("**🧾 Últimas 5 Notas Faturadas**")
                        if not df_ultimas_nfs.empty:
                            df_ultimas_display = df_ultimas_nfs.copy()
                            df_ultimas_display["Nota Fiscal"] = df_ultimas_display["Titulo"].astype(int).astype(str)
                            df_ultimas_display["Emissão"] = df_ultimas_display["Emissao"].apply(
                                lambda x: x.strftime("%d/%m/%Y") if pd.notnull(x) else ""
                            )
                            df_ultimas_display["Valor Total"] = df_ultimas_display["Valor"].apply(
                                lambda x: f"R$ {float(x):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                            )
                            st.dataframe(
                                df_ultimas_display[["Nota Fiscal", "Emissão", "Valor Total"]],
                                width="stretch",
                                hide_index=True
                            )
                        else:
                            st.caption("Nenhuma nota fiscal encontrada.")

                    st.divider()

                    # Chamada atualizada desempacotando o valor e a data
                    pico_historico, dt_pico = calcular_pico_historico(df)
                    if dt_pico is not None and pd.notnull(dt_pico):
                        pico_hist_detalhe = f"Atingido em {pd.to_datetime(dt_pico).strftime('%d/%m/%Y')}"
                    else:
                        pico_hist_detalhe = "Sem histórico de saldo"

                    # --- ANÁLISE FINANCEIRA ---
                    st.subheader("📈 Análise Financeira de Crédito e Cobrança")
                    c1, c2, c3 = st.columns(3)
                    c1.metric(
                        "Saldo Atual em Aberto (Total)", 
                        f"R$ {saldo_em_aberto:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                    )
                    c2.metric(
                        "Valor Total em Atraso (Atual)", 
                        f"R$ {total_valor_atraso_atual:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                        help="Soma de todos os títulos e parcelas atualmente vencidos."
                    )
                    c2.caption(f"📌 **Ref:** {detalhe_titulos_atraso}")

                    c3.metric(
                        "Pico Histórico de Saldo", 
                        f"R$ {pico_historico:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                    )
                    # Caso você use a legenda de referência do pico histórico:
                    if "pico_hist_detalhe" in locals():
                        c3.caption(f"📌 **Ref:** {pico_hist_detalhe}")

                    c4, c5, c6 = st.columns(3)
                    c4.metric(
                        label="Maior Atraso Atual", 
                        value=f"{maior_atraso_atual_dias} dias", 
                        help="Calculado a partir das parcelas atualmente vencidas e não quitadas."
                    )
                    c4.caption(f"📌 **Ref:** {maior_atraso_atual_detalhe}")

                    c5.metric(
                        label="Maior Atraso Histórico", 
                        value=f"{maior_atraso_hist_dias} dias", 
                        help="Maior atraso já ocorrido em parcelas que já foram quitadas."
                    )
                    c5.caption(f"📌 **Ref:** {maior_atraso_hist_detalhe}")

                    c6.metric("Atraso Médio Histórico", f"{atraso_medio_historico:.1f} dias")
                    c6.caption("📌 **Ref:** Média das parcelas quitadas fora do prazo")

                    st.divider()

                    # --- TABELA DE TÍTULOS ---
                    st.subheader(f"📑 Listagem de Títulos (Filtro: {filtro_status})")
                    
                    df_filtrado = df.copy()
                    if filtro_status != "TODOS":
                        df_filtrado = df_filtrado[df_filtrado["Status"] == filtro_status]

                    if df_filtrado.empty:
                        st.info(f"Nenhum título encontrado com status '{filtro_status}'.")
                    else:
                        # Colunas base do DataFrame
                        colunas_grid = [
                            "Titulo", "Desdob", "Emissao", "Valor", 
                            "Vencimento", "DataPagamento", "ValorRecebido", 
                            "ValorJuros", "DiasAtraso", "Status"
                        ]
                        df_view = df_filtrado[colunas_grid].copy()

                        df_view["Titulo"] = pd.to_numeric(df_view["Titulo"], errors="coerce").fillna(0).astype(int)
                        df_view["Valor"] = pd.to_numeric(df_view["Valor"], errors="coerce").fillna(0.0)
                        df_view["ValorRecebido"] = pd.to_numeric(df_view["ValorRecebido"], errors="coerce").fillna(0.0)
                        df_view["ValorJuros"] = pd.to_numeric(df_view["ValorJuros"], errors="coerce").fillna(0.0)

                        # Montagem da estrutura de exibição mantendo ordenação correta
                        df_display = pd.DataFrame({
                            "Titulo": df_view["Titulo"],
                            "Desdob": df_view["Desdob"],
                            "Emissão": pd.to_datetime(df_view["Emissao"]).dt.date,
                            "Valor": df_view["Valor"],
                            "Vencimento": pd.to_datetime(df_view["Vencimento"]).dt.date,
                            "Pagamento": pd.to_datetime(df_view["DataPagamento"]).dt.date,
                            "Valor Pago": df_view["ValorRecebido"],
                            "Juros": df_view["ValorJuros"],
                            "Atraso": df_view["DiasAtraso"].apply(
                                lambda x: f"{int(x)} d" if pd.notnull(x) and int(x) > 0 else "-"
                            ),
                            "Status": df_view["Status"]
                        })

                        def colorir_linhas(row):
                            status = row["Status"]
                            if status == "PAGO":
                                return ["background-color: #d4edda; color: #155724;"] * len(row)
                            elif status == "PAGO EM ATRASO":
                                return ["background-color: #ffe8cc; color: #d9480f; font-weight: bold;"] * len(row)
                            elif status == "ATRASADO":
                                return ["background-color: #f8d7da; color: #721c24; font-weight: bold;"] * len(row)
                            elif status == "PENDENTE (A VENCER)":
                                return ["background-color: #fff3cd; color: #856404;"] * len(row)
                            return [""] * len(row)

                        fmt_moeda = lambda x: f"R$ {float(x):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if pd.notnull(x) else ""

                        df_styled = (
                            df_display.style
                            .apply(colorir_linhas, axis=1)
                            .format({
                                "Valor": fmt_moeda,
                                "Valor Pago": fmt_moeda,
                                "Juros": fmt_moeda
                            })
                        )

                        st.dataframe(
                            df_styled,
                            column_config={
                                "Emissão": st.column_config.DateColumn("Emissão", format="DD/MM/YYYY"),
                                "Vencimento": st.column_config.DateColumn("Vencimento", format="DD/MM/YYYY"),
                                "Pagamento": st.column_config.DateColumn("Pagamento", format="DD/MM/YYYY"),
                            },
                            width="stretch",
                            hide_index=True
                        )

                    # --- EXPORTAÇÃO EXCEL ---
                    buffer = BytesIO()
                    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                        df_filtrado.drop(columns=["Ocorrencia"], errors="ignore").to_excel(writer, index=False, sheet_name="Titulos_Filtrados")
                        df.drop(columns=["Ocorrencia"], errors="ignore").to_excel(writer, index=False, sheet_name="Todos_Titulos")
                        
                        df_resumo = pd.DataFrame([{
                            "Codigo_Cliente": int(cliente_input),
                            "Nome_Cliente": nome_cliente,
                            "UF": uf_cliente,
                            "Representante": rep_formatado,
                            "Limite_Credito": limite_credito,
                            "Saldo_Disponivel": limite_credito - saldo_em_aberto,
                            "Total_Notas_Fiscais": total_nfs,
                            "Total_Parcelas": total_parcelas,
                            "Parcelas_Pagas_Em_Dia": len(df_pagos_em_dia),
                            "Parcelas_Pagas_Atraso": len(df_pagos_atraso),
                            "Parcelas_A_Vencer": len(df_pendentes_a_vencer),
                            "Parcelas_Atrasadas": len(df_atrasados),
                            "Saldo_Atual_Aberto": saldo_em_aberto,
                            "Valor_Total_Atraso_Atual": total_valor_atraso_atual,
                            "Titulos_Em_Atraso": detalhe_titulos_atraso,
                            "Maior_Atraso_Atual_Dias": maior_atraso_atual_dias,
                            "Detalhe_Atraso_Atual": maior_atraso_atual_detalhe,
                            "Maior_Atraso_Historico_Dias": maior_atraso_hist_dias,
                            "Detalhe_Atraso_Historico": maior_atraso_hist_detalhe,
                            "Atraso_Medio_Historico_Dias": atraso_medio_historico,
                            "Pico_Historico_Saldo": pico_historico
                        }])
                        df_resumo.to_excel(writer, index=False, sheet_name="Resumo_Financeiro")

                    st.download_button(
                        label="📥 Exportar Dados para Excel",
                        data=buffer.getvalue(),
                        file_name=f"analise_financeira_{cliente_input}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )

            except Exception as e:
                st.error(f"Erro ao processar análise financeira: {e}")
                # --- CONTEÚDO PRINCIPAL ---
if btn_consultar:
    if not cliente_input:
        st.warning("⚠️ Por favor, informe o Código do Cliente para realizar a consulta.")
    else:
        # [SEU CÓDIGO ATUAL DE CONSULTA DO CLIENTE CONTINUA AQUI SEM NENHUMA ALTERAÇÃO]
        pass
else:
    # Se o botão não foi clicado, exibe o módulo isolado da tela inicial
    renderizar_dashboard(get_connection)