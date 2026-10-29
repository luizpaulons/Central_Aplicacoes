import pandas as pd
import re

def processar_fatura_xlsx(caminho_arquivo):
    """Processa a fatura no formato exato da planilha da LYND CALCADOS LTDA."""
    df = pd.read_excel(caminho_arquivo, sheet_name=0)
    
    # Extrai o vencimento e o valor total do cabeçalho
    vencimento = None
    valor_total = 0.0
    
    for i in range(min(10, len(df))):
        col0 = str(df.iloc[i, 0]).strip().lower()
        if "data vencimento" in col0:
            vencimento = str(df.iloc[i, 1]).strip()
        elif "valor total" in col0:
            val_raw = str(df.iloc[i, 1]).replace(".", "").replace(",", ".")
            try:
                valor_total = float(val_raw)
            except:
                pass

    # A partir da linha 8 estão os lançamentos
    # Coluna 0: Data | Coluna 1: Lançamento | Coluna 3: Valor
    lancamentos = []
    
    for idx in range(8, len(df)):
        linha_data = str(df.iloc[idx, 0]).strip()
        descricao = str(df.iloc[idx, 1]).strip()
        valor_raw = str(df.iloc[idx, 3]).strip()
        
        # Ignora linhas de subtotal, pagamentos e cabeçalhos
        if not re.match(r"^\d{2}/\d{2}$", linha_data):
            continue
        if "PGTO DEBITO" in descricao or "SubTotal" in descricao or "Total" in descricao:
            continue
            
        try:
            val_limpo = valor_raw.replace(".", "").replace(",", ".")
            valor = float(val_limpo)
        except:
            continue
            
        # Detecta se é parcelada pela descrição (ex: PARC 01/03)
        m_parc = re.search(r"PARC\s*(\d{2})/(\d{2})", descricao, re.IGNORECASE)
        parcela_info = None
        if m_parc:
            parcela_info = f"{int(m_parc.group(1))}/{int(m_parc.group(2))}"
            
        lancamentos.append({
            "id_linha": idx,
            "data_fatura": linha_data,
            "descricao": descricao,
            "valor": valor,
            "parcela": parcela_info,
            "status": "PENDENTE",
            "tipo": "",
            "anexo_nf": None,
            "observacao": ""
        })
        
    return vencimento, valor_total, lancamentos