import requests
import json
import os
import modal
from collections import defaultdict
import time

DB_HOST = os.getenv("DB_HOST", "db-bitcoin-info.ctoim6igklzt.us-east-2.rds.amazonaws.com")
DB_USER = os.getenv("DB_USER", "admin") 
DB_PASSWORD = os.getenv("DB_PASSWORD", "db-bitcoin-info")
DB_NAME = "db-bitcoin-info"
DB_PORT = os.getenv("DB_PORT", "3306")

image = (
    modal.Image.debian_slim(python_version="3.10")
    .pip_install(["pymysql", "requests"])
    .env({
        "DB_HOST": "db-bitcoin-info.ctoim6igklzt.us-east-2.rds.amazonaws.com",
        "DB_USER": "admin",
        "DB_PASSWORD": "db-bitcoin-info",
        "DB_PORT": "3306"
    })
)

# Load environment variables
# load_dotenv()

app = modal.App(name="fy-db-auto-fetch-server")

# RPC configuration
RPC_USER = "eager-borg"
RPC_PASSWORD = "churn-romp-puma-crown-claw-finer"
RPC_URL = "https://bitcoin-mainnet.core.chainstack.com"

# Database connection configuration
DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = "bitcoin"
DB_PORT = int(os.getenv("DB_PORT", 3306))

@app.function(image=image)
def rpc_call(method, params=[]):
    """Send RPC request to Bitcoin node"""
    payload = json.dumps({"jsonrpc": "1.0", "id": "rpc", "method": method, "params": params})
    response = requests.post(RPC_URL, auth=(RPC_USER, RPC_PASSWORD), data=payload, headers={"content-type": "text/plain"})
    return response.json()["result"]

@app.function(image=image)
def get_db_schema():
    """Get database table structure information"""
    import pymysql
    conn = pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        port=DB_PORT
    )
    
    schema = {}
    foreign_keys = defaultdict(list)
    primary_keys = {}
    
    try:
        with conn.cursor() as cursor:
            # Get all table information
            cursor.execute("""
                SELECT TABLE_NAME 
                FROM INFORMATION_SCHEMA.TABLES 
                WHERE TABLE_SCHEMA = %s
            """, (DB_NAME,))
            tables = cursor.fetchall()
            
            # Get column information for each table
            for table in tables:
                table_name = table[0]
                schema[table_name] = {}
                
                # Get column information
                cursor.execute("""
                    SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_KEY
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
                    ORDER BY ORDINAL_POSITION
                """, (DB_NAME, table_name))
                
                for column in cursor.fetchall():
                    column_name, data_type, is_nullable, column_key = column
                    schema[table_name][column_name] = {
                        'data_type': data_type,
                        'nullable': is_nullable == 'YES',
                        'is_primary': column_key == 'PRI'
                    }
                    
                    # Record primary key
                    if column_key == 'PRI':
                        primary_keys[table_name] = column_name
            
            # Get foreign key relationships
            cursor.execute("""
                SELECT TABLE_NAME, COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
                FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
                WHERE TABLE_SCHEMA = %s AND REFERENCED_TABLE_SCHEMA = %s
            """, (DB_NAME, DB_NAME))
            
            for fk in cursor.fetchall():
                table_name, column_name, ref_table, ref_column = fk
                foreign_keys[table_name].append({
                    'column': column_name,
                    'references': {'table': ref_table, 'column': ref_column}
                })
    finally:
        conn.close()
    
    return schema, foreign_keys, primary_keys

