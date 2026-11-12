import imaplib
import email
from email.header import decode_header
import email.utils
import re
import os
import html
from pathlib import Path
from dotenv import load_dotenv

try:
    from pypdf import PdfReader

    PYPDF_DISPONIVEL = True
except ImportError:
    PYPDF_DISPONIVEL = False

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

NOTAS_DIR = str(BASE_DIR / "notas_fiscais")
os.makedirs(NOTAS_DIR, exist_ok=True)


def obter_configuracoes_env():
    # Recarrega o .env da pasta da aplicação caso tenha sido atualizado
    load_dotenv(BASE_DIR / ".env", override=True)
    return {
        "host": os.getenv("IMAP_HOST", ""),
        "port": int(os.getenv("IMAP_PORT", 993)),
        "user": os.getenv("IMAP_USER", ""),
        "password": os.getenv("IMAP_PASSWORD", ""),
        "folder": os.getenv("IMAP_FOLDER", "Cartao de credito").strip('"'),
    }


def decodificar_texto(texto):
    if not texto:
        return ""
    pedacos = decode_header(texto)
    resultado = ""
    for pedaco, encoding in pedacos:
        if isinstance(pedaco, bytes):
            resultado += pedaco.decode(encoding or "utf-8", errors="ignore")
        else:
            resultado += str(pedaco)
    return resultado


def limpar_nome_arquivo(nome):
    if not nome:
        return "anexo_sem_nome.pdf"
    nome = decodificar_texto(nome)
    nome = nome.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    nome = re.sub(r'[<>:"/\\|?*]', "_", nome)
    return re.sub(r"\s+", " ", nome).strip()


def extrair_email_puro(header_from):
    if not header_from:
        return ""
    _, endereco = email.utils.parseaddr(header_from)
    if endereco and "@" in endereco:
        return endereco.lower().strip()
    m = re.search(r"[\w\.-]+@[\w\.-]+", header_from)
    return m.group(0).lower().strip() if m else header_from.lower().strip()


def formatar_vencimento_aammdd(data_vencimento_str):
    """
    Converte datas do tipo DD/MM/AAAA para AAMMDD.
    Ex: 05/11/2026 -> 261105
    """
    if not data_vencimento_str:
        return ""
    partes = str(data_vencimento_str).strip().split("/")
    if len(partes) == 3:
        dia, mes, ano = partes[0].zfill(2), partes[1].zfill(2), partes[2]
        ano_2 = ano[-2:]
        return f"{ano_2}{mes}{dia}"
    return ""


