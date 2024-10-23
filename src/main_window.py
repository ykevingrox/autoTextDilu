from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLineEdit, QListWidget, QLabel, 
                             QMessageBox, QComboBox)
from PyQt6.QtCore import Qt
from .paper_searcher import PaperSearcher
from .paper_manager import PaperManager, Paper
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
        self.start_year = QComboBox()
        self.end_year = QComboBox()
        current_year = datetime.now().year
        years = [str(year) for year in range(current_year, current_year - 50, -1)]
        self.start_year.addItems(years)
        self.end_year.addItems(years)
        filter_layout.addWidget(QLabel("开始年份:"))
        filter_layout.addWidget(self.start_year)
        filter_layout.addWidget(QLabel("结束年份:"))
        filter_layout.addWidget(self.end_year)
        layout.addLayout(filter_layout)

        # 论文列表
        self.paper_list = QListWidget()
        layout.addWidget(self.paper_list)

        # 关键词部分
        keyword_layout = QHBoxLayout()
        self.keyword_input = QLineEdit()
        add_keyword_button = QPushButton("添加关键词")
        add_keyword_button.clicked.connect(self.add_keyword)
        keyword_layout.addWidget(self.keyword_input)
        keyword_layout.addWidget(add_keyword_button)
        layout.addLayout(keyword_layout)

        # 下载按钮
        self.download_button = QPushButton("下载论文")
        self.download_button.clicked.connect(self.download_paper)
        layout.addWidget(self.download_button)

    def search_papers(self):
        keywords = self.search_input.text()
        start_year = int(self.start_year.currentText())
        end_year = int(self.end_year.currentText())
        self.papers = self.paper_searcher.search_papers(keywords, start_year, end_year)
        self.paper_list.clear()
        for paper in self.papers:
            self.paper_list.addItem(f"{paper['title']} ({paper['year']})")

    def add_keyword(self):
        selected_items = self.paper_list.selectedItems()
        if selected_items:
            paper_index = self.paper_list.row(selected_items[0])
            keyword = self.keyword_input.text()
            self.paper_manager.add_keyword_to_paper(paper_index, keyword)
            self.keyword_input.clear()

    def download_paper(self):
        selected_items = self.paper_list.selectedItems()
        if selected_items:
            paper_index = self.paper_list.row(selected_items[0])
            paper = self.papers[paper_index]
            result = self.paper_searcher.download_or_get_abstract(paper['doi'], paper['title'])
            if result:
                if result['type'] == 'pdf':
                    message = f"论文PDF已下载到: {result['path']}"
                else:
                    message = f"论文摘要已保存到: {result['path']}"
                paper_id = self.paper_manager.add_paper(paper, result['path'])
                self.paper_manager.update_paper_local_path(paper_id, result['path'])
                QMessageBox.information(self, "操作成功", message)
            else:
                QMessageBox.warning(self, "操作失败", "无法下载论文或获取摘要，请检查控制台输出以获取更多信息")
