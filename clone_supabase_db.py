import asyncio
from sqlalchemy import create_engine, MetaData, Table, select, insert, text
from sqlalchemy.orm import sessionmaker

# ==============================================================================
# CONFIGURATION
# Replace these with your actual SUPABASE connection URIs (Direct Port 5432 or 6543)
# ==============================================================================
PROD_DB_URL = "postgresql://postgres:Vasanthraam%40123@db.kzjtserfhbkgzvcfpoyx.supabase.co:6543/postgres"
DEV_DB_URL = "postgresql://postgres:VasanthRaam%40123@db.dgmmkirxdpflxniqpako.supabase.co:6543/postgres"
# ==============================================================================

def clone_database():
    if "INSERT_YOUR_NEW_DEV" in DEV_DB_URL:
        print("[-] Error: Please update the DEV_DB_URL in the script first!")
        return

    print("[i] Connecting to databases...")
    prod_engine = create_engine(PROD_DB_URL)
    dev_engine = create_engine(DEV_DB_URL)

    prod_metadata = MetaData()
    
    print("[i] Reflecting tables from Production Database...")
    # This reads all tables, columns, indexes, and constraints from Prod
    prod_metadata.reflect(bind=prod_engine)
    
    print("[i] Dropping existing tables in Development Database (if any)...")
    # Clean up Dev DB first
    dev_metadata = MetaData()
    dev_metadata.reflect(bind=dev_engine)
    dev_metadata.drop_all(bind=dev_engine)
    
    print("[i] Creating table schemas in Development Database...")
    # Recreate all schemas in Dev DB in the correct dependency order
    prod_metadata.create_all(bind=dev_engine)
    print("[+] Table schemas successfully created in Dev!")

    print("[i] Cloning data table-by-table...")
    
    # We use connection to execute transactions
    with prod_engine.connect() as prod_conn, dev_engine.connect() as dev_conn:
        # Disable foreign key checks for this session to copy data smoothly in any order
        dev_conn.execute(text("SET session_replication_role = 'replica';"))
        dev_conn.commit()  # Make sure session settings are applied
        
        # Copy data for each table
        for table_name in prod_metadata.tables:
            table = Table(table_name, prod_metadata, autoload_with=prod_engine)
            
            # Fetch all rows from Prod table
            rows = prod_conn.execute(select(table)).fetchall()
            print(f"  - {table_name}: copying {len(rows)} row(s)...")
            
            if rows:
                # Convert rows to dicts for insertion
                data_to_insert = [row._asdict() for row in rows]
                dev_conn.execute(insert(table), data_to_insert)
                dev_conn.commit()  # Commit transaction
        
        # Reset replication role to default
        dev_conn.execute(text("SET session_replication_role = 'origin';"))
        dev_conn.commit()
        print("\n[+] Database clone complete! Schema and data are now in sync.")

if __name__ == "__main__":
    clone_database()
