import sqlite3
import os
import logging

class PaperManager:
    def __init__(self, db_path='data/papers.db'):
        # 确保数据目录存在
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.create_table()

    def create_table(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS papers
            (id TEXT PRIMARY KEY, 
             title TEXT, 
             authors TEXT,
             year INTEGER, 
             doi TEXT,
             pmid TEXT,
             pmcid TEXT,
             api_source TEXT,
             citation_count INTEGER,
             notes TEXT,
             downloaded BOOLEAN DEFAULT FALSE,
             ai_notes TEXT)
        ''')
        self.conn.commit()

    def add_paper(self, paper, api_source):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO papers 
            (id, title, authors, year, doi, pmid, pmcid, api_source, citation_count, downloaded)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            str(paper['id']),  # 确保 id 是字符串
            paper.get('title', ''),
            ', '.join(paper.get('authors', [])),
            paper.get('year'),
            paper.get('doi', ''),
            paper.get('pmid', ''),
            paper.get('pmcid', ''),
            api_source,
            paper.get('citation_count', 0),
            1 if paper.get('downloaded', False) else 0
        ))
        self.conn.commit()
        return paper['id']

    def update_paper_download_status(self, paper_id, downloaded):
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE papers SET downloaded = ? WHERE id = ?
        ''', (downloaded, paper_id))
        self.conn.commit()

    def get_all_papers(self):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM papers')
        return cursor.fetchall()

    def get_paper_by_id(self, paper_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM papers WHERE id = ?', (paper_id,))
        return cursor.fetchone()

    def get_papers_by_api_source(self, api_source):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM papers WHERE api_source = ?', (api_source,))
        return cursor.fetchall()

    def search_papers(self, query):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM papers 
            WHERE title LIKE ? OR authors LIKE ?
        ''', (f'%{query}%', f'%{query}%'))
        return cursor.fetchall()

    def update_paper_notes(self, paper_id, notes):
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE papers SET notes = ? WHERE id = ?
        ''', (notes, paper_id))
        self.conn.commit()

    def get_paper_notes(self, paper_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT notes FROM papers WHERE id = ?', (paper_id,))
        result = cursor.fetchone()
        return result[0] if result else ''

    def get_notes_status(self, paper_ids):
        cursor = self.conn.cursor()
        placeholders = ','.join('?' * len(paper_ids))
        cursor.execute(f'SELECT id, CASE WHEN notes != "" THEN 1 ELSE 0 END as has_notes FROM papers WHERE id IN ({placeholders})', paper_ids)
        return dict(cursor.fetchall())

    def update_paper_ai_notes(self, paper_id: str, ai_notes: str):
        """更新论文的AI笔记"""
        logging.info(f"开始更新论文AI笔记，ID: {paper_id}")
        try:
            # 直接使用 self.conn 而不是 get_db_connection
            cursor = self.conn.cursor()
            cursor.execute(
                "UPDATE papers SET ai_notes = ? WHERE id = ?",
                (ai_notes, paper_id)
            )
            self.conn.commit()
            logging.info(f"成功更新论文AI笔记，ID: {paper_id}, 影响行数: {cursor.rowcount}")
        except Exception as e:
            error_msg = f"更新AI笔记时发生错误: {str(e)}"
            logging.error(error_msg, exc_info=True)
            raise

    def __del__(self):
        self.conn.close()
