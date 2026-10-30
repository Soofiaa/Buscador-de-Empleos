import sqlite3
import sys

def backup(source_path, dest_path):
    src = sqlite3.connect(source_path)
    dst = sqlite3.connect(dest_path)
    with dst:
        src.backup(dst)
    dst.close()
    src.close()
    # Set journal_mode = DELETE on the backup
    conn = sqlite3.connect(dest_path)
    conn.execute("PRAGMA journal_mode = DELETE")
    conn.close()

if __name__ == "__main__":
    backup("/datos/ofertas.db", sys.argv[1])
