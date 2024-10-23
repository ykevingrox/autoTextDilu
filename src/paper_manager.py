import sqlite3
import os

class Paper:
    def __init__(self, title, abstract, url):
        self.title = title
        self.abstract = abstract
        self.url = url
        self.keywords = set()

    def add_keyword(self, keyword):
        self.keywords.add(keyword)

class PaperManager:
    def __init__(self, db_path='data/papers.db'):
        # 确保数据目录存在
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.create_table()
        self.update_table_structure()

    def create_table(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS papers
            (id INTEGER PRIMARY KEY, 
             title TEXT, 
             abstract TEXT, 
             url TEXT, 
             year INTEGER, 
             doi TEXT,
             pmid TEXT,
             pmcid TEXT,
             api_source TEXT,
             local_path TEXT)
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS keywords
            (paper_id INTEGER, 
             keyword TEXT,
             FOREIGN KEY(paper_id) REFERENCES papers(id))
        ''')
        self.conn.commit()

    def update_table_structure(self):
        # 由于我们不再单独存储 pdf_path，这个方法可以保持为空或删除
        pass

    def add_paper(self, paper, api_source, local_path=None):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO papers (title, abstract, url, year, doi, pmid, pmcid, api_source, local_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (paper.get('title', ''), 
              paper.get('abstract', ''), 
              paper.get('url', ''), 
              paper.get('year'), 
              paper.get('doi'), 
              paper.get('pmid'),
              paper.get('pmcid'),
              api_source, 
              local_path))
        paper_id = cursor.lastrowid
        self.conn.commit()
        return paper_id

    def add_keyword_to_paper(self, paper_id, keyword):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO keywords (paper_id, keyword)
            VALUES (?, ?)
        ''', (paper_id, keyword))
        self.conn.commit()

    def get_all_papers(self):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM papers')
        return cursor.fetchall()

    def get_paper_by_id(self, paper_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM papers WHERE id = ?', (paper_id,))
        return cursor.fetchone()

    def update_paper_local_path(self, paper_id, local_path):
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE papers SET local_path = ? WHERE id = ?
        ''', (local_path, paper_id))
        self.conn.commit()

    def get_papers_by_api_source(self, api_source):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM papers WHERE api_source = ?', (api_source,))
        return cursor.fetchall()

    def get_paper_keywords(self, paper_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT keyword FROM keywords WHERE paper_id = ?', (paper_id,))
        return [row[0] for row in cursor.fetchall()]

    def search_papers(self, query):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM papers 
            WHERE title LIKE ? OR abstract LIKE ?
        ''', (f'%{query}%', f'%{query}%'))
        return cursor.fetchall()

    def __del__(self):
        self.conn.close()
