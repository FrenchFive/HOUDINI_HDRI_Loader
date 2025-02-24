import os
import shutil
import sqlite3
import hou
from PySide2 import QtWidgets, QtGui, QtCore

# HDRI storage location
HDRI_STORAGE_FOLDER = "/media/jobs/3Dlibrary/HDRI/LOADER"  # Change to your desired storage location
DB_PATH = os.path.join(HDRI_STORAGE_FOLDER, "hdri_database.db")

def initialize_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hdri (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT NOT NULL,
            preview_path TEXT NOT NULL,
            name TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

class HDRIPreviewLoader(QtWidgets.QWidget):
    def __init__(self):
        super(HDRIPreviewLoader, self).__init__()
        self.setWindowTitle("HDRI Preview Loader")
        self.setGeometry(100, 100, 800, 600)
        
        initialize_database()
        
        self.layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.layout)
        
        self.add_button = QtWidgets.QPushButton("Add HDRI")
        self.add_button.clicked.connect(self.add_hdri)
        self.layout.addWidget(self.add_button)
        
        self.grid_layout = QtWidgets.QGridLayout()
        self.layout.addLayout(self.grid_layout)
        
        self.load_hdri_images()
    
    def load_hdri_images(self):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT file_path, preview_path, name FROM hdri")
        hdri_entries = cursor.fetchall()
        conn.close()
        
        row, col = 0, 0
        for file_path, preview_path, name in hdri_entries:
            widget = self.create_thumbnail_widget(file_path, preview_path, name)
            self.grid_layout.addWidget(widget, row, col)
            
            col += 1
            if col >= 4:  # Adjust for a 4-column layout
                col = 0
                row += 1
    
    def create_thumbnail_widget(self, img_path, preview_path, name):
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout()
        
        btn = QtWidgets.QPushButton()
        btn.setFixedSize(150, 150)
        
        pixmap = QtGui.QPixmap(preview_path)
        icon = QtGui.QIcon(pixmap)
        btn.setIcon(icon)
        btn.setIconSize(QtCore.QSize(150, 150))
        
        btn.clicked.connect(lambda: self.apply_hdri(img_path))
        
        label = QtWidgets.QLabel(name)
        label.setAlignment(QtCore.Qt.AlignCenter)
        
        layout.addWidget(btn)
        layout.addWidget(label)
        widget.setLayout(layout)
        
        return widget
    
    def apply_hdri(self, img_path):
        env_light = hou.node("/obj").createNode("envlight")
        env_light.parm("env_map").set(img_path)
        print(f"Applied HDRI: {img_path}")
    
    def add_hdri(self):
        file_dialog = QtWidgets.QFileDialog()
        file_path, _ = file_dialog.getOpenFileName(self, "Select HDRI", "", "HDRI Files (*.hdr *.exr)")
        
        if file_path:
            file_name = os.path.splitext(os.path.basename(file_path))[0]
            text, ok = QtWidgets.QInputDialog.getText(self, "Enter HDRI Name", "Name:", text=file_name)
            if not ok or not text:
                return
            
            unique_folder = os.path.join(HDRI_STORAGE_FOLDER, text)
            os.makedirs(unique_folder, exist_ok=True)
            new_file_path = os.path.join(unique_folder, os.path.basename(file_path))
            shutil.copy(file_path, new_file_path)
            
            preview_path = os.path.join(unique_folder, "preview.jpg")
            self.generate_preview(file_path, preview_path)
            
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO hdri (file_path, preview_path, name) VALUES (?, ?, ?)", (new_file_path, preview_path, text))
            conn.commit()
            conn.close()
            
            self.load_hdri_images()
    
    def generate_preview(self, img_path, preview_path):
        pixmap = QtGui.QPixmap(img_path)
        if pixmap.isNull():
            print(f"Failed to load image for preview: {img_path}")
            return
        
        thumbnail = pixmap.scaled(150, 150, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        thumbnail.save(preview_path, "JPG")


def launch_hdri_loader():
    global hdr_loader
    hdr_loader = HDRIPreviewLoader()
    hdr_loader.show()

launch_hdri_loader()