def extrair_numero_e_tipo_nf(caminho_pdf, nome_arquivo=""):
    """
    1. Se for NFSe (Serviço): Extrai o número DIRETAMENTE do nome do arquivo original.
       Exemplo: NFSe-202600002966737.pdf -> 202600002966737
    2. Se for NFe (Mercantil/DANFE): Extrai via Chave de Acesso SEFAZ (44 dígitos, posições 26 a 34).
    Retorna: (numero_nf, eh_servico)
    """
    if nome_arquivo:
        # Padrão 1: Contém explicitamente NFSe / NFS-e seguido do número
        m_nfse_direto = re.search(r"NFS[eE]?[\s\-_]*(\d+)", nome_arquivo, re.IGNORECASE)
        if m_nfse_direto:
            num = m_nfse_direto.group(1).lstrip("0")
            return (num if num else m_nfse_direto.group(1)), True

        # Padrão 2: Prefixo de CNPJ seguido do número da NFSe
        m_cnpj_num = re.search(r"^\d{14}_(\d+)\.pdf$", nome_arquivo, re.IGNORECASE)
        if m_cnpj_num:
            num = m_cnpj_num.group(1).lstrip("0")
            return (num if num else m_cnpj_num.group(1)), True

        # Padrão 3: Chave de 44 dígitos no nome (DANFE / NFe)
        chaves_nome = re.findall(r"\b\d{44}\b", re.sub(r"\D", "", nome_arquivo))
        if chaves_nome:
            return chaves_nome[0][25:34].lstrip("0") or "0", False

    # Leitura interna SOMENTE se NÃO for identificada como NFSe pelo nome
    if not caminho_pdf and nome_arquivo:
        caminho_pdf = os.path.join(NOTAS_DIR, nome_arquivo)

    if PYPDF_DISPONIVEL and caminho_pdf and os.path.exists(caminho_pdf):
        try:
            reader = PdfReader(caminho_pdf)
            texto = ""
            for p in reader.pages[:2]:
                texto += (p.extract_text() or "") + "\n"

            # DANFE / Chave SEFAZ de 44 dígitos (11 blocos de 4 dígitos)
            m_blocos = re.search(r"(?:\b|\D)(\d{4}(?:\s+\d{4}){10})(?:\b|\D)", texto)
            if m_blocos:
                chave = re.sub(r"\D", "", m_blocos.group(1))
                if len(chave) == 44:
                    return chave[25:34].lstrip("0") or "0", False

            # Chave após "CHAVE DE ACESSO"
            m_chave_txt = re.search(
                r"CHAVE\s+DE\s+ACESSO[\s\S]{0,80}?([\d\s]{44,70})", texto, re.IGNORECASE
            )
            if m_chave_txt:
                cand = re.sub(r"\D", "", m_chave_txt.group(1))
                if len(cand) >= 44:
                    return cand[:44][25:34].lstrip("0") or "0", False

            apenas_numeros = re.sub(r"\D", "", texto)
            for m in re.finditer(r"(?=((\d{20})(55|65)(\d{22})))", apenas_numeros):
                chave_valida = m.group(1)
                return chave_valida[25:34].lstrip("0") or "0", False

            chaves_gerais = re.findall(r"\d{44}", apenas_numeros)
            if chaves_gerais:
                return chaves_gerais[0][25:34].lstrip("0") or "0", False
        except Exception:
            pass

    return "-", False


def extrair_numero_nf_pdf(caminho_pdf, nome_arquivo=""):
    num, _ = extrair_numero_e_tipo_nf(caminho_pdf, nome_arquivo)
    return num


def extrair_dados_email(corpo_texto):
    dados = {
        "tipo": "Fiscal",
        "data_compra": None,
        "chegou_dia": None,
        "parcelas": 1,
        "vencimento": [],
        "valor_nota": 0.0,
        "desconto": 0.0,
        "valor_pago": 0.0,
    }

    texto_limpo = re.sub(r"<[^>]+>", " ", corpo_texto)
    texto_limpo = html.unescape(texto_limpo)
    texto_limpo = re.sub(r"[ \t\xa0]+", " ", texto_limpo)

    m_tipo = re.search(r"Tipo\s*:\s*(Fiscal|Gerencial)", texto_limpo, re.IGNORECASE)
    if m_tipo:
        dados["tipo"] = m_tipo.group(1).capitalize()

    m_compra = re.search(
        r"Compra\s*dia\s*:\s*(\d{2}/\d{2}/\d{2,4})", texto_limpo, re.IGNORECASE
    )
    if m_compra:
        dados["data_compra"] = m_compra.group(1)

    m_parc = re.search(r"Parcelas?\s*:\s*(\d+)", texto_limpo, re.IGNORECASE)
    if m_parc:
        dados["parcelas"] = int(m_parc.group(1))

    m_venc = re.findall(r"\b(\d{2}/\d{2}/\d{4})\b", texto_limpo)
    if m_venc:
        dados["vencimento"] = m_venc

    def converter_valor(val_str):
        if not val_str:
            return 0.0
        val = re.sub(r"[^\d,\.]", "", val_str)
        val = val.strip().replace(".", "").replace(",", ".")
        try:
            return float(val)
        except ValueError:
            return 0.0

    m_vnota = re.search(
        r"Valor\s+da\s+nota\s*:\s*(?:R\$\s*)?([\d\.,]+)", texto_limpo, re.IGNORECASE
    )
    if m_vnota:
        dados["valor_nota"] = converter_valor(m_vnota.group(1))

    m_desc = re.search(
        r"Desconto\s*:\s*(?:R\$\s*)?([\d\.,]+)", texto_limpo, re.IGNORECASE
    )
    if m_desc:
        dados["desconto"] = converter_valor(m_desc.group(1))

    m_pago = re.search(r"Pago\s*:\s*(?:R\$\s*)?([\d\.,]+)", texto_limpo, re.IGNORECASE)
    if m_pago:
        dados["valor_pago"] = converter_valor(m_pago.group(1))

    return dados


