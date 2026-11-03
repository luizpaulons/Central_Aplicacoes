from pathlib import Path
import os
import sys
import streamlit as st
import database

# Configurações iniciais da aplicação
st.set_page_config(page_title="Conciliador de Cartão de Crédito", layout="wide")
database.init_db()

# Garante o diretório de trabalho correto
diretorio_projeto = Path(__file__).resolve().parent
caminho_str = str(diretorio_projeto)
if caminho_str not in sys.path:
    sys.path.insert(0, caminho_str)
os.chdir(diretorio_projeto)

# ==========================================================
# MENU LATERAL ESQUERDO (SIDEBAR - PADRÃO LIMPO)
# ==========================================================
st.sidebar.title("💳 Conciliação de Cartão")
st.sidebar.markdown("---")

menu_selecionado = st.sidebar.radio(
    "Navegação:",
    [
        "🏠 Início (Descritivo da Rotina)",
        "📑 Conciliar Fatura",
        "👤 Compradores / E-mails",
        "📑 Assinaturas & Contratos",
        "📂 Consulta de Faturas",
        "⚙️ Configurações (.env)"
    ]
)
st.sidebar.markdown("---")
st.sidebar.caption("Financeiro - Gestão de Cartão de Crédito")

# ==========================================================
# CARREGADOR DOS SCRIPTS MODULARES
# ==========================================================
def carregar_script(nomes_possiveis):
    pasta_pages = diretorio_projeto / "pages"
    arquivos_existentes = list(pasta_pages.glob("*.py")) if pasta_pages.exists() else []

    # 1. Busca direta por nome exato
    for nome in nomes_possiveis:
        caminhos_diretos = [pasta_pages / nome, diretorio_projeto / nome]
        for c in caminhos_diretos:
            if c.is_file():
                escopo = globals().copy()
                escopo["__file__"] = str(c)
                with open(c, "r", encoding="utf-8") as f:
                    exec(f.read(), escopo)
                return

    # 2. Busca aproximada/flexível
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

    st.error("❌ Não foi possível encontrar a página correspondente.")

# ==========================================================
# RENDERIZAÇÃO DA TELA SELECIONADA
# ==========================================================
if menu_selecionado == "🏠 Início (Descritivo da Rotina)":
    st.title("💳 Sistema de Conciliação de Cartão de Crédito")
    st.subheader("📋 Descritivo da Rotina Operacional")
    
    st.markdown("""
    Bem-vindo ao sistema de conciliação e auditoria financeira de despesas com cartão corporativo. 
    Abaixo está o fluxo operacional padrão para conciliação das faturas mensais:

    ---

    ### 🔄 Fluxo Operacional Passo a Passo

    1. **👤 Pré-requisito: Cadastro de Compradores**
       * Acesse a tela **Compradores / E-mails**.
       * Garanta que os e-mails corporativos dos solicitantes estejam vinculados ao seu respectivo nome (ex: `compras@empresa.com.br ➔ Luiz Paulo`).

    2. **📑 Importação da Fatura**
       * Acesse **Conciliar Fatura**.
       * Faça o upload da fatura mensal no formato `.xlsx`. O sistema identifica automaticamente o vencimento completo (`DD/MM/AAAA`) e o valor total consolidado.

    3. **📥 Varredura Automática de E-mails (IMAP)**
       * Clique no botão de leitura de e-mails da pasta monitorada.
       * O robô busca os comprovantes recebidos, efetua o download dos PDFs (`notas_fiscais/`) e extrai os números de **NFe** (via chave SEFAZ) e **NFSe** (serviço).
       * Compras parceladas têm seus valores rateados e confrontados com precisão de centavos e proximidade de datas.

    4. **🔗 Herança e Recorrências Automáticas**
       * Parcelas de compras antigas (`PARC 02/X`, etc.) buscam e herdam automaticamente a nota fiscal da parcela 1 salva no histórico.
       * Lançamentos recorrentes cadastrados em **Assinaturas & Contratos** são validados e conciliados automaticamente pelo valor esperado.

    5. **✏️ Conciliação Manual e Ajustes**
       * Para despesas sem comprovante fiscal direto, defina o tipo manual (*Assinatura*, *Contrato*, *Despesa de Terceiro* ou *Aprovação Gerencial*).
       * Ao marcar uma nova Assinatura ou Contrato, selecione para salvar a recorrência nas próximas faturas (gravado apenas uma vez).

    6. **🔒 Fechamento Definitivo e Consulta**
       * Salve o progresso em rascunho a qualquer momento.
       * Quando todos os itens estiverem conciliados (0 pendentes), execute o fechamento definitivo da fatura.
       * Consulte o histórico completo e baixe todos os documentos comprobatórios na tela **Consulta de Faturas**.

    ---
    *Utilize o menu na barra lateral à esquerda para navegar entre os módulos.*
    """)

elif menu_selecionado == "📑 Conciliar Fatura":
    carregar_script(["1_Conciliar_Fatura.py", "conciliar_fatura.py"])

elif menu_selecionado == "👤 Compradores / E-mails":
    carregar_script(["2_Compradores_Emails.py", "compradores_emails.py"])

elif menu_selecionado == "📑 Assinaturas & Contratos":
    carregar_script(["3_Assinaturas_Contratos.py", "assinaturas_contratos.py"])

elif menu_selecionado == "📂 Consulta de Faturas":
    carregar_script(["4_Consulta_Faturas.py", "consulta_faturas.py"])

elif menu_selecionado == "⚙️ Configurações (.env)":
    carregar_script(["5_Configuracoes_Env.py", "configuracoes_env.py"])