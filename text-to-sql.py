import os
import pymysql
from openai import OpenAI

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Default database connection parameters
DEFAULT_DB_CONFIG = {
    "host": os.getenv("DB_HOST", "db-bitcoin-info.ctoim6igklzt.us-east-2.rds.amazonaws.com"),
    "user": os.getenv("DB_USER", "admin"),
    "password": os.getenv("DB_PASSWORD", "db-bitcoin-info"),
    "database": os.getenv("DB_NAME", "bitcoin"),
    "port": int(os.getenv("DB_PORT", "3306"))
}

def extract_schema(db_config=DEFAULT_DB_CONFIG):
    """Extract schema from MySQL database"""
    conn = pymysql.connect(
        host=db_config["host"],
        user=db_config["user"],
        password=db_config["password"],
        database=db_config["database"],
        port=db_config["port"],
        connect_timeout=10
    )
    
    schema = []
    
    try:
        with conn.cursor() as cursor:
            # Get all table names
            cursor.execute("""
                SELECT TABLE_NAME 
                FROM INFORMATION_SCHEMA.TABLES 
                WHERE TABLE_SCHEMA = %s AND TABLE_TYPE = 'BASE TABLE'
            """, (db_config["database"],))
            tables = cursor.fetchall()
            
            if not tables:
                print(f"Warning: No tables found in database {db_config['database']}")
                return "No tables found"
                
            # Generate CREATE statement for each table
            for table in tables:
                table_name = table[0]
                
                # Get column information
                cursor.execute("""
                    SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_KEY, COLUMN_DEFAULT, 
                           CHARACTER_MAXIMUM_LENGTH, NUMERIC_PRECISION, NUMERIC_SCALE
                    FROM INFORMATION_SCHEMA.COLUMNS 
                    WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
                    ORDER BY ORDINAL_POSITION
                """, (db_config["database"], table_name))
                
                columns = cursor.fetchall()
                create_stmt = f"CREATE TABLE {table_name} (\n"
                
                for i, col in enumerate(columns):
                    column_name, data_type, is_nullable, column_key, default, char_max_len, num_precision, num_scale = col
                    
                    # Data type mapping (keep MySQL types for better GPT understanding)
                    column_type = data_type.lower()
                    
                    # Add length information (if available)
                    if char_max_len and column_type in ('varchar', 'char'):
                        column_type += f"({char_max_len})"
                    elif num_precision and column_type in ('decimal', 'numeric'):
                        column_type += f"({num_precision},{num_scale or 0})"
                    
                    create_stmt += f"    {column_name} {column_type}"
                    
                    if column_key == 'PRI':
                        create_stmt += " PRIMARY KEY"
                    if is_nullable == 'NO':
                        create_stmt += " NOT NULL"
                    if default is not None:
                        if default == "CURRENT_TIMESTAMP":
                            create_stmt += f" DEFAULT {default}"
                        elif column_type in ('char', 'varchar', 'text', 'date', 'datetime'):
                            create_stmt += f" DEFAULT '{default}'"
                        else:
                            create_stmt += f" DEFAULT {default}"
                        
                    if i < len(columns) - 1:
                        create_stmt += ",\n"
                
                # Get foreign key relationships
                cursor.execute("""
                    SELECT COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
                    FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
                    WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND REFERENCED_TABLE_NAME IS NOT NULL
                """, (db_config["database"], table_name))
                
                fks = cursor.fetchall()
                if fks:
                    for i, fk in enumerate(fks):
                        col_name, ref_table, ref_col = fk
                        if i == 0 and columns:
                            create_stmt += ",\n"
                        create_stmt += f"    FOREIGN KEY ({col_name}) REFERENCES {ref_table}({ref_col})"
                        if i < len(fks) - 1:
                            create_stmt += ",\n"
                
                create_stmt += "\n);"
                schema.append(create_stmt)
    except Exception as e:
        print(f"Error extracting MySQL schema: {e}")
        return f"Error: {str(e)}"
    finally:
        conn.close()
    
    return "\n\n".join(schema)

def execute_sql(sql, db_config=DEFAULT_DB_CONFIG):
    """Execute SQL query on MySQL database"""
    conn = pymysql.connect(
        host=db_config["host"],
        user=db_config["user"],
        password=db_config["password"],
        database=db_config["database"],
        port=db_config["port"],
        cursorclass=pymysql.cursors.DictCursor
    )
    
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql)
            result = cursor.fetchall()
            return list(result) if result else "Query returned no results"
    except Exception as e:
        return f"SQL execution error: {str(e)}"
    finally:
        conn.close()

