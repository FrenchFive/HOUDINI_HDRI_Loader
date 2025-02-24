import os
import shutil
import sqlite3
import hou
from PySide2 import QtWidgets, QtGui, QtCore

# HDRI storage location
HDRI_STORAGE_FOLDER = "/media/jobs/3Dlibrary/HDRI/LOADER"
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
        cursor.execute("SELECT id, file_path, preview_path, name FROM hdri")
        hdri_entries = cursor.fetchall()
        conn.close()
        
        row, col = 0, 0
        for id, file_path, preview_path, name in hdri_entries:
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
        if pixmap.isNull():
            pixmap = QtGui.QPixmap(150, 150)
            pixmap.fill(QtGui.QColor("gray"))
        
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
            
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO hdri (file_path, preview_path, name) VALUES (?, ?, ?)", ("", "", text))
            conn.commit()
            cursor.execute("SELECT last_insert_rowid()")
            id = cursor.fetchone()[0]
            conn.close()
            
            folder_name = f"{id:05d}_{text}"
            hdri_folder = os.path.join(HDRI_STORAGE_FOLDER, folder_name)
            os.makedirs(hdri_folder, exist_ok=True)
            
            new_file_path = os.path.join(hdri_folder, os.path.basename(file_path))
            shutil.copy(file_path, new_file_path)
            
            preview_path = os.path.join(hdri_folder, "preview.jpg")
            self.generate_preview(new_file_path, preview_path)
            
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("UPDATE hdri SET file_path = ?, preview_path = ? WHERE id = ?", (new_file_path, preview_path, id))
            conn.commit()
            conn.close()
            
            self.load_hdri_images()
    
    def generate_preview(self, img_path, preview_path):
        try:
            hou.image.saveFrameToFile(img_path, preview_path, 0, 150, 150)
        except Exception as e:
            print(f"Error generating preview for {img_path}: {e}")


def launch_hdri_loader():
    global hdr_loader
    hdr_loader = HDRIPreviewLoader()
    hdr_loader.show()

launch_hdri_loader()
