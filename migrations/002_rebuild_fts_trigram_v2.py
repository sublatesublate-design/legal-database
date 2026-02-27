import sqlite3
import sys

# Force utf-8 output
sys.stdout.reconfigure(encoding='utf-8')

DB_PATH = "c:\\Users\\24812\\Desktop\\legal-database\\legal_database.db"
TEST_DB_PATH = "c:\\Users\\24812\\Desktop\\legal-database\\test_trigram.db"

def check_trigram_file():
    print("Checking trigram on file-based DB...")
    with sqlite3.connect(TEST_DB_PATH) as conn:
        try:
            conn.execute("CREATE VIRTUAL TABLE t USING fts5(content, tokenize='trigram')")
            print("Trigram tokenizer is SUPPORTED on file DB.")
        except Exception as e:
            print(f"Trigram tokenizer is NOT SUPPORTED on file DB: {e}")

def migrate():
    print(f"Migrating database at {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # 1. Drop existing FTS tables
        print("Dropping existing laws_fts...")
        cursor.execute("DROP TABLE IF EXISTS laws_fts")
        
        print("Dropping existing articles_fts...")
        cursor.execute("DROP TABLE IF EXISTS articles_fts")
        
        # 2. Recreate laws_fts with trigram tokenizer
        print("Recreating laws_fts with trigram tokenizer...")
        cursor.execute("""
            CREATE VIRTUAL TABLE laws_fts USING fts5(
                title,
                full_text,
                content='laws',
                content_rowid='id',
                tokenize='trigram'
            )
        """)
        print("laws_fts created.")

        # 3. Rebuild laws_fts index
        print("Rebuilding laws_fts index...")
        cursor.execute("INSERT INTO laws_fts(laws_fts) VALUES('rebuild')")
        print("laws_fts index rebuilt.")
        
        # 4. Recreate articles_fts with trigram tokenizer
        print("Recreating articles_fts with trigram tokenizer...")
        cursor.execute("""
            CREATE VIRTUAL TABLE articles_fts USING fts5(
                article_number,
                content,
                content='articles',
                content_rowid='id',
                tokenize='trigram'
            )
        """)
        print("articles_fts created.")
        
        # 5. Rebuild articles_fts index
        print("Rebuilding articles_fts index...")
        cursor.execute("INSERT INTO articles_fts(articles_fts) VALUES('rebuild')")
        print("articles_fts index rebuilt.")
        
        conn.commit()
        print("Migration successful!")
        
    except Exception as e:
        print(f"Migration failed at step: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    try:
        check_trigram_file()
        migrate()
    except Exception as e:
        print(f"Script failed: {e}")
