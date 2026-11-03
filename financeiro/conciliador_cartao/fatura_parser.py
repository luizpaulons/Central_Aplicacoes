import pandas as pd
import re

def processar_fatura_xlsx(caminho_arquivo):
    df = pd.read_excel(caminho_arquivo, sheet_name=0)
    
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

    # Extrai o ano da data de vencimento (ex: '05/11/2026' -> '2026')
    ano_fatura = "2026"
    if vencimento and "/" in vencimento:
        partes_v = vencimento.split("/")
        if len(partes_v) == 3:
            ano_fatura = partes_v[2]

    lancamentos = []
    
    for idx in range(8, len(df)):
        linha_data = str(df.iloc[idx, 0]).strip()
        descricao = str(df.iloc[idx, 1]).strip()
        valor_raw = str(df.iloc[idx, 3]).strip()
        
        if not re.match(r"^\d{2}/\d{2}$", linha_data):
            continue
        if "PGTO DEBITO" in descricao or "SubTotal" in descricao or "Total" in descricao:
            continue
            
        try:
            val_limpo = valor_raw.replace(".", "").replace(",", ".")
            valor = float(val_limpo)
        except:
            continue
            
        # Constrói a data completa: DD/MM/AAAA
        data_completa = f"{linha_data}/{ano_fatura}"

# 1. Padrão tradicional: PARC 05/10 ou PARC 1/12
        m_parc = re.search(r"PARC\s*(\d{1,2})/(\d{1,2})", descricao, re.IGNORECASE)
        
        # 2. Padrão Tokio Marine / Seguradoras: AUTO01D12, AUTO11D12, 01D12
        if not m_parc:
            m_parc = re.search(r"(?:AUTO)?(\d{1,2})D(\d{1,2})", descricao, re.IGNORECASE)

        num_parcela = 1
        total_parcelas = 1
        parcela_info = None
        
        if m_parc:
            num_parcela = int(m_parc.group(1))
            total_parcelas = int(m_parc.group(2))
            parcela_info = f"{num_parcela}/{total_parcelas}"
            
        lancamentos.append({
            "id_linha": idx,
            "data_fatura": data_completa,
            "fornecedor": descricao,
            "valor": valor,
            "parcela": parcela_info,
            "num_parcela": num_parcela,
            "comprador": "Não identificado",
            "status": "PENDENTE",
            "tipo": "",
            "anexos_nf": [],
            "numeros_nf": [],
            "observacao": "",
            "recorrente_salvo": False
        })
        
    return vencimento, valor_total, lancamentos