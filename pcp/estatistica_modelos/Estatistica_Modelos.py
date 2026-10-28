from pathlib import Path
import os
import sys
import streamlit as st

# ==========================================================
# CONFIGURAÇÃO DE AMBIENTE E CAMINHOS
# ==========================================================
diretorio_projeto = Path(__file__).resolve().parent

# Adiciona /app/pcp/estatistica_modelos ao sys.path para localizar "import utils"
caminho_str = str(diretorio_projeto)
if caminho_str not in sys.path:
    sys.path.insert(0, caminho_str)

# Garante o diretório de trabalho correto para ler cadastros_base.json e CSVs
os.chdir(diretorio_projeto)

# ==========================================================
# MENU LATERAL ESQUERDO (SIDEBAR)
# ==========================================================
st.sidebar.title("🏭 Estatística de Modelos")
st.sidebar.markdown("---")

menu_selecionado = st.sidebar.radio(
    "Navegação PCP:",
    [
        "📝 De-Para",
        "⚙️ Cadastro de Solados e Cores",
        "📑 Importar Relatório CHB"
    ]
)
st.sidebar.markdown("---")
st.sidebar.caption("PCP - Gestão de Solados e EVA")

# ==========================================================
# CARREGADOR DOS SCRIPTS
# ==========================================================
def carregar_script(nomes_possiveis):
    pasta_pages = diretorio_projeto / "pages"
    arquivos_existentes = list(pasta_pages.glob("*.py")) if pasta_pages.exists() else []

    # 1. Busca por nome exato
    for nome in nomes_possiveis:
        caminhos_diretos = [
            pasta_pages / nome,
            diretorio_projeto / nome,
            Path("/app/pcp/estatistica_modelos/pages") / nome
        ]
        for c in caminhos_diretos:
            if c.is_file():
                escopo = globals().copy()
                escopo["__file__"] = str(c)
                with open(c, "r", encoding="utf-8") as f:
                    exec(f.read(), escopo)
                return

    # 2. Busca aproximada (casos com prefixos numéricos como 1_📝_De_Para.py)
    for arq in arquivos_existentes:
        nome_limpo = arq.name.lower().replace("-", "_")
        for esperado in nomes_possiveis:
            palavra_chave = esperado.lower().replace("-", "_").replace(".py", "")
            if palavra_chave in nome_limpo:
                escopo = globals().copy()
                escopo["__file__"] = str(arq)
                with open(arq, "r", encoding="utf-8") as f:
                    exec(f.read(), escopo)
                return

    st.error("❌ Não foi possível encontrar a tela correspondente.")
    st.write("Nomes procurados:", nomes_possiveis)
    if pasta_pages.exists():
        st.write("Arquivos em `pages/`:", [f.name for f in pasta_pages.iterdir()])

# ==========================================================
# RENDERIZAÇÃO DA PÁGINA SELECIONADA
# ==========================================================
if menu_selecionado == "📝 De-Para":
    carregar_script(["de-para.py", "de_para.py", "1_📝_De_Para.py", "1_De_Para.py"])

elif menu_selecionado == "⚙️ Cadastro de Solados e Cores":
    carregar_script(["cadastro_solados.py", "cadastro_solados_cores.py", "2_⚙️_Cadastro_Solados_Cores.py", "2_Cadastro_Solados_Cores.py"])

elif menu_selecionado == "📑 Importar Relatório CHB":
    carregar_script(["importador.py", "3_📑_Importar_Relatorio.py", "3_Importar_Relatorio.py", "importar_relatorio.py"])
