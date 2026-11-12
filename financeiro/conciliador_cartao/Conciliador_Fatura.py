from pathlib import Path
import importlib.util
import sys
import streamlit as st

# ==========================================================
# 1. ISOLAMENTO DE CAMINHO E IMPORTAÇÃO LOCAL SEGURA
# ==========================================================
diretorio_projeto = Path(__file__).resolve().parent
caminho_str = str(diretorio_projeto)
if caminho_str not in sys.path:
    sys.path.insert(0, caminho_str)

# Carrega o database.py especificamente desta subpasta (evita conflito com outros .db na Central)
spec_db = importlib.util.spec_from_file_location(
    "database", diretorio_projeto / "database.py"
)
database = importlib.util.module_from_spec(spec_db)
sys.modules["database"] = database
spec_db.loader.exec_module(database)

database.init_db()

# Esconde o menu duplicado nativo do Streamlit se houver pasta pages
st.markdown(
    """
    <style>
        [data-testid="stSidebarNav"] { display: none !important; }
    </style>
""",
    unsafe_allow_html=True,
)

# ==========================================================
# MENU LATERAL ESQUERDO (SIDEBAR)
# ==========================================================
st.sidebar.title("💳 Conciliação de Cartão")
st.sidebar.markdown("---")

menu_selecionado = st.sidebar.radio(
    "Navegação:",
    [
        "🏠 Início",
        "📑 Conciliar Fatura",
        "⚖️ Confronto de Relatório",
        "👤 Compradores / E-mails",
        "📑 Assinaturas & Contratos",
        "📂 Consulta de Faturas",
        "⚙️ Configurações (.env)",
    ],
)
st.sidebar.markdown("---")
st.sidebar.caption("Financeiro - Gestão de Cartão de Crédito")


# ==========================================================
# CARREGADOR DOS SCRIPTS MODULARES
# ==========================================================
def carregar_script(nomes_possiveis):
    pastas = [
        diretorio_projeto / "pages_scripts",
        diretorio_projeto / "pages",
        diretorio_projeto,
    ]
    for p in pastas:
        if not p.exists():
            continue
        for nome in nomes_possiveis:
            c = p / nome
            if c.is_file():
                escopo = globals().copy()
                escopo["__file__"] = str(c)
                with open(c, "r", encoding="utf-8") as f:
                    exec(f.read(), escopo)
                return

    st.error("❌ Não foi possível encontrar a tela correspondente.")


# ==========================================================
# RENDERIZAÇÃO DA PÁGINA SELECIONADA
# ==========================================================
if menu_selecionado == "🏠 Início":
    st.title("💳 Conciliação de Cartão de Crédito")
    st.subheader("📋 Descritivo da Rotina Operacional")
    st.markdown("""
    Bem-vindo ao sistema de conciliação e auditoria de compras de cartão de crédito.
    
    1. **👤 Compradores / E-mails**: Cadastre os e-mails corporativos dos solicitantes para puxar o nome do comprador automaticamente.
    2. **📑 Conciliar Fatura**: Importe o arquivo `.xlsx` da fatura mensal e processe os e-mails com as notas fiscais recebidas via IMAP.
    3. **⚖️ Confronto de Relatório**: Compare os títulos lançados no ERP com os itens conciliados da fatura.
    4. **📑 Assinaturas & Contratos**: Gerencie os lançamentos recorrentes automáticos ou salve novas assinaturas/contratos vindos da conciliação.
    5. **📂 Consulta de Faturas**: Consulte o histórico de faturas fechadas e acesse diretamente os PDFs das notas fiscais.
    """)

elif menu_selecionado == "📑 Conciliar Fatura":
    carregar_script(["1_Conciliar_Fatura.py", "conciliar_fatura.py"])

elif menu_selecionado == "⚖️ Confronto de Relatório":
    carregar_script(["6_Confronto_Relatorio.py", "confronto_relatorio.py"])

elif menu_selecionado == "👤 Compradores / E-mails":
    carregar_script(["2_Compradores_Emails.py", "compradores_emails.py"])

elif menu_selecionado == "📑 Assinaturas & Contratos":
    carregar_script(["3_Assinaturas_Contratos.py", "assinaturas_contratos.py"])

elif menu_selecionado == "📂 Consulta de Faturas":
    carregar_script(["4_Consulta_Faturas.py", "consulta_faturas.py"])

elif menu_selecionado == "⚙️ Configurações (.env)":
    carregar_script(["5_Configuracoes_Env.py", "configuracoes_env.py"])
