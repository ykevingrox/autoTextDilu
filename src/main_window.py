from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLineEdit, QListWidget, QLabel, 
                             QMessageBox, QComboBox)
from PyQt6.QtCore import Qt
from .paper_searcher import PaperSearcher
from .paper_manager import PaperManager
from datetime import datetime
import logging

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("学术助手")
        self.setGeometry(100, 100, 800, 600)

        self.paper_searcher = PaperSearcher()
        self.paper_manager = PaperManager()

        self.setup_ui()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # API源选择
        api_layout = QHBoxLayout()
        api_label = QLabel("API源:")
        self.api_selector = QComboBox()
        self.api_selector.addItems(["Crossref", "PubMed", "PMC Open Access"])
        api_layout.addWidget(api_label)
        api_layout.addWidget(self.api_selector)
        layout.addLayout(api_layout)

        # 搜索部分
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        search_button = QPushButton("搜索")
        search_button.clicked.connect(self.search_papers)
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(search_button)
        layout.addLayout(search_layout)

        # 年份筛选
        filter_layout = QHBoxLayout()
        self.start_year = QLineEdit()
        self.end_year = QLineEdit()
        filter_layout.addWidget(QLabel("开始年份:"))
        filter_layout.addWidget(self.start_year)
        filter_layout.addWidget(QLabel("结束年份:"))
        filter_layout.addWidget(self.end_year)
        layout.addLayout(filter_layout)

        # 论文列表
        self.paper_list = QListWidget()
        layout.addWidget(self.paper_list)

        # 下载按钮
        self.download_button = QPushButton("下载论文")
        self.download_button.clicked.connect(self.download_paper)
        layout.addWidget(self.download_button)

    def search_papers(self):
        keywords = self.search_input.text()
        start_year = self.start_year.text()
        end_year = self.end_year.text()
        api_source = self.api_selector.currentText().lower()

        if api_source == 'crossref':
            self.papers = self.paper_searcher.search_papers_crossref(keywords, start_year, end_year)
        elif api_source == 'pubmed':
            self.papers = self.paper_searcher.search_papers_pubmed(keywords, start_year, end_year)
        elif api_source == 'pmc open access':
            self.papers = self.paper_searcher.search_papers_pmc(keywords, start_year, end_year)

        self.paper_list.clear()
        for paper in self.papers:
            self.paper_list.addItem(f"{paper['title']} ({paper.get('year', 'N/A')})")

    def download_paper(self):
        selected_items = self.paper_list.selectedItems()
        if selected_items:
            paper_index = self.paper_list.row(selected_items[0])
            paper = self.papers[paper_index]
            api_source = self.api_selector.currentText().lower()
            if api_source == 'pmc open access':
                api_source = 'pmc'  # 调整为与 PaperSearcher 中的方法名匹配
            
            logging.info(f"Attempting to download paper: {paper.get('title', 'Unknown Title')}")
            result = self.paper_searcher.download_or_get_abstract(paper, api_source)
            
            if result:
                paper_data = {
                    'title': paper.get('title', ''),
                    'abstract': paper.get('abstract', ''),
                    'url': paper.get('url', ''),
                    'year': paper.get('year'),
                    'doi': paper.get('doi'),
                    'pmid': paper.get('pmid'),
                    'pmcid': paper.get('pmcid')
                }
                if result['type'] == 'both':
                    paper_id = self.paper_manager.add_paper(paper_data, api_source, result['abstract_path'])
                    self.paper_manager.update_paper_pdf_path(paper_id, result['pdf_path'])
                    message = f"论文摘要已保存到: {result['abstract_path']}\nPDF已保存到: {result['pdf_path']}"
                else:
                    paper_id = self.paper_manager.add_paper(paper_data, api_source, result['path'])
                    message = f"论文摘要已保存到: {result['path']}"
                logging.info(message)
                QMessageBox.information(self, "操作成功", message)
            else:
                error_message = "无法获取摘要或PDF，请检查控制台输出以获取更多信息"
                logging.error(error_message)
                QMessageBox.warning(self, "操作失败", error_message)
        else:
            logging.warning("No paper selected for download")
