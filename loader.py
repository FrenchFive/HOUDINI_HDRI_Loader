import os
import shutil
import sqlite3
import hou
import OpenImageIO as oiio
import numpy as np
from PySide2 import QtWidgets, QtGui, QtCore
from PIL import Image

# Check if path.txt exists
if not os.path.exists("path.txt"):
    # Create a Houdini Folder Selector dialog
    folder_dialog = QtWidgets.QFileDialog()
    folder_dialog.setFileMode(QtWidgets.QFileDialog.Directory)
    folder_dialog.setOption(QtWidgets.QFileDialog.ShowDirsOnly)
    folder_dialog.setWindowTitle("Select HDRI Storage Folder")
    folder_dialog.exec_()
    HDRI_STORAGE_FOLDER = folder_dialog.selectedFiles()[0]
    with open("path.txt", "w") as f:
        f.write(HDRI_STORAGE_FOLDER)
else:
    with open("path.txt", "r") as f:
        HDRI_STORAGE_FOLDER = f.read()

print(HDRI_STORAGE_FOLDER)
DB_PATH = os.path.join(HDRI_STORAGE_FOLDER, "hdri_database.db")

def initialize_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hdri (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT NOT NULL,
            preview_path TEXT NOT NULL,
            name TEXT NOT NULL,
            cat_Outdoor BOOLEAN DEFAULT 0,
            cat_Indoor BOOLEAN DEFAULT 0,
            cat_Studio BOOLEAN DEFAULT 0,
            cat_Nature BOOLEAN DEFAULT 0,
            cat_Urban BOOLEAN DEFAULT 0,
            cat_Sunset BOOLEAN DEFAULT 0,
            cat_Night BOOLEAN DEFAULT 0,
            cat_Day BOOLEAN DEFAULT 0,
            cat_Dawn BOOLEAN DEFAULT 0
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

class HDRIInfoDialog(QtWidgets.QDialog):
    def __init__(self, record, parent=None):
        """
        record indices:
          0: id, 1: file_path, 2: preview_path, 3: name,
          4: cat_Outdoor, 5: cat_Indoor, 6: cat_Studio, 7: cat_Nature,
          8: cat_Urban, 9: cat_Sunset, 10: cat_Night, 11: cat_Day, 12: cat_Dawn
        """
        super(HDRIInfoDialog, self).__init__(parent)
        self.setWindowTitle("Update HDRI Info")
        layout = QtWidgets.QFormLayout(self)
        
        self.name_edit = QtWidgets.QLineEdit(record[3])
        layout.addRow("Name:", self.name_edit)
        
        self.outdoor_checkbox = QtWidgets.QCheckBox("Outdoor")
        self.outdoor_checkbox.setChecked(bool(record[4]))
        layout.addRow(self.outdoor_checkbox)
        
        self.indoor_checkbox = QtWidgets.QCheckBox("Indoor")
        self.indoor_checkbox.setChecked(bool(record[5]))
        layout.addRow(self.indoor_checkbox)
        
        self.studio_checkbox = QtWidgets.QCheckBox("Studio")
        self.studio_checkbox.setChecked(bool(record[6]))
        layout.addRow(self.studio_checkbox)
        
        self.nature_checkbox = QtWidgets.QCheckBox("Nature")
        self.nature_checkbox.setChecked(bool(record[7]))
        layout.addRow(self.nature_checkbox)
        
        self.urban_checkbox = QtWidgets.QCheckBox("Urban")
        self.urban_checkbox.setChecked(bool(record[8]))
        layout.addRow(self.urban_checkbox)
        
        self.sunset_checkbox = QtWidgets.QCheckBox("Sunset")
        self.sunset_checkbox.setChecked(bool(record[9]))
        layout.addRow(self.sunset_checkbox)
        
        self.night_checkbox = QtWidgets.QCheckBox("Night")
        self.night_checkbox.setChecked(bool(record[10]))
        layout.addRow(self.night_checkbox)
        
        self.day_checkbox = QtWidgets.QCheckBox("Day")
        self.day_checkbox.setChecked(bool(record[11]))
        layout.addRow(self.day_checkbox)
        
        self.dawn_checkbox = QtWidgets.QCheckBox("Dawn")
        self.dawn_checkbox.setChecked(bool(record[12]))
        layout.addRow(self.dawn_checkbox)
        
        self.button_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addRow(self.button_box)

class HDRIPreviewLoader(QtWidgets.QWidget):
    def __init__(self):
        super(HDRIPreviewLoader, self).__init__()
        self.setWindowTitle("HDRI Preview Loader")
        self.setGeometry(100, 100, 800, 600)
        initialize_database()
        self.layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.layout)
        
        # -- Search and Filter Bar Section --
        self.search_layout = QtWidgets.QHBoxLayout()
        self.search_bar = QtWidgets.QLineEdit()
        self.search_bar.setPlaceholderText("Search HDRI...")
        self.search_bar.textChanged.connect(self.search_hdri)
        self.search_layout.addWidget(self.search_bar)
        
        # Filter button to toggle filter checkboxes
        self.filter_button = QtWidgets.QPushButton("Filters")
        self.filter_button.setCheckable(True)
        self.filter_button.toggled.connect(self.toggle_filters)
        self.search_layout.addWidget(self.filter_button)
        self.layout.addLayout(self.search_layout)
        
        # -- Filter Widget (initially hidden) --
        self.filter_widget = QtWidgets.QWidget()
        self.filter_layout = QtWidgets.QHBoxLayout(self.filter_widget)
        self.filter_checkboxes = {}
        # List of tuples: (database column, display text)
        categories = [
            ("cat_Outdoor", "Outdoor"),
            ("cat_Indoor", "Indoor"),
            ("cat_Studio", "Studio"),
            ("cat_Nature", "Nature"),
            ("cat_Urban", "Urban"),
            ("cat_Sunset", "Sunset"),
            ("cat_Night", "Night"),
            ("cat_Day", "Day"),
            ("cat_Dawn", "Dawn")
        ]
        for col, text in categories:
            cb = QtWidgets.QCheckBox(text)
            cb.stateChanged.connect(self.search_hdri)
            self.filter_layout.addWidget(cb)
            self.filter_checkboxes[col] = cb
        self.filter_widget.setVisible(False)
        self.layout.addWidget(self.filter_widget)
        
        # -- Add HDRI Button --
        self.add_button = QtWidgets.QPushButton("Add HDRI")
        self.add_button.clicked.connect(self.add_hdri)
        self.layout.addWidget(self.add_button)
        
        # -- Scrollable Grid Section --
        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_widget = QtWidgets.QWidget()
        self.wrap_layout = QWrapLayout(self.scroll_widget)
        self.scroll_widget.setLayout(self.wrap_layout)
        self.scroll_area.setWidget(self.scroll_widget)
        self.layout.addWidget(self.scroll_area)
        
        self.load_hdri_images()
    
    def toggle_filters(self, checked):
        self.filter_widget.setVisible(checked)
        self.search_hdri()
    
    def load_hdri_images(self, search_text=""):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        base_query = """
            SELECT id, file_path, preview_path, name,
                   cat_Outdoor, cat_Indoor, cat_Studio, cat_Nature,
                   cat_Urban, cat_Sunset, cat_Night, cat_Day, cat_Dawn
            FROM hdri
        """
        conditions = []
        params = []
        if search_text:
            conditions.append("name LIKE ?")
            params.append(f"%{search_text}%")
        
        # Build filter conditions (using OR logic among checked filters)
        filter_conds = []
        for col, checkbox in self.filter_checkboxes.items():
            if checkbox.isChecked():
                filter_conds.append(f"{col} = 1")
        if filter_conds:
            # If there are both search text and filter conditions, combine with AND.
            conditions.append("(" + " OR ".join(filter_conds) + ")")
        
        if conditions:
            query = base_query + " WHERE " + " AND ".join(conditions)
        else:
            query = base_query
        
        cursor.execute(query, params)
        records = cursor.fetchall()
        conn.close()
        
        # Clear existing widgets from the grid
        for i in reversed(range(self.wrap_layout.count())):
            widget = self.wrap_layout.takeAt(i).widget()
            if widget:
                widget.deleteLater()
        
        # Create and add a thumbnail widget for each HDRI record
        for record in records:
            self.wrap_layout.addWidget(self.create_thumbnail_widget(record))
    
    def search_hdri(self):
        # Use the current text and filter settings to update the grid
        search_text = self.search_bar.text().strip()
        self.load_hdri_images(search_text)
    
    def create_thumbnail_widget(self, record):
        # record indices:
        # 0: id, 1: file_path, 2: preview_path, 3: name, 4-12: category flags
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout()
        
        # HDRI apply button with thumbnail image
        btn = QtWidgets.QPushButton()
        btn.setFixedSize(150, 150)
        pixmap = QtGui.QPixmap(record[2])
        if pixmap.isNull():
            pixmap.fill(QtGui.QColor("gray"))
        btn.setIcon(QtGui.QIcon(pixmap))
        btn.setIconSize(QtCore.QSize(150, 150))
        btn.clicked.connect(lambda: self.apply_hdri(record[1]))
        layout.addWidget(btn)
        
        # Label displaying the HDRI name
        label = QtWidgets.QLabel(record[3])
        label.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(label)
        
        # Update button to change info
        update_btn = QtWidgets.QPushButton("Update")
        update_btn.clicked.connect(lambda: self.update_hdri_info(record))
        layout.addWidget(update_btn)
        
        # Delete button to remove the HDRI
        delete_btn = QtWidgets.QPushButton("Delete")
        delete_btn.clicked.connect(lambda: self.delete_hdri(record[0], record[1]))
        layout.addWidget(delete_btn)
        
        widget.setLayout(layout)
        return widget
    
    def update_hdri_info(self, record):
        dialog = HDRIInfoDialog(record, self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            new_name = dialog.name_edit.text().strip()
            new_cat_outdoor = 1 if dialog.outdoor_checkbox.isChecked() else 0
            new_cat_indoor = 1 if dialog.indoor_checkbox.isChecked() else 0
            new_cat_studio = 1 if dialog.studio_checkbox.isChecked() else 0
            new_cat_nature = 1 if dialog.nature_checkbox.isChecked() else 0
            new_cat_urban = 1 if dialog.urban_checkbox.isChecked() else 0
            new_cat_sunset = 1 if dialog.sunset_checkbox.isChecked() else 0
            new_cat_night = 1 if dialog.night_checkbox.isChecked() else 0
            new_cat_day = 1 if dialog.day_checkbox.isChecked() else 0
            new_cat_dawn = 1 if dialog.dawn_checkbox.isChecked() else 0
            
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE hdri 
                SET name = ?, 
                    cat_Outdoor = ?,
                    cat_Indoor = ?,
                    cat_Studio = ?,
                    cat_Nature = ?,
                    cat_Urban = ?,
                    cat_Sunset = ?,
                    cat_Night = ?,
                    cat_Day = ?,
                    cat_Dawn = ?
                WHERE id = ?
            """, (new_name, new_cat_outdoor, new_cat_indoor, new_cat_studio, new_cat_nature,
                  new_cat_urban, new_cat_sunset, new_cat_night, new_cat_day, new_cat_dawn, record[0]))
            conn.commit()
            conn.close()
            self.load_hdri_images()
    
    def generate_preview(self, input_path, output_path):
        brightness_factor = 2.0
        gamma = 0.8
        size = (200, 200)
        try:
            ext = os.path.splitext(input_path)[1].lower()
            if ext in [".exr", ".hdr"]:
                input_image = oiio.ImageInput.open(input_path)
                if not input_image:
                    raise ValueError(f"Could not open {input_path}")
                spec = input_image.spec()
                image_data = input_image.read_image("float")
                input_image.close()
                if image_data is None:
                    raise ValueError("Failed to read image data.")
                image = np.array(image_data).reshape(spec.height, spec.width, spec.nchannels)
                if spec.nchannels > 3:
                    image = image[:, :, :3]
                image = image * brightness_factor
                image = np.power(image, gamma)
                image = np.clip(image * 255, 0, 255).astype(np.uint8)
                img = Image.fromarray(image)
            else:
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
            # For new HDRI, we start with default category values (all 0)
            text, ok = QtWidgets.QInputDialog.getText(self, "Enter HDRI Name", "Name:", text=file_name)
            if not ok or not text:
                return

            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO hdri (file_path, preview_path, name, 
                                  cat_Outdoor, cat_Indoor, cat_Studio, cat_Nature, 
                                  cat_Urban, cat_Sunset, cat_Night, cat_Day, cat_Dawn)
                VALUES (?, ?, ?, 0, 0, 0, 0, 0, 0, 0, 0, 0)
            """, ("", "", text))
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
    
    def delete_hdri(self, id, hdri_path):
        reply = QtWidgets.QMessageBox.question(
            self,
            "Delete HDRI",
            "Are you sure you want to delete this HDRI?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        if reply == QtWidgets.QMessageBox.Yes:
            try:
                folder_to_delete = os.path.dirname(hdri_path)
                if os.path.exists(folder_to_delete):
                    shutil.rmtree(folder_to_delete)
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute("DELETE FROM hdri WHERE id = ?", (id,))
                conn.commit()
                conn.close()
                self.load_hdri_images()
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "Error", f"Error deleting HDRI: {e}")

    def apply_hdri(self, hdri_path):
        try:
            obj = hou.node("/obj")
            light_name = "hdri_env_light"
            env_light = obj.node(light_name)
            if env_light is None:
                env_light = obj.createNode("envlight", light_name)
            env_light.parm("env_map").set(hdri_path)
            print(f"HDRI applied: {hdri_path}")
            self.close()
        except Exception as e:
            print(f"Error applying HDRI: {e}")

def launch_hdri_loader():
    global hdr_loader
    hdr_loader = HDRIPreviewLoader()
    hdr_loader.show()

launch_hdri_loader()
