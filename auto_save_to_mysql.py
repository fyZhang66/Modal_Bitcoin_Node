import json
import pymysql
import os
from dotenv import load_dotenv
from collections import defaultdict

# 加载环境变量
load_dotenv()

# 数据库连接配置
DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = "bitcoin"
DB_PORT = int(os.getenv("DB_PORT", 3306))

def get_db_schema():
    """获取数据库的表结构信息"""
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
            # 获取所有表信息
            cursor.execute("""
                SELECT TABLE_NAME 
                FROM INFORMATION_SCHEMA.TABLES 
                WHERE TABLE_SCHEMA = %s
            """, (DB_NAME,))
            tables = cursor.fetchall()
            
            # 获取每个表的列信息
            for table in tables:
                table_name = table[0]
                schema[table_name] = {}
                
                # 获取列信息
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
                    
                    # 记录主键
                    if column_key == 'PRI':
                        primary_keys[table_name] = column_name
            
            # 获取外键关系
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

def map_json_to_tables(json_data, schema, foreign_keys, primary_keys):
    """将JSON数据映射到相应的表结构"""
    # 识别主要实体对应的表
    # 假设最高级别的JSON对象对应于"bitcoin_block"表
    
    mapped_data = {}
    
    # 处理区块数据
    block_table = "bitcoin_block"
    if block_table in schema:
        block_data = {col: json_data.get(col, None) 
                     for col in schema[block_table] 
                     if col in json_data}
        mapped_data[block_table] = [block_data]
    
    # 处理交易数据
    tx_table = "transaction"
    if tx_table in schema and "tx" in json_data:
        mapped_data[tx_table] = []
        for tx in json_data["tx"]:
            tx_data = {col: tx.get(col, None) 
                      for col in schema[tx_table] 
                      if col in tx}
            # 添加与区块的关联
            tx_data["block_hash"] = json_data.get("hash", None)
            mapped_data[tx_table].append(tx_data)
            
            # 处理交易输入
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
                    
            # 处理交易输出
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

def insert_mapped_data(mapped_data, schema, foreign_keys, primary_keys):
    """将映射后的数据插入到数据库中"""
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
            # 按依赖关系顺序插入数据
            # 1. 首先插入区块数据
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
                    
                    # 保存区块hash作为外键引用
                    if "hash" in block:
                        inserted_ids["bitcoin_block"] = block["hash"]
                print(f"✅ 插入区块数据成功")
                
            # # 2. 插入交易数据
            # if "transaction" in mapped_data:
            #     for tx in mapped_data["transaction"]:
            #         # 确保有区块hash作为外键
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
                    
            #         # 保存交易ID作为外键引用
            #         if "txid" in tx:
            #             if "transaction" not in inserted_ids:
            #                 inserted_ids["transaction"] = {}
            #             inserted_ids["transaction"][tx["txid"]] = cursor.lastrowid
            #     print(f"✅ 插入交易数据成功")
                
            # # 3. 插入交易输入(vin)数据
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
                    
            #         # 插入见证数据(如果有)
            #         if "witness" in vin_raw and vin_raw["witness"]:
            #             for witness_data in vin_raw["witness"]:
            #                 sql = """
            #                 INSERT INTO vin_witness (vin_id, witness)
            #                 VALUES (%s, %s)
            #                 """
            #                 cursor.execute(sql, (vin_id, witness_data))
            #     print(f"✅ 插入交易输入数据成功")
                
            # # 4. 插入交易输出(vout)数据和相关的scriptPubKey
            # if "vout" in mapped_data:
            #     for vout_data, vout_raw in mapped_data["vout"]:
            #         columns = list(vout_data.keys())
            #         placeholders = ', '.join(['%s'] * len(columns))
            #         sql = f"""
            #         INSERT INTO vout ({', '.join(columns)})
            #         VALUES ({placeholders})
            #         """
            #         cursor.execute(sql, list(vout_data.values()))
            #         vout_id = cursor.lastrowid
                    
            #         # 处理scriptPubKey
            #         if "scriptPubKey" in vout_raw:
            #             script = vout_raw["scriptPubKey"]
            #             address = None
            #             if "address" in script:
            #                 address = script["address"]
            #             elif "addresses" in script and script["addresses"]:
            #                 address = script["addresses"][0]
                            
            #             sql = """
            #             INSERT INTO script_pubkey (vout_id, asm, description, hex, address, type)
            #             VALUES (%s, %s, %s, %s, %s, %s)
            #             """
            #             cursor.execute(sql, (
            #                 vout_id,
            #                 script.get("asm", ""),
            #                 script.get("desc", ""),
            #                 script.get("hex", ""),
            #                 address,
            #                 script.get("type", "")
            #             ))
            #     print(f"✅ 插入交易输出数据成功")
                
            conn.commit()
            print("✅ 所有数据插入成功")
            
    except Exception as e:
        conn.rollback()
        print(f"❌ 错误: {e}")
    finally:
        conn.close()

def auto_insert_block_data(json_file_path):
    """自动获取数据库结构并插入区块数据"""
    # 读取JSON文件
    with open(json_file_path, "r") as f:
        block_data = json.load(f)
    
    # 获取数据库结构
    print("🔍 获取数据库结构...")
    schema, foreign_keys, primary_keys = get_db_schema()
    print(f"✅ 获取到 {len(schema)} 个表的结构")
    
    # 映射JSON数据到表结构
    print("🔄 映射JSON数据到表结构...")
    mapped_data = map_json_to_tables(block_data, schema, foreign_keys, primary_keys)
    
    # 插入映射后的数据
    print("📥 插入数据到数据库...")
    insert_mapped_data(mapped_data, schema, foreign_keys, primary_keys)

if __name__ == "__main__":
    auto_insert_block_data("latest_block.json")