@app.function(image=image)
def map_json_to_tables(json_data, schema, foreign_keys, primary_keys):
    """Map JSON data to corresponding table structure"""
    mapped_data = {}
    
    # Process block data
    block_table = "bitcoin_block"
    if block_table in schema:
        block_data = {col: json_data.get(col, None) 
                     for col in schema[block_table] 
                     if col in json_data}
        mapped_data[block_table] = [block_data]
    
    # Process transaction data
    tx_table = "transaction"
    if tx_table in schema and "tx" in json_data:
        mapped_data[tx_table] = []
        for tx in json_data["tx"]:
            tx_data = {col: tx.get(col, None) 
                      for col in schema[tx_table] 
                      if col in tx}
            # Add association with block
            tx_data["block_hash"] = json_data.get("hash", None)
            mapped_data[tx_table].append(tx_data)
            
            # Process transaction inputs
            vin_table = "vin"
            if vin_table in schema and "vin" in tx:
                if vin_table not in mapped_data:
                    mapped_data[vin_table] = []
                
                for vin_item in tx["vin"]:
                    vin_data = {col: vin_item.get(col, None) 
                               for col in schema[vin_table] 
                               if col in vin_item}
                    vin_data["txid"] = tx.get("txid", None)
                    mapped_data[vin_table].append((vin_data, vin_item))
                    
            # Process transaction outputs
            vout_table = "vout"
            if vout_table in schema and "vout" in tx:
                if vout_table not in mapped_data:
                    mapped_data[vout_table] = []
                
                for vout_item in tx["vout"]:
                    vout_data = {col: vout_item.get(col, None) 
                                for col in schema[vout_table] 
                                if col in vout_item}
                    vout_data["txid"] = tx.get("txid", None)
                    mapped_data[vout_table].append((vout_data, vout_item))
    
    return mapped_data

@app.function(image=image)
def insert_mapped_data(mapped_data, schema, foreign_keys, primary_keys):
    """Insert the mapped data into the database"""
    import pymysql
    conn = pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        port=DB_PORT
    )
    
    inserted_ids = {}
    
    try:
        with conn.cursor() as cursor:
            # Insert data in dependency order
            # 1. First insert block data
            if "bitcoin_block" in mapped_data:
                for block in mapped_data["bitcoin_block"]:
                    columns = list(block.keys())
                    placeholders = ', '.join(['%s'] * len(columns))
                    sql = f"""
                    INSERT INTO bitcoin_block ({', '.join(columns)})
                    VALUES ({placeholders})
                    ON DUPLICATE KEY UPDATE
                    {', '.join([f'{col} = VALUES({col})' for col in columns])}
                    """
                    cursor.execute(sql, list(block.values()))
                    
                    # Save block hash as foreign key reference
                    if "hash" in block:
                        inserted_ids["bitcoin_block"] = block["hash"]
                print(f"✅ Block data inserted successfully")
                
            # 2. Insert transaction data
            # if "transaction" in mapped_data:
            #     for tx in mapped_data["transaction"]:
            #         # Ensure block hash is available as foreign key
            #         if "bitcoin_block" in inserted_ids and "block_hash" not in tx:
            #             tx["block_hash"] = inserted_ids["bitcoin_block"]
                        
            #         columns = list(tx.keys())
            #         placeholders = ', '.join(['%s'] * len(columns))
            #         sql = f"""
            #         INSERT INTO transaction ({', '.join(columns)})
            #         VALUES ({placeholders})
            #         ON DUPLICATE KEY UPDATE
            #         {', '.join([f'{col} = VALUES({col})' for col in columns])}
            #         """
            #         cursor.execute(sql, list(tx.values()))
                    
            #         # Save transaction ID as foreign key reference
            #         if "txid" in tx:
            #             if "transaction" not in inserted_ids:
            #                 inserted_ids["transaction"] = {}
            #             inserted_ids["transaction"][tx["txid"]] = cursor.lastrowid
            #     print(f"✅ Transaction data inserted successfully")
                
            # # 3. Insert transaction input (vin) data
            # if "vin" in mapped_data:
            #     for vin_data, vin_raw in mapped_data["vin"]:
            #         columns = list(vin_data.keys())
            #         placeholders = ', '.join(['%s'] * len(columns))
            #         sql = f"""
            #         INSERT INTO vin ({', '.join(columns)})
            #         VALUES ({placeholders})
            #         """
            #         cursor.execute(sql, list(vin_data.values()))
            #         vin_id = cursor.lastrowid
                    
            #         # Insert witness data (if any)
            #         if "witness" in vin_raw and vin_raw["witness"]:
            #             for witness_data in vin_raw["witness"]:
            #                 sql = """
            #                 INSERT INTO vin_witness (vin_id, witness)
            #                 VALUES (%s, %s)
            #                 """
            #                 cursor.execute(sql, (vin_id, witness_data))
            #     print(f"✅ Transaction input data inserted successfully")
                
            # # 4. Insert transaction output (vout) data and related scriptPubKey
            # if "vout" in mapped_data:
                # for vout_data, vout_raw in mapped_data["vout"]:
                #     columns = list(vout_data.keys())
                #     placeholders = ', '.join(['%s'] * len(columns))
                #     sql = f"""
                #     INSERT INTO vout ({', '.join(columns)})
                #     VALUES ({placeholders})
                #     """
                #     cursor.execute(sql, list(vout_data.values()))
                #     vout_id = cursor.lastrowid
                    
                #     # Process scriptPubKey
                #     if "scriptPubKey" in vout_raw:
                #         script = vout_raw["scriptPubKey"]
                #         address = None
                #         if "address" in script:
                #             address = script["address"]
                #         elif "addresses" in script and script["addresses"]:
                #             address = script["addresses"][0]
                            
                #         sql = """
                #         INSERT INTO script_pubkey (vout_id, asm, description, hex, address, type)
                #         VALUES (%s, %s, %s, %s, %s, %s)
                #         """
                #         cursor.execute(sql, (
                #             vout_id,
                #             script.get("asm", ""),
                #             script.get("desc", ""),
                #             script.get("hex", ""),
                #             address,
                #             script.get("type", "")
                #         ))
                # print(f"✅ Transaction output data inserted successfully")
                
            conn.commit()
            print("✅ All data inserted successfully")
            
    except Exception as e:
        conn.rollback()
        print(f"❌ Error: {e}")
    finally:
        conn.close()

