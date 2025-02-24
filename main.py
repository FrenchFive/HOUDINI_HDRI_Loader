import os
import shutil
import sqlite3
import hou
import OpenImageIO as oiio
import numpy as np
from PySide2 import QtWidgets, QtGui, QtCore
from PIL import Image

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

class QWrapLayout(QtWidgets.QLayout):
    def __init__(self, parent=None, margin=0, spacing=-1):
        super(QWrapLayout, self).__init__(parent)
        if parent is not None:
            self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)
        self.itemList = []

    def addItem(self, item):
        self.itemList.append(item)

    def count(self):
        return len(self.itemList)

    def itemAt(self, index):
        return self.itemList[index] if 0 <= index < len(self.itemList) else None

    def takeAt(self, index):
        return self.itemList.pop(index) if 0 <= index < len(self.itemList) else None

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self.doLayout(QtCore.QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super(QWrapLayout, self).setGeometry(rect)
        self.doLayout(rect, False)

    def sizeHint(self):
        return QtCore.QSize(400, 300)

    def minimumSize(self):
        return QtCore.QSize(200, 200)

    def doLayout(self, rect, testOnly):
        x, y, lineHeight = rect.x(), rect.y(), 0
        for item in self.itemList:
            spaceX, spaceY = self.spacing(), self.spacing()
            nextX = x + item.sizeHint().width() + spaceX
            if nextX - spaceX > rect.right() and lineHeight > 0:
                x = rect.x()
                y += lineHeight + spaceY
                nextX = x + item.sizeHint().width() + spaceX
                lineHeight = 0
            if not testOnly:
                item.setGeometry(QtCore.QRect(QtCore.QPoint(x, y), item.sizeHint()))
            x = nextX
            lineHeight = max(lineHeight, item.sizeHint().height())
        return y + lineHeight - rect.y()

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
        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_widget = QtWidgets.QWidget()
        self.wrap_layout = QWrapLayout(self.scroll_widget)
        self.scroll_widget.setLayout(self.wrap_layout)
        self.scroll_area.setWidget(self.scroll_widget)
        self.layout.addWidget(self.scroll_area)
        self.load_hdri_images()
    
    def load_hdri_images(self):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT id, file_path, preview_path, name FROM hdri")
        hdri_entries = cursor.fetchall()
        conn.close()
        
        for i in reversed(range(self.wrap_layout.count())):
            self.wrap_layout.takeAt(i).widget().deleteLater()
        
        for id, file_path, preview_path, name in hdri_entries:
            self.wrap_layout.addWidget(self.create_thumbnail_widget(file_path, preview_path, name))
    
    def create_thumbnail_widget(self, img_path, preview_path, name):
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout()
        
        btn = QtWidgets.QPushButton()
        btn.setFixedSize(150, 150)
        
        pixmap = QtGui.QPixmap(preview_path)
        if pixmap.isNull():
            pixmap.fill(QtGui.QColor("gray"))
        
        btn.setIcon(QtGui.QIcon(pixmap))
        btn.setIconSize(QtCore.QSize(150, 150))
        btn.clicked.connect(lambda: self.apply_hdri(img_path))
        
        label = QtWidgets.QLabel(name)
        label.setAlignment(QtCore.Qt.AlignCenter)
        
        layout.addWidget(btn)
        layout.addWidget(label)
        widget.setLayout(layout)
        return widget
    
    def generate_preview(self, input_path, output_path):
        brightness_factor=2.0
        gamma=0.8
        size=(200, 200)
        try:
            ext = os.path.splitext(input_path)[1].lower()
    
            if ext in [".exr", ".hdr"]:  # Handle HDR and EXR using OpenImageIO
                input_image = oiio.ImageInput.open(input_path)
                if not input_image:
                    raise ValueError(f"Could not open {input_path}")
    
                spec = input_image.spec()
                image_data = input_image.read_image("float")  # Read as float32
                input_image.close()
    
                if image_data is None:
                    raise ValueError("Failed to read image data.")
    
                # Reshape to match (height, width, channels)
                image = np.array(image_data).reshape(spec.height, spec.width, spec.nchannels)
    
                # Normalize and remove alpha channel if present
                if spec.nchannels > 3:
                    image = image[:, :, :3]  # Keep RGB only
    
                # Apply brightness factor
                image = image * brightness_factor
    
                # Apply gamma correction
                image = np.power(image, gamma)
    
                # Normalize to 8-bit
                image = np.clip(image * 255, 0, 255).astype(np.uint8)
    
                # Convert to PIL image for resizing
                img = Image.fromarray(image)
    
            else:  # Handle PNG, JPG, and other standard formats
                img = Image.open(input_path).convert("RGB")
    
            img.thumbnail(size, Image.ANTIALIAS)
            img.save(output_path, "JPEG")
            print(f"Preview generated: {output_path}")

        except Exception as e:
                print(f"Error generating preview for {input_path}: {e}")

    def add_hdri(self):
        file_dialog = QtWidgets.QFileDialog()
        file_path, _ = file_dialog.getOpenFileName(self, "Select HDRI", "", "HDRI Files (*.hdr *.exr *.png *.jpg)")
        
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

    def apply_hdri(self, hdri_path):
        try:
            # Get the Houdini root object
            obj = hou.node("/obj")
    
            # Check if an environment light already exists
            light_name = "hdri_env_light"
            env_light = obj.node(light_name)
    
            if env_light is None:
                # Create a new environment light
                env_light = obj.createNode("envlight", light_name)
    
            # Assign the HDRI to the environment light
            env_light.parm("env_map").set(hdri_path)
    
            # Move the light to a good position (optional)
            env_light.parmTuple("t").set((0, 5, 0))
    
            # Set intensity if needed
            env_light.parm("light_intensity").set(1.5)
    
            # Make sure the light is visible in the viewport
            env_light.setDisplayFlag(True)
            env_light.setRenderFlag(True)
    
            print(f"HDRI applied: {hdri_path}")
    
        except Exception as e:
            print(f"Error applying HDRI: {e}")


def launch_hdri_loader():
    global hdr_loader
    hdr_loader = HDRIPreviewLoader()
    hdr_loader.show()

launch_hdri_loader()
