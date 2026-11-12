import io
import re
import pandas as pd


def processar_fatura_xlsx(arquivo_origem):
    """
    Valida o layout da fatura e extrai vencimento, valor total e lançamentos.
    Retorna: (sucesso: bool, mensagem_ou_vencimento, valor_total, lancamentos)
    """
    try:
        if isinstance(arquivo_origem, bytes):
            fonte = io.BytesIO(arquivo_origem)
        else:
            fonte = arquivo_origem

        df = pd.read_excel(fonte, sheet_name=0)
    except Exception as e:
        return False, f"Erro ao ler o arquivo Excel: {e}", 0.0, []

    if df.empty or df.shape[1] < 4:
        return (
            False,
            "Arquivo fora do layout esperado da fatura (colunas insuficientes).",
            0.0,
            [],
        )

    vencimento = None
    valor_total = 0.0
    encontrou_cabecalho_fatura = False

    # Valida as primeiras 12 linhas procurando os campos característicos da fatura
    for i in range(min(12, len(df))):
        col0 = str(df.iloc[i, 0]).strip().lower() if pd.notna(df.iloc[i, 0]) else ""
        col1 = str(df.iloc[i, 1]).strip() if pd.notna(df.iloc[i, 1]) else ""

        if "data vencimento" in col0 or "vencimento" in col0:
            vencimento = col1
            encontrou_cabecalho_fatura = True
        elif "valor total" in col0:
            encontrou_cabecalho_fatura = True
            val_raw = col1.replace("R$", "").replace(".", "").replace(",", ".").strip()
            try:
                valor_total = float(val_raw)
            except:
                pass

    if not encontrou_cabecalho_fatura or not vencimento:
        return (
            False,
            "Arquivo fora do layout da fatura! Verifique se enviou a planilha correta do cartão.",
            0.0,
            [],
        )

    lancamentos = []
    for idx in range(6, len(df)):
        linha_data = str(df.iloc[idx, 0]).strip() if pd.notna(df.iloc[idx, 0]) else ""
        descricao = str(df.iloc[idx, 1]).strip() if pd.notna(df.iloc[idx, 1]) else ""
        valor_raw = str(df.iloc[idx, 3]).strip() if pd.notna(df.iloc[idx, 3]) else ""

        if not re.match(r"^\d{2}/\d{2}", linha_data):
            continue
        if any(
            p in descricao.upper()
            for p in [
                "PGTO DEBITO",
                "SUBTOTAL",
                "TOTAL DA FATURA",
                "PAGAMENTO EFETUADO",
            ]
        ):
            continue

        try:
            val_limpo = (
                valor_raw.replace("R$", "")
                .replace(" ", "")
                .replace(".", "")
                .replace(",", ".")
            )
            valor = float(val_limpo)
        except:
            continue

        # Detecta parcelamento padrão (PARC 05/10) ou seguradoras (AUTO01D12 / 01D12)
        m_parc = re.search(r"PARC\s*(\d{1,2})/(\d{1,2})", descricao, re.IGNORECASE)
        if not m_parc:
            m_parc = re.search(
                r"(?:AUTO)?(\d{1,2})D(\d{1,2})", descricao, re.IGNORECASE
            )

        num_parcela = 1
        total_parcelas = 1
        parcela_info = None

        if m_parc:
            num_parcela = int(m_parc.group(1))
            total_parcelas = int(m_parc.group(2))
            parcela_info = f"{num_parcela}/{total_parcelas}"

        lancamentos.append(
            {
                "id_linha": idx,
                "data_fatura": linha_data[:5],
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
                "recorrente_salvo": False,
            }
        )

    if not lancamentos:
        return (
            False,
            "Arquivo fora do layout: nenhum lançamento válido encontrado na fatura.",
            0.0,
            [],
        )

    return True, vencimento, valor_total, lancamentos