@app.function(image=image)
def save_block_to_db(block_data):
    """Save block data to the database"""
    print("🔍 Getting database structure...")
    schema, foreign_keys, primary_keys = get_db_schema.remote()
    print(f"✅ Got structure of {len(schema)} tables")
    
    print("🔄 Mapping JSON data to table structure...")
    mapped_data = map_json_to_tables.remote(block_data, schema, foreign_keys, primary_keys)
    
    print("📥 Inserting data into database...")
    insert_mapped_data.remote(mapped_data, schema, foreign_keys, primary_keys)

@app.function(schedule=modal.Cron("*/10 * * * *"), image=image)
def scheduled_sync():
    """Periodic task to sync the latest Bitcoin block to database"""
    print(f"⏰ Scheduled sync started at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # get latest block hash
        print("🔍 Getting latest block hash...")
        latest_block_hash = rpc_call.remote("getbestblockhash")
        print(f"✅ Latest block hash: {latest_block_hash}")
        
        # get latest block details
        print("📦 Getting block details...")
        latest_block = rpc_call.remote("getblock", [latest_block_hash, 2])
        print(f"✅ Got data for block #{latest_block['height']}")
        
        # save to database
        print("💾 Starting to save data to database...")
        save_block_to_db.remote(latest_block)
        
        print(f"✅ Sync completed successfully at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    except Exception as e:
        print(f"❌ Error during sync: {e}")

# Test database connection
@app.function(image=image)
def test_db_connection():
    """Test database connection"""
    import pymysql
    try:
        conn = pymysql.connect(
            host=os.environ.get("DB_HOST"),
            user=os.environ.get("DB_USER"),
            password=os.environ.get("DB_PASSWORD"),
            database="bitcoin",
            port=int(os.environ.get("DB_PORT", 3306)),
            connect_timeout=5
        )
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
        conn.close()
        return f"✅ Database connection successful: {result}"
    except Exception as e:
        return f"❌ Database connection failed: {e}"

# deploy the app
@app.local_entrypoint()
def main():
    print("🚀 Testing database connection...")
    try:
        result = test_db_connection.remote()
        print(result)
        
        print("🔄 Running one-time sync...")
        scheduled_sync.remote()
        
        print("""
✅ Setup complete!
- Scheduled task will run every 10 minutes
- To deploy permanently, run: modal deploy chainstackRPCcall.py
        """)
    except Exception as e:
        print(f"❌ Setup failed: {e}")