import psycopg

DB_DSN = "postgresql://schedule_app:1@localhost:5432/schedule_db"
with psycopg.connect(DB_DSN) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT 1;")
        print(cur.fetchone())
print("OK")