# -*- coding: utf-8 -*-
"""
Migration 004: Reparse Hierarchy

Object: Re-parse all laws in the database using the new ArticleSplitter
to populate the `chapter_path` column with full hierarchy (Book > Part > Chapter > Section).
"""

import sqlite3
import sys
import logging
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from article_splitter import ArticleSplitter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "legal_database.db"

def run_migration():
    if not DB_PATH.exists():
        logger.error(f"Database not found: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    splitter = ArticleSplitter()

    try:
        # 0. Fix Triggers for Standalone FTS Table
        # The previous rebuild might have created triggers for external content table, 
        # but we created a standalone table. We need to fix them to avoid "SQL logic error".
        logger.info("Fixing FTS triggers for standalone table...")
        cursor.execute("DROP TRIGGER IF EXISTS law_articles_ai")
        cursor.execute("DROP TRIGGER IF EXISTS law_articles_ad")
        cursor.execute("DROP TRIGGER IF EXISTS law_articles_au")

        # Standalone FTS Triggers
        cursor.execute("""
            CREATE TRIGGER law_articles_ai AFTER INSERT ON law_articles BEGIN
                INSERT INTO law_articles_fts(rowid, content, article_number_str, chapter_path)
                VALUES (new.id, new.content, new.article_number_str, new.chapter_path);
            END
        """)
        cursor.execute("""
            CREATE TRIGGER law_articles_ad AFTER DELETE ON law_articles BEGIN
                DELETE FROM law_articles_fts WHERE rowid = old.id;
            END
        """)
        cursor.execute("""
            CREATE TRIGGER law_articles_au AFTER UPDATE ON law_articles BEGIN
                DELETE FROM law_articles_fts WHERE rowid = old.id;
                INSERT INTO law_articles_fts(rowid, content, article_number_str, chapter_path)
                VALUES (new.id, new.content, new.article_number_str, new.chapter_path);
            END
        """)
        conn.commit()
        logger.info("Triggers fixed.")

        # 1. Get all laws
        logger.info("Fetching all laws...")
        cursor.execute("SELECT id, title, content FROM laws WHERE status = '有效'")
        laws = cursor.fetchall()
        
        logger.info(f"Found {len(laws)} active laws to re-parse.")
        
        updated_count = 0
        
        for law_id, title, content in laws:
            logger.info(f"Processing: {title} (ID: {law_id})")
            
            # Reparse content
            articles = splitter.split_law(content)
            
            # Update each article's chapter_path in law_articles
            # We match by law_id and article_number_int
            
            for art in articles:
                path = art['chapter_path']
                art_num = art['article_number_int']
                
                if path:
                    cursor.execute("""
                        UPDATE law_articles 
                        SET chapter_path = ? 
                        WHERE law_id = ? AND article_number_int = ?
                    """, (path, law_id, art_num))
                    
            updated_count += len(articles)
            
        conn.commit()
        logger.info(f"Migration complete. Updated hierarchy for {updated_count} articles.")

        # Verify a few
        cursor.execute("""
            SELECT l.title, la.article_number_str, la.chapter_path 
            FROM law_articles la 
            JOIN laws l ON la.law_id = l.id 
            WHERE la.chapter_path IS NOT NULL AND la.chapter_path != '' 
            LIMIT 5
        """)
        logger.info("\nVerification Sample:")
        for row in cursor.fetchall():
            logger.info(f"  {row[0]} Art {row[1]}: {row[2]}")

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    run_migration()
