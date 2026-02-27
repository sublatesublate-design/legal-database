import os
import zipfile
import sqlite3
import shutil
from pathlib import Path
from docx import Document
import logging
from datetime import datetime
import re

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class LegalDataProcessor:
    def __init__(self, download_dir="downloads", db_path="legal_database.db"):
        self.download_dir = Path(download_dir)
        self.db_path = db_path
        self.temp_dir = Path("temp_processing")
        
    def setup_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS laws (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT,
                publish_date TEXT,
                category TEXT,
                status TEXT,
                file_name TEXT,
                is_amendment INTEGER DEFAULT 0,
                base_law_title TEXT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # 创建全文检索索引
        cursor.execute('CREATE VIRTUAL TABLE IF NOT EXISTS laws_fts USING fts5(title, content, content="laws", content_rowid="id")')
        
        # 数据库迁移: 添加新列 (如果不存在)
        try:
            cursor.execute("ALTER TABLE laws ADD COLUMN is_amendment INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass # 已存在
            
        try:
            cursor.execute("ALTER TABLE laws ADD COLUMN base_law_title TEXT")
        except sqlite3.OperationalError:
            pass # 已存在
            
        conn.commit()
        conn.close()

    def extract_docx_text(self, docx_path):
        """从DOCX中提取文字"""
        try:
            doc = Document(docx_path)
            full_text = []
            for para in doc.paragraphs:
                full_text.append(para.text)
            return '\n'.join(full_text)
        except Exception as e:
            logger.error(f"解析文档 {docx_path} 出错: {e}")
            return ""

    def process_zip(self, zip_path, category, status):
        """处理单个ZIP文件"""
        logger.info(f"正在处理 ZIP: {zip_path}")
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(self.temp_dir)
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            for docx_file in self.temp_dir.glob("*.docx"):
                # 解析文件名获取标题和日期 (例如: 中华人民共和国公司法_20231229.docx)
                match = re.match(r"(.+)_(\d{8})\.docx", docx_file.name)
                if match:
                    title = match.group(1)
                    publish_date = f"{match.group(2)[:4]}-{match.group(2)[4:6]}-{match.group(2)[6:]}"
                else:
                    title = docx_file.stem
                    publish_date = "Unknown"
                
                content = self.extract_docx_text(docx_file)
                
                # 检查是否已存在 (避免重复)
                cursor.execute("SELECT id FROM laws WHERE title=? AND publish_date=? AND category=?", 
                             (title, publish_date, category))
                existing = cursor.fetchone()
                
                # 识别修正案/修改决定
                is_amendment = 0
                base_law_title = None
                
                # 常见模式: 关于修改《XXX》的决定, XXX修正案(N)
                amend_patterns = [
                    r"关于修改《(.+)》的决定",
                    r"关于修改〈(.+)〉的决定",
                    r"(.+)修正案"
                ]
                for pattern in amend_patterns:
                    amend_match = re.search(pattern, title)
                    if amend_match:
                        is_amendment = 1
                        base_law_title = amend_match.group(1)
                        break

                if not existing:
                    cursor.execute('''
                        INSERT INTO laws (title, content, publish_date, category, status, file_name, is_amendment, base_law_title)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (title, content, publish_date, category, status, docx_file.name, is_amendment, base_law_title))
                    logger.info(f"已添加到数据库: {title} {'(修正案)' if is_amendment else ''}")
                else:
                    # 如果状态改变，可以更新
                    cursor.execute("UPDATE laws SET status=?, is_amendment=?, base_law_title=? WHERE id=?", 
                                 (status, is_amendment, base_law_title, existing[0]))
            
            conn.commit()
            # 更新FTS全文检索引索
            cursor.execute("INSERT INTO laws_fts(laws_fts) VALUES('rebuild')")
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"处理 ZIP {zip_path} 出错: {e}")
        finally:
            if self.temp_dir.exists():
                shutil.rmtree(self.temp_dir)

    def run(self):
        """遍历整个下载目录进行处理"""
        self.setup_db()
        
        # 遍历分类文件夹
        for category_dir in self.download_dir.iterdir():
            if not category_dir.is_dir():
                continue
            
            category = category_dir.name
            
            # 1. 处理直接在该分类下的文件 (默认为 "有效" 或是之前的测试文件)
            # 注意: 手动下载或者未指定状态的默认归为 "有效"
            for item in category_dir.iterdir():
                if item.is_file() and item.suffix == ".zip":
                    self.process_zip(item, category, "有效")
                
                # 2. 处理子文件夹 (对应的状态: 尚未生效, 已废止等)
                elif item.is_dir():
                    status = item.name
                    for zip_path in item.glob("*.zip"):
                        self.process_zip(zip_path, category, status)

        logger.info("数据同步完成！")

if __name__ == "__main__":
    processor = LegalDataProcessor()
    processor.run()
