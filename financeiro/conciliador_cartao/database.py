import sqlite3
import json

DB_FILE = "conciliacao.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS faturas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_arquivo TEXT,
            data_vencimento TEXT UNIQUE,
            valor_total REAL,
            status TEXT DEFAULT 'ABERTA',
            dados_conciliados TEXT
        )
    """)
    conn.commit()
    conn.close()

def salvar_fatura(nome_arquivo, vencimento, valor_total, dados_lista):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO faturas (nome_arquivo, data_vencimento, valor_total, status, dados_conciliados)
        VALUES (?, ?, ?, 'ABERTA', ?)
    """, (nome_arquivo, vencimento, valor_total, json.dumps(dados_lista, ensure_ascii=False)))
    conn.commit()
    conn.close()

def fechar_fatura(vencimento, dados_lista):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE faturas 
        SET status = 'FECHADA', dados_conciliados = ? 
        WHERE data_vencimento = ?
    """, (json.dumps(dados_lista, ensure_ascii=False), vencimento))
    conn.commit()
    conn.close()

def reabrir_fatura(vencimento):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE faturas SET status = 'ABERTA' WHERE data_vencimento = ?", (vencimento,))
    conn.commit()
    conn.close()

def carregar_fatura(vencimento):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT status, dados_conciliados FROM faturas WHERE data_vencimento = ?", (vencimento,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return row[0], json.loads(row[1])
    return None, None

def listar_faturas():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT id, nome_arquivo, data_vencimento, valor_total, status FROM faturas ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return rows