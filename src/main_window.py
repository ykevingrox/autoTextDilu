from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLineEdit, QTableWidget, QLabel, 
                             QMessageBox, QComboBox, QTableWidgetItem, QHeaderView,
                             QDialog, QTextEdit, QProgressDialog)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from .paper_searcher import PaperSearcher
from .paper_manager import PaperManager
from .ai_processor import AIProcessor
from .database_viewer import DatabaseViewer
import logging
import os
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

class NotesDialog(QDialog):
    def __init__(self, parent=None, notes=''):
        super().__init__(parent)
        self.setWindowTitle("论文笔记")
        self.setGeometry(200, 200, 400, 300)

        layout = QVBoxLayout()
        self.notes_edit = QTextEdit()
        self.notes_edit.setPlainText(notes)
        layout.addWidget(self.notes_edit)

        buttons = QHBoxLayout()
        save_button = QPushButton("保存")
        save_button.clicked.connect(self.accept)
        cancel_button = QPushButton("取消")
        cancel_button.clicked.connect(self.reject)
        buttons.addWidget(save_button)
        buttons.addWidget(cancel_button)

        layout.addLayout(buttons)
        self.setLayout(layout)

    def get_notes(self):
        return self.notes_edit.toPlainText()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("学术助手")
        self.setGeometry(100, 100, 1000, 600)

        self.paper_searcher = PaperSearcher()
        self.paper_manager = PaperManager()
        self.papers = []
        self.max_results = 10  # 默认值

        # 加载环境变量
        load_dotenv()
        self.ai_processor = AIProcessor(os.getenv('DASHSCOPE_API_KEY'))

        self.setup_ui()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # API源选择
        api_layout = QHBoxLayout()
        api_label = QLabel("API源:")
        self.api_selector = QComboBox()
        self.api_selector.addItems(["Crossref", "PubMed", "PMC Open Access", "PubMed Recent"])
        self.time_range_selector = QComboBox()
        self.time_range_selector.addItems(["过去一周", "过去一个月"])
        self.time_range_selector.setVisible(False)  # 默认隐藏
        api_layout.addWidget(api_label)
        api_layout.addWidget(self.api_selector)
        api_layout.addWidget(self.time_range_selector)
        layout.addLayout(api_layout)

        # 连接 API 选择器的信号
        self.api_selector.currentTextChanged.connect(self.on_api_changed)

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
        self.paper_table.setColumnCount(10)  # 增加到10列，包括ID列
        self.paper_table.setHorizontalHeaderLabels(["标题", "作者", "年份", "引用次数", "API来源", "DOI", "ID", "笔记", "下载状态", "AI笔记"])
        self.paper_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.paper_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.paper_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.paper_table.setSortingEnabled(True)
        layout.addWidget(self.paper_table)

        # 下载按钮
        self.download_button = QPushButton("一键下载全部论文")
        self.download_button.clicked.connect(self.download_all_papers)
        layout.addWidget(self.download_button)

        # 添加笔记按钮
        self.notes_button = QPushButton("添加/编辑笔记")
        self.notes_button.clicked.connect(self.open_notes_dialog)
        layout.addWidget(self.notes_button)

        # 添加最大结果数选择
        max_results_layout = QHBoxLayout()
        max_results_label = QLabel("每次下载最大文献数量:")
        self.max_results_selector = QComboBox()
        self.max_results_selector.addItems([str(i) for i in range(1, 11)])
        self.max_results_selector.setCurrentText(str(self.max_results))
        self.max_results_selector.currentTextChanged.connect(self.update_max_results)
        max_results_layout.addWidget(max_results_label)
        max_results_layout.addWidget(self.max_results_selector)
        layout.addLayout(max_results_layout)

        # 添加AI分析按钮
        self.ai_button = QPushButton("AI分析论文")
        self.ai_button.clicked.connect(self.process_papers_with_ai)
        layout.addWidget(self.ai_button)

        # 添加查看AI笔记按钮
        self.view_ai_notes_button = QPushButton("查看AI笔记")
        self.view_ai_notes_button.clicked.connect(self.open_ai_notes_dialog)
        layout.addWidget(self.view_ai_notes_button)

        # 添加数据库浏览按钮
        self.db_viewer_button = QPushButton("浏览数据库")
        self.db_viewer_button.clicked.connect(self.open_database_viewer)
        layout.addWidget(self.db_viewer_button)

    def on_api_changed(self, text):
        # 当选择 "PubMed Recent" 时显示时间范围选择器
        self.time_range_selector.setVisible(text == "PubMed Recent")

    def update_max_results(self, value):
        self.max_results = int(value)
        logging.info(f"Updated max results to {self.max_results}")

    def search_papers(self):
        keywords = self.search_input.text()
        api_source = self.api_selector.currentText().lower()

        try:
            if api_source == 'pubmed recent':
                time_range = self.time_range_selector.currentText()
                if time_range == "过去一周":
                    new_papers = self.paper_searcher.get_latest_papers_pubmed(keywords, self.max_results, weeks=1)
                else:  # 过去一个月
                    new_papers = self.paper_searcher.get_latest_papers_pubmed(keywords, self.max_results, months=1)
            elif api_source == 'crossref':
                new_papers = self.paper_searcher.search_papers_crossref(keywords, self.start_year.text(), self.end_year.text(), self.max_results)
            elif api_source == 'pubmed':
                new_papers = self.paper_searcher.search_papers_pubmed(keywords, self.start_year.text(), self.end_year.text(), self.max_results)
            elif api_source == 'pmc open access':
                new_papers = self.paper_searcher.search_papers_pmc(keywords, self.start_year.text(), self.end_year.text(), self.max_results)

            if new_papers:
                for paper in new_papers:
                    paper_id = self.paper_manager.add_paper(paper, paper['api_source'])  # 使用 paper['api_source']
                    paper['id'] = paper_id
                    logging.info(f"Added paper to database: {paper['title']} ID: {paper_id}")

                self.papers = new_papers
                self.update_paper_table()
            else:
                QMessageBox.information(self, "搜索结果", "没有找到新的论文。")
        except Exception as e:
            logging.error(f"搜索论文时发生错误: {str(e)}")
            QMessageBox.warning(self, "搜索错误", f"搜索论文时发生错误: {str(e)}")

    def update_paper_table(self):
        self.paper_table.setRowCount(len(self.papers))
        for row, paper in enumerate(self.papers):
            self.paper_table.setItem(row, 0, QTableWidgetItem(paper.get('title', '')))
            self.paper_table.setItem(row, 1, QTableWidgetItem(', '.join(paper.get('authors', []))))
            self.paper_table.setItem(row, 2, QTableWidgetItem(str(paper.get('year', 'N/A'))))
            self.paper_table.setItem(row, 3, QTableWidgetItem(str(paper.get('citation_count', 'N/A'))))
            self.paper_table.setItem(row, 4, QTableWidgetItem(paper.get('api_source', '').upper()))
            self.paper_table.setItem(row, 5, QTableWidgetItem(paper.get('doi', 'N/A')))
            self.paper_table.setItem(row, 6, QTableWidgetItem(str(paper.get('id', 'N/A'))))  # 显示编辑过的DOI作为ID
            
            notes = self.paper_manager.get_paper_notes(paper['id'])
            has_notes = "有" if notes and notes.strip() else "无"
            self.paper_table.setItem(row, 7, QTableWidgetItem(has_notes))

            download_status = "已下载" if paper.get('downloaded', False) else "未下载"
            self.paper_table.setItem(row, 8, QTableWidgetItem(download_status))

            ai_notes = paper.get('ai_notes', '')
            ai_notes_status = "有" if ai_notes else "无"
            self.paper_table.setItem(row, 9, QTableWidgetItem(ai_notes_status))

        self.highlight_keywords(self.search_input.text())

    def download_all_papers(self):
        for paper in self.papers:
            api_source = paper['api_source']
            result = self.paper_searcher.download_or_get_abstract(paper, api_source)
            
            if result and result['type'] != 'error':
                paper['downloaded'] = True
                paper_id = paper.get('id')
                if paper_id:
                    self.paper_manager.update_paper_download_status(paper_id, True)
            else:
                paper['downloaded'] = False

        self.update_paper_table()
        QMessageBox.information(self, "下载完成", "所有论文下载尝试已完成")

    def clear_results(self):
        self.papers.clear()
        self.paper_table.setRowCount(0)
        logging.info("搜索结果已清空")

    def open_notes_dialog(self):
        selected_rows = self.paper_table.selectionModel().selectedRows()
        if selected_rows:
            row = selected_rows[0].row()
            paper = self.papers[row]
            paper_id = paper.get('id')
            if paper_id:
                current_notes = self.paper_manager.get_paper_notes(paper_id)
                dialog = NotesDialog(self, current_notes)
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    new_notes = dialog.get_notes()
                    self.paper_manager.update_paper_notes(paper_id, new_notes)
                    QMessageBox.information(self, "成功", "笔记已更新")
                    self.update_paper_table()  # 更新表格以反映笔记状态的变化
            else:
                QMessageBox.warning(self, "错误", "无法为未保存的论文添加笔记")
        else:
            QMessageBox.warning(self, "错误", "请先选择一篇论文")

    def highlight_keywords(self, keywords):
        if not keywords:
            return

        keywords = keywords.lower().split()
        for row in range(self.paper_table.rowCount()):
            for col in range(self.paper_table.columnCount()):
                item = self.paper_table.item(row, col)
                if item:
                    text = item.text().lower()
                    if any(keyword in text for keyword in keywords):
                        item.setBackground(QColor(255, 255, 0, 100))  # 浅黄色背景
                    else:
                        item.setBackground(QColor(255, 255, 255))  # 白色背景

    def process_papers_with_ai(self):
        logging.info("开始AI论文处理流程")
        
        # 检查是否有已下载的论文
        downloaded_papers = [p for p in self.papers if p.get('downloaded', False)]
        logging.info(f"找到 {len(downloaded_papers)} 篇已下载的论文")
        
        if not downloaded_papers:
            logging.warning("没有找到已下载的论文")
            QMessageBox.warning(self, "警告", "没有找到已下载的论文")
            return

        # 显示进度对话框
        progress = QProgressDialog("正在进行AI分析...", "取消", 0, len(downloaded_papers), self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.show()

        try:
            logging.info("开始调用AI处理器进行批量处理")
            # 批量处理论文
            results = self.ai_processor.batch_process_papers(downloaded_papers)
            logging.info(f"AI处理完成，获得 {len(results)} 个结果")
            
            # 更新数据库和表格
            for paper in downloaded_papers:
                paper_id = paper['id']
                logging.info(f"正在处理论文 ID: {paper_id}")
                
                if paper_id in results:
                    ai_notes = results[paper_id]
                    logging.info(f"更新论文AI笔记，ID: {paper_id}, 笔记长度: {len(ai_notes)}")
                    self.paper_manager.update_paper_ai_notes(paper_id, ai_notes)
                    paper['ai_notes'] = ai_notes
                else:
                    logging.warning(f"未找到论文的AI处理结果，ID: {paper_id}")
            
            # 更新表格显示
            logging.info("更新表格显示")
            self.update_paper_table()
            logging.info("AI���理流程完成")
            QMessageBox.information(self, "完成", "AI分析已完成")
            
        except Exception as e:
            error_msg = f"AI处理过程中发生错误: {str(e)}"
            logging.error(error_msg, exc_info=True)
            QMessageBox.warning(self, "错误", f"AI处理失败: {str(e)}")
        finally:
            progress.close()

    def open_ai_notes_dialog(self):
        selected_rows = self.paper_table.selectionModel().selectedRows()
        if selected_rows:
            row = selected_rows[0].row()
            paper = self.papers[row]
            paper_id = paper.get('id')
            if paper_id:
                ai_notes = self.paper_manager.get_paper_ai_notes(paper_id)
                if ai_notes:
                    dialog = NotesDialog(self, ai_notes)
                    dialog.setWindowTitle("AI笔记")
                    dialog.notes_edit.setReadOnly(True)  # AI笔记设为只读
                    dialog.exec()
                else:
                    QMessageBox.information(self, "提示", "该论文暂无AI笔记")
            else:
                QMessageBox.warning(self, "错误", "无法获取论文ID")
        else:
            QMessageBox.warning(self, "错误", "请先选择一篇论文")

    def open_database_viewer(self):
        """打开数据库浏览器窗口"""
        self.db_viewer = DatabaseViewer(self.paper_manager)
        self.db_viewer.show()
