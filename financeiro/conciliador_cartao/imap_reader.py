import imaplib
import email
from email.header import decode_header
import re
import os
import html
from dotenv import load_dotenv

load_dotenv()

NOTAS_DIR = "notas_fiscais"
os.makedirs(NOTAS_DIR, exist_ok=True)

def obter_configuracoes_env():
    """Retorna as credenciais e configurações salvas no arquivo .env"""
    return {
        "host": os.getenv("IMAP_HOST", ""),
        "port": int(os.getenv("IMAP_PORT", 993)),
        "user": os.getenv("IMAP_USER", ""),
        "password": os.getenv("IMAP_PASSWORD", ""),
        "folder": os.getenv("IMAP_FOLDER", "Cartao de credito").strip('"')
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

def extrair_dados_email(corpo_texto):
    """Extrai os dados da compra limpando formatações HTML, negritos e caracteres ocultos."""
    dados = {
        "tipo": "Fiscal",
        "data_compra": None,
        "chegou_dia": None,
        "parcelas": 1,
        "vencimento": [],
        "valor_nota": 0.0,
        "desconto": 0.0,
        "valor_pago": 0.0
    }
    
    # 1. Limpeza de tags HTML e entidades (&nbsp;, etc.)
    texto_limpo = re.sub(r"<[^>]+>", " ", corpo_texto)
    texto_limpo = html.unescape(texto_limpo)
    texto_limpo = re.sub(r"[ \t\xa0]+", " ", texto_limpo)

    # 2. Tipo (Fiscal ou Gerencial)
    m_tipo = re.search(r"Tipo\s*:\s*(Fiscal|Gerencial)", texto_limpo, re.IGNORECASE)
    if m_tipo:
        dados["tipo"] = m_tipo.group(1).capitalize()
        
    # 3. Compra dia
    m_compra = re.search(r"Compra\s*dia\s*:\s*(\d{2}/\d{2}/\d{2,4})", texto_limpo, re.IGNORECASE)
    if m_compra:
        dados["data_compra"] = m_compra.group(1)
        
    # 4. Parcelas (ex: 3x, 3)
    m_parc = re.search(r"Parcelas?\s*:\s*(\d+)", texto_limpo, re.IGNORECASE)
    if m_parc:
        dados["parcelas"] = int(m_parc.group(1))
        
    # 5. Vencimentos (datas no formato DD/MM/AAAA)
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

    # 6. Valores (tolerante a negrito, espaços, R$)
    m_vnota = re.search(r"Valor\s+da\s+nota\s*:\s*(?:R\$\s*)?([\d\.,]+)", texto_limpo, re.IGNORECASE)
    if m_vnota:
        dados["valor_nota"] = converter_valor(m_vnota.group(1))

    m_desc = re.search(r"Desconto\s*:\s*(?:R\$\s*)?([\d\.,]+)", texto_limpo, re.IGNORECASE)
    if m_desc:
        dados["desconto"] = converter_valor(m_desc.group(1))

    m_pago = re.search(r"Pago\s*:\s*(?:R\$\s*)?([\d\.,]+)", texto_limpo, re.IGNORECASE)
    if m_pago:
        dados["valor_pago"] = converter_valor(m_pago.group(1))
        
    return dados

def buscar_emails_imap(host, porta, usuario, senha, pasta_nome="Cartao de credito"):
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
            f'"{pasta_nome.replace("INBOX/", "").replace("INBOX.", "")}"'
        ]
        
        selecionou = False
        for p in tentativas:
            status, _ = mail.select(p)
            if status == "OK":
                selecionou = True
                break
                
        if not selecionou:
            mail.logout()
            return False, f"Pasta '{pasta_nome}' não encontrada no servidor."

        status, messages = mail.search(None, '(SUBJECT "Compras - Cart")')
        if status != "OK" or not messages[0]:
            mail.logout()
            return True, []

        email_ids = messages[0].split()
        for idx_e, eid in enumerate(email_ids):
            res, msg_data = mail.fetch(eid, "(RFC822)")
            if res != "OK":
                continue
                
            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)
            
            assunto = decodificar_texto(msg.get("Subject", ""))
            de = decodificar_texto(msg.get("From", ""))
            
            corpo = ""
            lista_anexos = []
            
            if msg.is_multipart():
                for part in msg.walk():
                    content_type = part.get_content_type()
                    content_disposition = str(part.get("Content-Disposition"))
                    
                    if content_type in ["text/plain", "text/html"] and "attachment" not in content_disposition:
                        payload = part.get_payload(decode=True)
                        if payload:
                            corpo += payload.decode("utf-8", errors="ignore") + "\n"
                    elif "attachment" in content_disposition or part.get_filename():
                        filename = part.get_filename()
                        if filename:
                            filename = decodificar_texto(filename)
                            # FILTRO ESTRITO: Apenas arquivos PDF são considerados NFs/faturas
                            if filename.lower().endswith(".pdf"):
                                caminho = os.path.join(NOTAS_DIR, filename)
                                with open(caminho, "wb") as f:
                                    f.write(part.get_payload(decode=True))
                                lista_anexos.append(filename)
            else:
                payload = msg.get_payload(decode=True)
                if payload:
                    corpo = payload.decode("utf-8", errors="ignore")

            dados = extrair_dados_email(corpo)
            dados["numero_item"] = idx_e + 1  # Contagem começando do 1
            dados["email_id"] = f"email_{idx_e + 1}"
            dados["assunto"] = assunto
            dados["remetente"] = de
            dados["anexos_nf"] = lista_anexos
            dados["vinculado"] = False
            compras_email.append(dados)
            
        mail.logout()
        return True, compras_email

    except Exception as e:
        return False, str(e)