import imaplib
import os
from dotenv import load_dotenv

load_dotenv()

host = os.getenv("IMAP_HOST")
port = int(os.getenv("IMAP_PORT", 993))
user = os.getenv("IMAP_USER")
pwd = os.getenv("IMAP_PASSWORD")

try:
    mail = imaplib.IMAP4_SSL(host, port=port)
    mail.login(user, pwd)
    print("Conexão realizada com sucesso!\nListando pastas do servidor:\n" + "-"*40)
    
    status, pastas = mail.list()
    for p in pastas:
        print(p.decode("utf-8", errors="ignore"))
        
    mail.logout()
except Exception as e:
    print(f"Erro ao listar pastas: {e}")