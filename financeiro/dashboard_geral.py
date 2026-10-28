import streamlit as st
import pandas as pd
from datetime import date
from dateutil.relativedelta import relativedelta

# --- CONSULTAS SQL GLOBAIS COM CACHE ---
@st.cache_data(ttl=600)
def consultar_recebidos_dia_anterior(_get_connection_func):
    """Retorna o valor total e quantidade de títulos quitados no dia anterior."""
    query = """
    SELECT 
        COUNT(DISTINCT P.[Fn06NumTit]) AS QtdTitulos,
        COALESCE(SUM(P.[Fn06VrRecB]), 0) AS TotalRecebido
    FROM [FN06T2] P
    WHERE P.[Fn06Emp07] = 1
      AND CAST(P.[Fn06DtDig] AS DATE) = CAST(DATEADD(day, -1, GETDATE()) AS DATE);
    """
    with _get_connection_func() as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        row = cursor.fetchone()
        return {
            "qtd": row[0] if row else 0,
            "total": float(row[1]) if row and row[1] else 0.0
        }

@st.cache_data(ttl=600)
def consultar_visao_geral_inadimplencia(_get_connection_func):
    """Busca todos os títulos a receber em aberto da empresa."""
    query = """
    WITH BaixasTotais AS (
        SELECT 
            [Fn06Emp07], [Fn06TipTit], [Fn06NumTit], [Fn06Desdob], [Fn06cCli1],
            SUM(COALESCE([Fn06VrRecB], 0)) AS TotalBaixado
        FROM [FN06T2]
        WHERE [Fn06Desdob] IS NOT NULL
        GROUP BY [Fn06Emp07], [Fn06TipTit], [Fn06NumTit], [Fn06Desdob], [Fn06cCli1]
    )
    SELECT 
        A.[Fn06NumTit] AS Titulo,
        A.[Fn06Desdob] AS Desdob,
        A.[Fn06cCli1] AS CodCliente,
        COALESCE(C.[fi15nome], 'Não Identificado') AS NomeCliente,
        A.[Fn06DtVenc] AS Vencimento,
        A.[FN06VrTitu] AS Valor
    FROM [FN06T] A
    LEFT JOIN BaixasTotais B ON (
        A.[Fn06Emp07] = B.[Fn06Emp07]
        AND A.[Fn06TipTit] = B.[Fn06TipTit]
        AND A.[Fn06NumTit] = B.[Fn06NumTit]
        AND A.[Fn06Desdob] = B.[Fn06Desdob]
        AND A.[Fn06cCli1] = B.[Fn06cCli1]
    )
    LEFT JOIN [FI15T] C ON (
        C.[fi15emp05] = 1 
        AND C.[fi15codcf] = A.[Fn06cCli1]
    )
    WHERE A.[Fn06Emp07] = 1
      AND A.[Fn06tCli1] = 'C'
      AND A.[Fn06TipTit] = 'R'
      AND (B.TotalBaixado IS NULL OR B.TotalBaixado = 0);
    """
    with _get_connection_func() as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        colunas = [col[0].strip() for col in cursor.description]
        registros = cursor.fetchall()
        dados = [tuple(row) for row in registros]
        return pd.DataFrame(dados, columns=colunas)

# --- TELA VISUAL DO DASHBOARD ---
def renderizar_dashboard(get_connection_func):
    st.subheader("🌐 Painel Geral de Recebimentos e Inadimplência")
    st.caption("Visão consolidada da empresa antes da seleção de cliente individual.")

    try:
        dados_ontem = consultar_recebidos_dia_anterior(get_connection_func)
        df_abertos = consultar_visao_geral_inadimplencia(get_connection_func)
    except Exception as e:
        st.error(f"Erro ao obter dados do painel: {e}")
        return

    hoje = pd.Timestamp.now().normalize()
    df_abertos["Valor"] = pd.to_numeric(df_abertos["Valor"], errors="coerce").fillna(0.0)
    df_abertos["Vencimento"] = pd.to_datetime(df_abertos["Vencimento"], errors="coerce")

    # Filtros por data de vencimento
    df_vencidos = df_abertos[df_abertos["Vencimento"] < hoje].copy()
    df_hoje = df_abertos[df_abertos["Vencimento"] == hoje].copy()
    df_futuros = df_abertos[df_abertos["Vencimento"] > hoje].copy()

    total_vencido = df_vencidos["Valor"].sum()
    total_hoje = df_hoje["Valor"].sum()
    qtd_hoje = len(df_hoje)
    total_futuro = df_futuros["Valor"].sum()
    
    total_carteira = total_vencido + total_hoje + total_futuro
    indice_inadimplencia = (total_vencido / total_carteira * 100) if total_carteira > 0 else 0.0

    # 1. Cards Principais (5 Colunas)
    m1, m2, m3, m4, m5 = st.columns(5)
    
    m1.metric(
        "Recebido Ontem (D-1)", 
        f"R$ {dados_ontem['total']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
        help=f"{dados_ontem['qtd']} títulos quitados no dia anterior."
    )
    m2.metric(
        "A Receber Hoje", 
        f"R$ {total_hoje:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
        help=f"{qtd_hoje} parcelas com vencimento para o dia de hoje."
    )
    m3.metric(
        "A Vencer (Futuro)", 
        f"R$ {total_futuro:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
        help="Parcelas com vencimento posterior a hoje."
    )
    m4.metric(
        "Total em Atraso", 
        f"R$ {total_vencido:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
        delta="Crítico" if total_vencido > 0 else "Em dia",
        delta_color="inverse"
    )
    m5.metric("Inadimplência Geral", f"{indice_inadimplencia:.1f}%")

    st.divider()

    # 2. Faixas de Atraso (Aging) e Top Devedores
    col_aging, col_top = st.columns([1.2, 1.8])

    with col_aging:
        st.markdown("##### ⏳ Faixas de Atraso (Aging)")
        if not df_vencidos.empty:
            df_vencidos["DiasAtraso"] = (hoje - df_vencidos["Vencimento"]).dt.days
            
            def agrupar_faixa(dias):
                if dias <= 15:
                    return "1. Até 15 dias"
                elif dias <= 30:
                    return "2. 16 a 30 dias"
                elif dias <= 60:
                    return "3. 31 a 60 dias"
                else:
                    return "4. Acima de 60 dias"

            df_vencidos["Faixa"] = df_vencidos["DiasAtraso"].apply(agrupar_faixa)
            df_faixas = df_vencidos.groupby("Faixa", as_index=False)["Valor"].sum()
            df_faixas["Total"] = df_faixas["Valor"].apply(
                lambda x: f"R$ {float(x):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            )
            st.dataframe(df_faixas[["Faixa", "Total"]], width="stretch", hide_index=True)
        else:
            st.success("Sem títulos em atraso no momento.")

    with col_top:
        st.markdown("##### 🚨 Top 5 Maiores Devedores")
        if not df_vencidos.empty:
            df_top = (
                df_vencidos.groupby(["CodCliente", "NomeCliente"], as_index=False)["Valor"]
                .sum()
                .sort_values(by="Valor", ascending=False)
                .head(5)
            )
            df_top["Código"] = df_top["CodCliente"].astype(int)
            df_top["Valor Devido"] = df_top["Valor"].apply(
                lambda x: f"R$ {float(x):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            )
            st.dataframe(df_top[["Código", "NomeCliente", "Valor Devido"]], width="stretch", hide_index=True)
            st.caption("💡 *Insira o código do cliente na barra lateral para detalhar os títulos.*")
        else:
            st.info("Nenhum cliente inadimplente.")