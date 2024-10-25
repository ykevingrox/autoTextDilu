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
        sql_statement = '''
            CREATE TABLE IF NOT EXISTS papers
            (id INTEGER PRIMARY KEY, 
             title TEXT UNIQUE, 
             authors TEXT,
             year INTEGER, 
             doi TEXT UNIQUE,
             pmid TEXT,
             pmcid TEXT,
             api_source TEXT,
             citation_count INTEGER,
             notes TEXT,
             downloaded BOOLEAN DEFAULT FALSE)
        '''
        logging.info(f"Executing SQL: {sql_statement}")
        cursor.execute(sql_statement)
        
        self.conn.commit()

    def add_paper(self, paper, api_source):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO papers 
            (title, authors, year, doi, pmid, pmcid, api_source, citation_count, downloaded)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            paper.get('title', ''),
            ', '.join(paper.get('authors', [])),
            paper.get('year'),
            paper.get('doi', ''),  # 确保DOI被保存
            paper.get('pmid'),
            paper.get('pmcid'),
            api_source,
            paper.get('citation_count', 0),
            paper.get('downloaded', False)
        ))
        paper_id = cursor.lastrowid
        self.conn.commit()
        return paper_id

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

    def __del__(self):
        self.conn.close()
