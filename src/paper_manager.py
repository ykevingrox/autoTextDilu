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

    def create_table(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS papers
            (id INTEGER PRIMARY KEY, title TEXT, abstract TEXT, url TEXT, year INTEGER, local_path TEXT)
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS keywords
            (paper_id INTEGER, keyword TEXT,
            FOREIGN KEY(paper_id) REFERENCES papers(id))
        ''')
        self.conn.commit()

    def add_paper(self, paper, local_path=None):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO papers (title, abstract, url, year, local_path)
            VALUES (?, ?, ?, ?, ?)
        ''', (paper['title'], paper['abstract'], paper['url'], paper['year'], local_path))
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

    def update_paper_local_path(self, paper_id, local_path):
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE papers SET local_path = ? WHERE id = ?
        ''', (local_path, paper_id))
        self.conn.commit()

    def __del__(self):
        self.conn.close()
