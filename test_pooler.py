import psycopg2

tests = [
    # 1. Pooler Singapore port 6543
    {
        "name": "Pooler 6543",
        "dsn": "postgresql://postgres.dgmmkirxdpflxniqpako:VasanthRaam%40123@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres"
    },
    # 2. Pooler Singapore port 5432
    {
        "name": "Pooler 5432",
        "dsn": "postgresql://postgres.dgmmkirxdpflxniqpako:VasanthRaam%40123@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres"
    },
    # 3. Direct host with port 6543 (pooler on direct host)
    {
        "name": "Direct Host 6543",
        "dsn": "postgresql://postgres:VasanthRaam%40123@db.dgmmkirxdpflxniqpako.supabase.co:6543/postgres"
    },
    # 4. Direct host with port 5432 (direct postgres connection)
    {
        "name": "Direct Host 5432",
        "dsn": "postgresql://postgres:VasanthRaam%40123@db.dgmmkirxdpflxniqpako.supabase.co:5432/postgres"
    }
]

for t in tests:
    print(f"Testing connection: {t['name']}...")
    try:
        conn = psycopg2.connect(t['dsn'], connect_timeout=5)
        print(f"  [+] SUCCESS!")
        conn.close()
    except Exception as e:
        print(f"  [-] FAILED: {e}")
    print("-" * 50)
