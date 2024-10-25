from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QTableWidget, 
                           QTableWidgetItem, QHeaderView, QPushButton, QHBoxLayout,
                           QDialog, QTextEdit, QMessageBox)
from PyQt6.QtCore import Qt
import logging

class NotesDialog(QDialog):
    def __init__(self, parent=None, notes='', title="笔记"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setGeometry(200, 200, 600, 400)

        layout = QVBoxLayout()
        self.notes_edit = QTextEdit()
        self.notes_edit.setPlainText(notes)
        self.notes_edit.setReadOnly(True)
        layout.addWidget(self.notes_edit)

        self.setLayout(layout)

class DatabaseViewer(QMainWindow):
    def __init__(self, paper_manager):
        super().__init__()
        self.paper_manager = paper_manager
        self.setup_ui()
        self.load_papers()

    def setup_ui(self):
        self.setWindowTitle("数据库浏览器")
        self.setGeometry(100, 100, 1200, 800)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # 创建表格
        self.paper_table = QTableWidget()
        self.paper_table.setColumnCount(11)
        self.paper_table.setHorizontalHeaderLabels([
            "ID", "标题", "作者", "年份", "引用次数", 
            "API来源", "DOI", "下载状态", "笔记", "AI笔记", "操作"
        ])
        self.paper_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.paper_table)

        # 按钮区域
        button_layout = QHBoxLayout()
        refresh_button = QPushButton("刷新")
        refresh_button.clicked.connect(self.load_papers)
        button_layout.addWidget(refresh_button)
        layout.addLayout(button_layout)

    def load_papers(self):
        # 从数据库获取所有论文
        papers = self.paper_manager.get_all_papers()
        self.paper_table.setRowCount(len(papers))

        for row, paper in enumerate(papers):
            # ID
            self.paper_table.setItem(row, 0, QTableWidgetItem(str(paper['id'])))
            # 标题
            self.paper_table.setItem(row, 1, QTableWidgetItem(paper['title']))
            # 作者
            self.paper_table.setItem(row, 2, QTableWidgetItem(paper['authors']))
            # 年份
            self.paper_table.setItem(row, 3, QTableWidgetItem(str(paper['year'])))
            # 引用次数
            self.paper_table.setItem(row, 4, QTableWidgetItem(str(paper['citation_count'])))
            # API来源
            self.paper_table.setItem(row, 5, QTableWidgetItem(paper['api_source']))
            # DOI
            self.paper_table.setItem(row, 6, QTableWidgetItem(paper['doi']))
            # 下载状态
            download_status = "已下载" if paper['downloaded'] else "未下载"
            self.paper_table.setItem(row, 7, QTableWidgetItem(download_status))
            
            # 笔记状态
            notes_status = "有" if paper['notes'] else "无"
            notes_button = QPushButton(notes_status)
            notes_button.clicked.connect(lambda checked, p=paper: self.view_notes(p))
            self.paper_table.setCellWidget(row, 8, notes_button)
            
            # AI笔记状态
            ai_notes_status = "有" if paper['ai_notes'] else "无"
            ai_notes_button = QPushButton(ai_notes_status)
            ai_notes_button.clicked.connect(lambda checked, p=paper: self.view_ai_notes(p))
            self.paper_table.setCellWidget(row, 9, ai_notes_button)

            # 删除按钮
            delete_button = QPushButton("删除")
            delete_button.clicked.connect(lambda checked, p=paper: self.delete_paper(p))
            self.paper_table.setCellWidget(row, 10, delete_button)

    def view_notes(self, paper):
        if paper['notes']:
            dialog = NotesDialog(self, paper['notes'], "论文笔记")
            dialog.exec()
        else:
            QMessageBox.information(self, "提示", "该论文暂无笔记")

    def view_ai_notes(self, paper):
        if paper['ai_notes']:
            dialog = NotesDialog(self, paper['ai_notes'], "AI笔记")
            dialog.exec()
        else:
            QMessageBox.information(self, "提示", "该论文暂无AI笔记")

    def delete_paper(self, paper):
        reply = QMessageBox.question(self, '确认删除', 
                                   f"确定要删除论文 '{paper['title']}' 吗？",
                                   QMessageBox.StandardButton.Yes | 
                                   QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.paper_manager.delete_paper(paper['id'])
                self.load_papers()  # 重新加载数据
                QMessageBox.information(self, "成功", "论文已删除")
            except Exception as e:
                QMessageBox.warning(self, "错误", f"删除失败: {str(e)}")
