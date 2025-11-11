import os, pyodbc
from dotenv import load_dotenv

load_dotenv()
def get_conn():
    auth_mode = os.getenv('AUTH_MODE', '').lower()
    if auth_mode == 'windows':
        conn_str = (
            f"DRIVER={{{os.getenv('DB_DRIVER','ODBC Driver 18 for SQL Server')}}};"
            f"SERVER={os.getenv('DB_SERVER')};"
            f"DATABASE={os.getenv('DB_NAME')};"
            "Trusted_Connection=yes;"
            "Encrypt=yes;TrustServerCertificate=yes;"
        )
    else:
        conn_str = (
            f"DRIVER={{{os.getenv('DB_DRIVER','ODBC Driver 18 for SQL Server')}}};"
            f"SERVER={os.getenv('DB_SERVER')};"
            f"DATABASE={os.getenv('DB_NAME')};"
            f"UID={os.getenv('DB_USER')};PWD={os.getenv('DB_PASS')};"
            "Encrypt=yes;TrustServerCertificate=yes;"
        )
    conn = pyodbc.connect(conn_str)
    conn.autocommit = True
    return conn

def run_sql_file(path: str):
    with open(path, 'r', encoding='utf-8') as f:
        script = f.read()
    with get_conn() as cn:
        cur = cn.cursor()
        for stmt in [s.strip() for s in script.split(';') if s.strip()]:
            cur.execute(stmt)
