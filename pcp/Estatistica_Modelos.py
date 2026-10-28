from pathlib import Path
import os
import streamlit as st

# ==========================================================
# CONFIGURAÇÃO DE DIRETÓRIOS E AMBIENTE
# ==========================================================
# Garante que leituras de 'cadastros_base.json' e 'de_para_solados_eva.csv'
# funcionem na pasta /app/pcp
diretorio_pcp = Path(__file__).resolve().parent
os.chdir(diretorio_pcp)

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
# LOCALIZADOR ROBUSTO DAS TELAS EM pcp/pages/
# ==========================================================
def carregar_script(nomes_possiveis):
    pasta_pages = diretorio_pcp / "pages"
    
    # Lista arquivos reais dentro de /app/pcp/pages/ se ela existir
    arquivos_existentes = list(pasta_pages.glob("*.py")) if pasta_pages.exists() else []

    # 1. Tenta correspondência exata nos caminhos
    for nome in nomes_possiveis:
        caminhos_diretos = [
            pasta_pages / nome,
            diretorio_pcp / nome,
            Path("/app/pcp/pages") / nome
        ]
        for c in caminhos_diretos:
            if c.is_file():
                with open(c, "r", encoding="utf-8") as f:
                    exec(f.read(), globals())
                return

    # 2. Se tiver prefixo (ex: 1_...de_para, 2_...cadastro, etc.), tenta correspondência parcial
    for arq in arquivos_existentes:
        nome_limpo = arq.name.lower().replace("-", "_")
        for esperado in nomes_possiveis:
            palavra_chave = esperado.lower().replace("-", "_").replace(".py", "")
            if palavra_chave in nome_limpo:
                with open(arq, "r", encoding="utf-8") as f:
                    exec(f.read(), globals())
                return

    # Se não encontrar, mostra na tela exatamente quais arquivos existem na pasta pages
    st.error(f"❌ Não foi possível encontrar a tela correspondente.")
    st.write("Nomes procurados:", nomes_possiveis)
    if pasta_pages.exists():
        st.write("Arquivos encontrados em `pcp/pages/`:", [f.name for f in pasta_pages.iterdir()])
    else:
        st.warning(f"A pasta `{pasta_pages}` não foi encontrada.")

# ==========================================================
# RENDERIZAÇÃO DA PÁGINA SELECIONADA
# ==========================================================
if menu_selecionado == "📝 De-Para":
    carregar_script(["de-para.py", "de_para.py", "1_📝_De_Para.py"])

elif menu_selecionado == "⚙️ Cadastro de Solados e Cores":
    carregar_script(["cadastro_solados.py", "cadastro_solados_cores.py", "2_⚙️_Cadastro_Solados_Cores.py"])

elif menu_selecionado == "📑 Importar Relatório CHB":
    carregar_script(["importador.py", "3_📑_Importar_Relatorio.py", "importar_relatorio.py"])