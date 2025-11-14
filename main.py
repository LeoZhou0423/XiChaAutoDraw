import os
import sys
import argparse

# 获取应用程序路径
base_path = os.path.dirname(os.path.abspath(__file__))
if hasattr(sys, '_MEIPASS'):
    base_path = sys._MEIPASS

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFileDialog,
    QProgressBar, QMessageBox, QGroupBox, QFrame
)
from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtCore import Qt, QThread, pyqtSignal
import threading
from src import draw_image
import sys
import os
# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from src import window_detection


class DrawingThread(QThread):
    """绘制任务线程，用于在后台执行绘制操作"""
    progress_signal = pyqtSignal(int)  # 进度信号
    finished_signal = pyqtSignal(bool, str)  # 完成信号

    def __init__(self, image_path):
        super().__init__()
        self.image_path = image_path
        self.is_running = True

    def run(self):
        """线程运行函数"""
        try:
            # 构造命令行参数并执行绘制
            sys.argv = ["main.py", "-i", self.image_path, "-m", "draw"]
            draw_image.main()

            self.finished_signal.emit(True, "绘制完成！")
        except Exception as e:
            self.finished_signal.emit(False, f"绘制过程中发生错误: {str(e)}")

    def stop(self):
        """停止线程"""
        self.is_running = False
        self.terminate()


class DrawingApp(QMainWindow):
    """喜茶绘图工具主窗口"""

    def __init__(self):
        super().__init__()
        self.init_ui()
        self.drawing_thread = None

    def init_ui(self):
        """初始化界面"""
        # 设置窗口属性
        self.setWindowTitle("喜贴绘制")
        self.setGeometry(100, 100, 600, 400)
        self.setMinimumSize(400, 300)
        # 设置窗口图标
        self.setWindowIcon(QIcon(os.path.join(base_path, "logo.png")))

        # 创建中心组件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 创建主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # 标题区域
        title_label = QLabel("喜贴绘制工具")
        title_label.setFont(QFont("Arial", 24, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)
        # 创建设置区域
        settings_group = QGroupBox("绘制设置")
        settings_layout = QVBoxLayout(settings_group)
        settings_layout.setSpacing(15)

        # 图片选择
        image_layout = QHBoxLayout()
        self.image_path_label = QLabel("未选择图片")
        self.image_path_label.setFrameShape(QFrame.StyledPanel)
        self.image_path_label.setFixedHeight(30)
        self.image_path_label.setAlignment(Qt.AlignCenter)
        image_layout.addWidget(self.image_path_label, 4)

        self.select_image_btn = QPushButton("选择图片")
        self.select_image_btn.setFont(QFont("Arial", 12))
        self.select_image_btn.clicked.connect(self.select_image)
        image_layout.addWidget(self.select_image_btn, 1)
        settings_layout.addLayout(image_layout)

        main_layout.addWidget(settings_group)

        # 开始按钮
        self.start_btn = QPushButton("开始绘制")
        self.start_btn.setFont(QFont("Arial", 14, QFont.Bold))
        self.start_btn.setFixedHeight(40)
        self.start_btn.clicked.connect(self.start_drawing)
        main_layout.addWidget(self.start_btn)

        # 移除了进度条

        # 初始状态
        self.selected_image = None

    def select_image(self):
        """选择图片文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择图像文件", "./input", 
            "图像文件 (*.png *.jpg *.jpeg *.bmp *.gif)"
        )
        if file_path:
            self.selected_image = file_path
            self.image_path_label.setText(os.path.basename(file_path))

    def start_drawing(self):
        """开始绘制"""
        if not self.selected_image:
            QMessageBox.warning(self, "警告", "请先选择要绘制的图片！")
            return

        # 开始绘制（无确认弹窗）
        self.start_btn.setEnabled(False)
        self.select_image_btn.setEnabled(False)

        # 首先执行窗口检测
        try:
            print("🔍 正在执行窗口检测...")
            window_detection.main()
            print("✅ 窗口检测完成！")
        except Exception as e:
            self.start_btn.setEnabled(True)
            self.select_image_btn.setEnabled(True)
            QMessageBox.critical(self, "错误", f"窗口检测失败: {str(e)}")
            return

        # 启动绘制线程
        self.drawing_thread = DrawingThread(self.selected_image)
        # 移除了进度条信号连接
        self.drawing_thread.finished_signal.connect(self.drawing_finished)
        self.drawing_thread.start()
        
        # 隐藏窗口
        self.hide()

    # 移除了进度条更新函数
    # def update_progress(self, value):
    #     """更新进度条"""
    #     self.progress_bar.setValue(value)

    def drawing_finished(self, success, message):
        """绘制完成处理（无弹窗）"""
        # 直接打印结果信息
        if success:
            print(f"✅ {message}")
        else:
            print(f"❌ {message}")

        # 恢复界面状态
        self.start_btn.setEnabled(True)
        self.select_image_btn.setEnabled(True)
        
        # 重新显示窗口
        self.show()

    def closeEvent(self, event):
        """窗口关闭事件"""
        if self.drawing_thread and self.drawing_thread.isRunning():
            reply = QMessageBox.question(
                self, "确认关闭", 
                "绘制正在进行中，确定要关闭程序吗？",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.drawing_thread.stop()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


def main():
    """主函数"""
    app = QApplication(sys.argv)
    # 设置应用程序图标（同时修改窗口标题栏和任务栏图标）
    app.setWindowIcon(QIcon(os.path.join(base_path, "logo.png")))
    window = DrawingApp()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()