def text_to_sql(nlq, db_config=DEFAULT_DB_CONFIG):
    """Convert natural language query to SQL query"""
    # Get database schema
    db_schema = extract_schema(db_config)
    
    # Build system prompt
    SYSTEM_PROMPT = f"""You are a SQL developer that is expert in Bitcoin and you answer natural language questions about the Bitcoin database in MySQL.
You always only respond with SQL statements that are correct for MySQL 8.0.
The schema of the Bitcoin database is the following:

{db_schema}

Guidelines:
1. Only give me the SQL. Do not explain.
2. Do not include any ticks like \"\"\" or ```.
3. Your SQL must be compatible with MySQL 8.0.
4. Use appropriate JOINs when needed.
5. Be precise and accurate.
6. When counting total blocks, use MAX(height) + 1 instead of COUNT(*), as height starts from 0 and some blocks might be missing from the database.
7. For questions about blockchain data, remember that:
   a. Block height starts from 0 (genesis block)
   b. The database may contain incomplete block history
   c. Transaction volume refers to the number of transactions, not the BTC amount
   d. Time in blocks is stored as Unix timestamp
8. Pay careful attention to which table contains which fields:
   a. Time fields (time, mediantime) are in the bitcoin_block table, not in the transaction table
   b. Transaction count (nTx) is stored directly in the bitcoin_block table
   c. When joining tables, always check foreign key relationships (transaction.block_hash references bitcoin_block.hash)
   d. For time-based queries, remember to use the appropriate timestamp columns from the correct table
9. For complex queries requiring timestamp operations:
   a. The 'time' field in bitcoin_block is a Unix timestamp (seconds since epoch)
   b. Use UNIX_TIMESTAMP() for current time comparisons
   c. For time intervals, subtract the appropriate number of seconds (e.g., 3600 for 1 hour, 86400 for 1 day)
"""
    
    # Call OpenAI API
    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": nlq}
        ]
    )
    
    # Extract SQL query
    sql = completion.choices[0].message.content
    return sql

def format_result_for_humans(result):
    """Format query results to be more human-readable"""
    # If result is already a string, return as is
    if isinstance(result, str):
        return result
        
    # If result is an empty list
    if not result:
        return "No data found"
        
    # If result is a list with a single dictionary that has only one key-value pair
    if (isinstance(result, list) and len(result) == 1 and 
            isinstance(result[0], dict) and len(result[0]) == 1):
        # Return just the value
        return list(result[0].values())[0]
        
    # If result is a list with multiple items but all have same single key
    if (isinstance(result, list) and all(isinstance(item, dict) and len(item) == 1 for item in result)):
        # Check if all dictionaries have the same key
        keys = [list(item.keys())[0] for item in result]
        if all(key == keys[0] for key in keys):
            # Return list of values
            return [item[keys[0]] for item in result]
    
    # For all other cases return as is
    return result

def natural_query_to_answer(query, db_config=DEFAULT_DB_CONFIG):
    """Convert natural language query to answer"""
    # Convert natural language query to SQL query
    sql = text_to_sql(query, db_config)
    print(f"Generated SQL: {sql}")
    
    # Execute SQL query and return results
    raw_result = execute_sql(sql, db_config)
    
    # Format result for human readability
    formatted_result = format_result_for_humans(raw_result)
    return formatted_result

# Example usage
if __name__ == "__main__":
    # Example query
    # query = "What is the total number of blocks in the database?"
    # # query = "What is the latest block hash?"
    
    # # Execute query
    # result = natural_query_to_answer(query)
    # print(f"❓Query: {query}")
    # print(f"💡Result: {result}")
    
    print("🔍 Bitcoin Database Query Tool")
    print("💡 Enter natural language questions about the Bitcoin database")
    print("⚠️  First query may take longer as it needs to load the database schema")
    print("❌ Type 'exit', 'quit' or 'q' to exit the program")
    print("=" * 50)
    
    try:
        while True:
            # Get user input
            query = input("\n🤔 Enter your question: ")
            
            # Check for exit commands
            if query.lower() in ['exit', 'quit', 'q']:
                print("👋 Thanks for using the tool. Goodbye!")
                break
                
            # Skip empty inputs
            if not query.strip():
                print("⚠️  Please enter a valid question")
                continue
                
            print("⏳ Processing query...")
            
            try:
                # Execute the query
                result = natural_query_to_answer(query)
                
                # Display results
                print("\n💡 Query Result:")
                print("-" * 50)
                print(result)
                print("-" * 50)
            except Exception as e:
                print(f"❌ Error processing query: {str(e)}")
    except KeyboardInterrupt:
        print("\n👋 Program interrupted by user. Goodbye!")
    except Exception as e:
        print(f"❌ Error: {str(e)}")