def buscar_emails_imap(
    host,
    porta,
    usuario,
    senha,
    pasta_nome="Cartao de credito",
    data_vencimento_fatura="",
):
    compras_email = []

    try:
        mail = imaplib.IMAP4_SSL(host, port=porta)
        mail.login(usuario, senha)

        tentativas = [
            f'"{pasta_nome}"',
            pasta_nome,
            f'"INBOX/{pasta_nome}"',
            f"INBOX/{pasta_nome}",
            f'"INBOX.{pasta_nome}"',
            f"INBOX.{pasta_nome}",
        ]
        selecionou = False
        for p in tentativas:
            if mail.select(p)[0] == "OK":
                selecionou = True
                break

        if not selecionou:
            mail.logout()
            return False, f"Pasta '{pasta_nome}' não encontrada no servidor."

        status, messages = mail.search(None, '(SUBJECT "Compras - Cart")')
        if status != "OK" or not messages[0]:
            mail.logout()
            return True, []

        for idx_e, eid in enumerate(messages[0].split()):
            res, msg_data = mail.fetch(eid, "(RFC822)")
            if res != "OK":
                continue
            msg = email.message_from_bytes(msg_data[0][1])
            assunto = decodificar_texto(msg.get("Subject", ""))
            remetente = extrair_email_puro(decodificar_texto(msg.get("From", "")))

            corpo = ""
            partes_anexos = []

            if msg.is_multipart():
                for part in msg.walk():
                    cdisp = str(part.get("Content-Disposition"))
                    if (
                        part.get_content_type() in ["text/plain", "text/html"]
                        and "attachment" not in cdisp
                    ):
                        payload = part.get_payload(decode=True)
                        if payload:
                            corpo += payload.decode("utf-8", errors="ignore") + "\n"
                    elif "attachment" in cdisp or part.get_filename():
                        fn = limpar_nome_arquivo(part.get_filename())
                        if fn.lower().endswith(".pdf"):
                            partes_anexos.append((fn, part.get_payload(decode=True)))
            else:
                payload = msg.get_payload(decode=True)
                if payload:
                    corpo = payload.decode("utf-8", errors="ignore")

            dados = extrair_dados_email(corpo)

            # Prefixo AAMMDD: pega da fatura ou da data no corpo do e-mail
            venc_ref = data_vencimento_fatura or (
                dados["vencimento"][0] if dados["vencimento"] else ""
            )
            prefixo_data = formatar_vencimento_aammdd(venc_ref)

            lista_anexos = []
            lista_nfs = []

            for fn_orig, payload_bytes in partes_anexos:
                # Salva temporário para análise
                caminho_temp = os.path.join(NOTAS_DIR, f"temp_{fn_orig}")
                with open(caminho_temp, "wb") as f_temp:
                    f_temp.write(payload_bytes)

                num_nf, eh_servico = extrair_numero_e_tipo_nf(caminho_temp, fn_orig)

                # Define o nome oficial conforme as regras
                if prefixo_data and num_nf and num_nf != "-":
                    tipo_tag = "NFSe" if eh_servico else "NF"
                    nome_padronizado = f"{prefixo_data}-{tipo_tag}{num_nf}.pdf"
                else:
                    nome_padronizado = fn_orig

                caminho_final = os.path.join(NOTAS_DIR, nome_padronizado)
                if os.path.exists(caminho_final):
                    try:
                        os.remove(caminho_final)
                    except:
                        pass

                os.replace(caminho_temp, caminho_final)
                lista_anexos.append(nome_padronizado)
                lista_nfs.append(num_nf)

            dados["numero_item"] = idx_e + 1
            dados["remetente"] = remetente
            dados["assunto"] = assunto
            dados["anexos_nf"] = lista_anexos
            dados["numeros_nf"] = lista_nfs
            dados["vinculado"] = False
            compras_email.append(dados)

        mail.logout()
        return True, compras_email
    except Exception as e:
        return False, str(e)
