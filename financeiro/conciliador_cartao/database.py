import sqlite3
import json
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_FILE = str(BASE_DIR / "conciliacao.db")


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
            data_fechamento TEXT,
            dados_conciliados TEXT
        )
    """)

    # Adiciona a coluna data_fechamento caso a tabela já exista
    try:
        cursor.execute("ALTER TABLE faturas ADD COLUMN data_fechamento TEXT")
    except sqlite3.OperationalError:
        pass

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS compradores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE,
            nome TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS recorrencias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo_recorrencia TEXT,
            fornecedor_padrao TEXT,
            valor_esperado REAL,
            comprador TEXT,
            observacao TEXT
        )
    """)

    conn.commit()
    conn.close()


def listar_compradores():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT email, nome FROM compradores ORDER BY nome ASC")
    rows = cursor.fetchall()
    conn.close()
    return {row[0].lower().strip(): row[1] for row in rows}


def salvar_comprador(email, nome):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT OR REPLACE INTO compradores (email, nome)
        VALUES (?, ?)
    """,
        (email.lower().strip(), nome.strip()),
    )
    conn.commit()
    conn.close()


def excluir_comprador(email):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM compradores WHERE email = ?", (email.lower().strip(),))
    conn.commit()
    conn.close()


def salvar_recorrencia(tipo, fornecedor, valor, comprador, obs=""):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # Verifica se já não existe recorrência idêntica para não salvar repetido
    cursor.execute(
        """
        SELECT id FROM recorrencias 
        WHERE tipo_recorrencia = ? AND fornecedor_padrao = ? AND abs(valor_esperado - ?) < 0.05
    """,
        (tipo, fornecedor.strip(), valor),
    )
    if not cursor.fetchone():
        cursor.execute(
            """
            INSERT INTO recorrencias (tipo_recorrencia, fornecedor_padrao, valor_esperado, comprador, observacao)
            VALUES (?, ?, ?, ?, ?)
        """,
            (tipo, fornecedor.strip(), valor, comprador, obs),
        )
        conn.commit()
    conn.close()


def listar_recorrencias():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, tipo_recorrencia, fornecedor_padrao, valor_esperado, comprador, observacao FROM recorrencias ORDER BY id ASC"
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def excluir_recorrencia(recorrencia_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM recorrencias WHERE id = ?", (recorrencia_id,))
    conn.commit()
    conn.close()


def buscar_nf_parcela_1(descricao_base):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT dados_conciliados FROM faturas")
    rows = cursor.fetchall()
    conn.close()

    desc_limpa = descricao_base.split("PARC")[0].strip().upper()

    for row in rows:
        try:
            itens = json.loads(row[0])
            for it in itens:
                desc_ant = it.get("descricao", it.get("fornecedor", "")).upper()
                parc_ant = it.get("parcela", "")
                anexos_ant = it.get("anexos_nf", [])

                if desc_limpa in desc_ant and (
                    parc_ant.startswith("1/") or "PARC 01" in desc_ant
                ):
                    if anexos_ant:
                        return anexos_ant, it.get("comprador", "")
        except:
            continue
    return [], ""


def salvar_fatura(nome_arquivo, vencimento, valor_total, dados_lista):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO faturas (nome_arquivo, data_vencimento, valor_total, status, dados_conciliados)
        VALUES (?, ?, ?, 'ABERTA', ?)
        ON CONFLICT(data_vencimento) DO UPDATE SET
            nome_arquivo=excluded.nome_arquivo,
            valor_total=excluded.valor_total,
            dados_conciliados=excluded.dados_conciliados
    """,
        (
            nome_arquivo,
            vencimento,
            valor_total,
            json.dumps(dados_lista, ensure_ascii=False),
        ),
    )
    conn.commit()
    conn.close()


def fechar_fatura(vencimento, dados_lista):
    agora_formatado = datetime.now().strftime("%d/%m/%Y %H:%M")
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE faturas 
        SET status = 'FECHADA', data_fechamento = ?, dados_conciliados = ? 
        WHERE data_vencimento = ?
    """,
        (agora_formatado, json.dumps(dados_lista, ensure_ascii=False), vencimento),
    )
    conn.commit()
    conn.close()


def reabrir_fatura(vencimento):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE faturas SET status = 'ABERTA', data_fechamento = NULL WHERE data_vencimento = ?",
        (vencimento,),
    )
    conn.commit()
    conn.close()


def carregar_fatura(vencimento):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT status, dados_conciliados FROM faturas WHERE data_vencimento = ?",
        (vencimento,),
    )
    row = cursor.fetchone()
    conn.close()
    if row:
        return row[0], json.loads(row[1])
    return None, None


def listar_faturas():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, nome_arquivo, data_vencimento, valor_total, status, data_fechamento FROM faturas ORDER BY id DESC"
    )
    rows = cursor.fetchall()
    conn.close()
    return rows
