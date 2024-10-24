from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLineEdit, QTableWidget, QLabel, 
                             QMessageBox, QComboBox, QTableWidgetItem, QHeaderView)
from PyQt6.QtCore import Qt, QSortFilterProxyModel
from PyQt6.QtGui import QColor
from .paper_searcher import PaperSearcher
from .paper_manager import PaperManager
import logging

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("学术助手")
        self.setGeometry(100, 100, 1000, 600)

        self.paper_searcher = PaperSearcher()
        self.paper_manager = PaperManager()
        self.papers = []

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
        clear_button = QPushButton("清空结果")
        clear_button.clicked.connect(self.clear_results)
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(search_button)
        search_layout.addWidget(clear_button)
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

        # 论文表格
        self.paper_table = QTableWidget()
        self.paper_table.setColumnCount(5)
        self.paper_table.setHorizontalHeaderLabels(["标题", "作者", "年份", "引用次数", "API来源"])
        self.paper_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.paper_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.paper_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.paper_table.setSortingEnabled(True)
        layout.addWidget(self.paper_table)

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
            new_papers = self.paper_searcher.search_papers_crossref(keywords, start_year, end_year)
        elif api_source == 'pubmed':
            new_papers = self.paper_searcher.search_papers_pubmed(keywords, start_year, end_year)
        elif api_source == 'pmc open access':
            new_papers = self.paper_searcher.search_papers_pmc(keywords, start_year, end_year)

        for paper in new_papers:
            paper['api_source'] = api_source

        self.papers.extend(new_papers)
        self.update_paper_table()

    def update_paper_table(self):
        self.paper_table.setRowCount(len(self.papers))
        for row, paper in enumerate(self.papers):
            self.paper_table.setItem(row, 0, QTableWidgetItem(paper.get('title', '')))
            self.paper_table.setItem(row, 1, QTableWidgetItem(', '.join(paper.get('authors', []))))
            self.paper_table.setItem(row, 2, QTableWidgetItem(str(paper.get('year', ''))))
            self.paper_table.setItem(row, 3, QTableWidgetItem(str(paper.get('citation_count', 'N/A'))))
            self.paper_table.setItem(row, 4, QTableWidgetItem(paper.get('api_source', '').upper()))

    def download_paper(self):
        selected_items = self.paper_table.selectedItems()
        if selected_items:
            row = self.paper_table.row(selected_items[0])
            paper = self.papers[row]
            api_source = paper['api_source']
            if api_source == 'pmc open access':
                api_source = 'pmc'  # 调整为与 PaperSearcher 中的方法名匹配
            
            logging.info(f"Attempting to download paper: {paper.get('title', 'Unknown Title')}")
            result = self.paper_searcher.download_or_get_abstract(paper, api_source)
            
            if result:
                if result['type'] == 'error':
                    error_message = f"下载失败: {result['message']}"
                    logging.error(error_message)
                    QMessageBox.warning(self, "操作失败", error_message)
                else:
                    paper_data = {
                        'title': paper.get('title', ''),
                        'abstract': paper.get('abstract', ''),
                        'url': paper.get('url', ''),
                        'year': paper.get('year'),
                        'doi': paper.get('doi'),
                        'pmid': paper.get('pmid'),
                        'pmcid': paper.get('pmcid')
                    }
                    paper_id = self.paper_manager.add_paper(paper_data, api_source, result['path'])
                    message = f"{'PDF' if result['type'] == 'pdf' else '论文摘要'}已保存到: {result['path']}"
                    logging.info(message)
                    QMessageBox.information(self, "操作成功", message)
            else:
                error_message = "无法获取PDF或摘要，请检查控制台输出以获取更多信息"
                logging.error(error_message)
                QMessageBox.warning(self, "操作失败", error_message)
        else:
            logging.warning("No paper selected for download")

    def clear_results(self):
        self.papers.clear()
        self.paper_table.setRowCount(0)
        logging.info("搜索结果已清空")
