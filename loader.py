import os
import shutil
import sqlite3
import datetime
from functools import partial

import hou
import OpenImageIO as oiio
import numpy as np
from PySide2 import QtWidgets, QtGui, QtCore
from PIL import Image

# Check if path.txt exists; if not, prompt the user to select a folder.
if not os.path.exists("path.txt"):
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
    # Create the hdri table with fixed columns; tag columns will be added dynamically.
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS hdri (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT NOT NULL,
            preview_path TEXT NOT NULL,
            name TEXT NOT NULL,
            upload_date TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()

def get_tag_columns():
    """Return a list of tag column names in the hdri table (columns starting with 'tag_')."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(hdri)")
    cols = cursor.fetchall()  # each row: (cid, name, type, notnull, dflt_value, pk)
    conn.close()
    tag_cols = [col[1] for col in cols if col[1].startswith("tag_")]
    return tag_cols

def safe_tag_column(tag_name):
    """Create a safe column name for a tag by stripping spaces and prepending 'tag_'."""
    return "tag_" + tag_name.strip().replace(" ", "_")

def drop_column_from_table(db_path, table, column_to_drop):
    """
    Workaround to drop a column in SQLite:
      1. Create a temporary table with all columns except the one to drop.
      2. Copy data.
      3. Drop the old table.
      4. Rename the new table.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table})")
    columns_info = cursor.fetchall()  # (cid, name, type, notnull, dflt_value, pk)
    # Keep all columns except the one to drop.
    new_columns = [col for col in columns_info if col[1] != column_to_drop]
    # Build new CREATE TABLE statement.
    col_defs = []
    for col in new_columns:
        name = col[1]
        typ = col[2]
        notnull = "NOT NULL" if col[3] else ""
        dflt = f"DEFAULT {col[4]}" if col[4] is not None else ""
        pk = "PRIMARY KEY" if col[5] else ""
        parts = [name, typ, notnull, dflt, pk]
        parts = [p for p in parts if p]
        col_defs.append(" ".join(parts))
    col_defs_str = ", ".join(col_defs)
    temp_table = table + "_backup"
    cursor.execute("BEGIN TRANSACTION;")
    cursor.execute(f"CREATE TABLE {temp_table} ({col_defs_str});")
    col_names = [col[1] for col in new_columns]
    col_names_str = ", ".join(col_names)
    cursor.execute(f"INSERT INTO {temp_table} ({col_names_str}) SELECT {col_names_str} FROM {table};")
    cursor.execute(f"DROP TABLE {table};")
    cursor.execute(f"ALTER TABLE {temp_table} RENAME TO {table};")
    conn.commit()
    conn.close()

class QWrapLayout(QtWidgets.QLayout):
    def __init__(self, parent=None, margin=0, spacing=-1):
        super().__init__(parent)
        if parent is not None:
            self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)
        self.itemList = []

    def addItem(self, item):
        self.itemList.append(item)

    def count(self):
        return len(self.itemList)

    def itemAt(self, index):
        if 0 <= index < len(self.itemList):
            return self.itemList[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self.itemList):
            return self.itemList.pop(index)
        return None

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self.doLayout(QtCore.QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self.doLayout(rect, False)

    def sizeHint(self):
        return QtCore.QSize(400, 300)

    def minimumSize(self):
        return QtCore.QSize(200, 200)

    def doLayout(self, rect, testOnly):
        x = rect.x()
        y = rect.y()
        line_height = 0
        for item in self.itemList:
            space_x = self.spacing()
            space_y = self.spacing()
            next_x = x + item.sizeHint().width() + space_x
            if next_x - space_x > rect.right() and line_height > 0:
                x = rect.x()
                y += line_height + space_y
                next_x = x + item.sizeHint().width() + space_x
                line_height = 0
            if not testOnly:
                item.setGeometry(QtCore.QRect(QtCore.QPoint(x, y), item.sizeHint()))
            x = next_x
            line_height = max(line_height, item.sizeHint().height())
        return y + line_height - rect.y()

class HDRIInfoDialog(QtWidgets.QDialog):
    def __init__(self, record, parent=None):
        """
        record indices:
          0: id, 1: file_path, 2: preview_path, 3: name, 4: upload_date
        """
        super().__init__(parent)
        self.setWindowTitle("Update HDRI Info")
        self.hdri_id = record[0]
        self.tag_checkboxes = {}  # Mapping from tag column name to QCheckBox
        layout = QtWidgets.QFormLayout(self)

        self.name_edit = QtWidgets.QLineEdit(record[3])
        layout.addRow("Name:", self.name_edit)

        # --- Tag editing section ---
        self.tags_widget = QtWidgets.QWidget()
        self.tags_layout = QtWidgets.QVBoxLayout(self.tags_widget)
        self.load_tags()  # Populate self.tags_layout with checkboxes and delete buttons
        layout.addRow("Tags:", self.tags_widget)

        # Input and button to add a new tag
        tag_input_layout = QtWidgets.QHBoxLayout()
        self.new_tag_edit = QtWidgets.QLineEdit()
        self.new_tag_edit.setPlaceholderText("Enter new tag")
        self.add_tag_button = QtWidgets.QPushButton("Add Tag")
        self.add_tag_button.clicked.connect(self.add_new_tag)
        tag_input_layout.addWidget(self.new_tag_edit)
        tag_input_layout.addWidget(self.add_tag_button)
        layout.addRow("New Tag:", tag_input_layout)

        # --- Dialog buttons ---
        self.button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addRow(self.button_box)

    def load_tags(self):
        """Clear and repopulate the tags section with checkboxes for each tag column."""
        for i in reversed(range(self.tags_layout.count())):
            item = self.tags_layout.takeAt(i)
            if item.widget():
                item.widget().deleteLater()
        self.tag_checkboxes = {}
        tag_cols = get_tag_columns()
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        for col in tag_cols:
            cursor.execute(f"SELECT {col} FROM hdri WHERE id = ?", (self.hdri_id,))
            value = cursor.fetchone()[0]
            hlayout = QtWidgets.QHBoxLayout()
            display_name = col[4:]  # remove the "tag_" prefix for display
            checkbox = QtWidgets.QCheckBox(display_name)
            checkbox.setChecked(bool(value))
            self.tag_checkboxes[col] = checkbox
            hlayout.addWidget(checkbox)
            # X button to delete the tag without confirmation
            del_btn = QtWidgets.QPushButton("X")
            del_btn.setFixedSize(20, 20)
            # Use functools.partial to capture the current value of col
            del_btn.clicked.connect(partial(self.delete_tag, col))
            hlayout.addWidget(del_btn)
            container = QtWidgets.QWidget()
            container.setLayout(hlayout)
            self.tags_layout.addWidget(container)
        conn.close()

    def add_new_tag(self):
        new_tag = self.new_tag_edit.text().strip()
        if not new_tag:
            return
        col_name = safe_tag_column(new_tag)
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        try:
            cursor.execute(f"ALTER TABLE hdri ADD COLUMN {col_name} BOOLEAN DEFAULT 0")
            conn.commit()
        except Exception as e:
            print(f"Error adding tag: {e}")
            conn.close()
            return
        cursor.execute(f"UPDATE hdri SET {col_name} = 1 WHERE id = ?", (self.hdri_id,))
        conn.commit()
        conn.close()
        self.new_tag_edit.clear()
        self.load_tags()
        parent = self.parent()
        if parent is not None and hasattr(parent, "populate_filter_checkboxes"):
            parent.populate_filter_checkboxes()

    def delete_tag(self, col_name):
        # Immediately drop the column without confirmation or warning.
        try:
            drop_column_from_table(DB_PATH, "hdri", col_name)
        except Exception as e:
            print(f"Error deleting tag: {e}")
            return
        self.load_tags()
        parent = self.parent()
        if parent is not None and hasattr(parent, "populate_filter_checkboxes"):
            parent.populate_filter_checkboxes()

    def accept(self):
        new_name = self.name_edit.text().strip()
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("UPDATE hdri SET name = ? WHERE id = ?", (new_name, self.hdri_id))
        for col, checkbox in self.tag_checkboxes.items():
            val = 1 if checkbox.isChecked() else 0
            cursor.execute(f"UPDATE hdri SET {col} = ? WHERE id = ?", (val, self.hdri_id))
        conn.commit()
        conn.close()
        super().accept()

class HDRIPreviewLoader(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
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
        self.filter_button = QtWidgets.QPushButton("Filters")
        self.filter_button.setCheckable(True)
        self.filter_button.toggled.connect(self.toggle_filters)
        self.search_layout.addWidget(self.filter_button)
        self.sort_combo = QtWidgets.QComboBox()
        self.sort_combo.addItems([
            "Alphabetical Ascending",
            "Alphabetical Descending",
            "Upload Date Ascending",
            "Upload Date Descending"
        ])
        self.sort_combo.currentIndexChanged.connect(self.search_hdri)
        self.search_layout.addWidget(self.sort_combo)
        self.layout.addLayout(self.search_layout)

        # -- Filter Widget (initially hidden) --
        self.filter_widget = QtWidgets.QWidget()
        self.filter_layout = QtWidgets.QHBoxLayout(self.filter_widget)
        self.filter_checkboxes = {}
        self.populate_filter_checkboxes()
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

    def populate_filter_checkboxes(self):
        for i in reversed(range(self.filter_layout.count())):
            widget = self.filter_layout.takeAt(i).widget()
            if widget:
                widget.deleteLater()
        self.filter_checkboxes = {}
        for col in get_tag_columns():
            display_name = col[4:]
            cb = QtWidgets.QCheckBox(display_name)
            cb.stateChanged.connect(self.search_hdri)
            self.filter_layout.addWidget(cb)
            self.filter_checkboxes[col] = cb

    def toggle_filters(self, checked):
        self.filter_widget.setVisible(checked)
        self.search_hdri()

    def load_hdri_images(self, search_text=""):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        base_query = "SELECT id, file_path, preview_path, name, upload_date FROM hdri"
        conditions = []
        params = []
        if search_text:
            conditions.append("name LIKE ?")
            params.append(f"%{search_text}%")
        for col, cb in self.filter_checkboxes.items():
            if cb.isChecked():
                conditions.append(f"{col} = 1")
        if conditions:
            query = base_query + " WHERE " + " AND ".join(conditions)
        else:
            query = base_query
        sort_option = self.sort_combo.currentText() if hasattr(self, 'sort_combo') else "Alphabetical Ascending"
        if sort_option.startswith("Alphabetical"):
            query += " ORDER BY name "
        elif sort_option.startswith("Upload Date"):
            query += " ORDER BY upload_date "
        query += "DESC" if "Descending" in sort_option else "ASC"
        cursor.execute(query, params)
        records = cursor.fetchall()
        conn.close()

        for i in reversed(range(self.wrap_layout.count())):
            widget = self.wrap_layout.takeAt(i).widget()
            if widget:
                widget.deleteLater()

        for record in records:
            self.wrap_layout.addWidget(self.create_thumbnail_widget(record))

    def search_hdri(self):
        search_text = self.search_bar.text().strip()
        self.load_hdri_images(search_text)

    def create_thumbnail_widget(self, record):
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout()
        
        # Create the HDRI preview button.
        btn = QtWidgets.QPushButton()
        btn.setFixedSize(150, 150)
        pixmap = QtGui.QPixmap(record[2])
        if pixmap.isNull():
            pixmap = QtGui.QPixmap(150, 150)
            pixmap.fill(QtGui.QColor("gray"))
        btn.setIcon(QtGui.QIcon(pixmap))
        btn.setIconSize(QtCore.QSize(150, 150))
        btn.clicked.connect(lambda: self.apply_hdri(record[1]))
        layout.addWidget(btn)
        
        # Create a horizontal layout for the HDRI name and the options button.
        name_layout = QtWidgets.QHBoxLayout()
        
        # Display only the HDRI name (date removed).
        name_label = QtWidgets.QLabel(record[3])
        name_layout.addWidget(name_label)
        
        # Create a three-dotted button using QToolButton.
        options_button = QtWidgets.QToolButton()
        options_button.setText("...")
        options_button.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        
        # Create a menu with "Update" and "Delete" actions.
        menu = QtWidgets.QMenu(options_button)
        update_action = menu.addAction("Update")
        delete_action = menu.addAction("Delete")
        
        update_action.triggered.connect(lambda: self.update_hdri_info(record))
        delete_action.triggered.connect(lambda: self.delete_hdri(record[0], record[1]))
        
        options_button.setMenu(menu)
        name_layout.addWidget(options_button)
        
        layout.addLayout(name_layout)
        widget.setLayout(layout)
        return widget


    def update_hdri_info(self, record):
        dialog = HDRIInfoDialog(record, self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            self.load_hdri_images()
            self.populate_filter_checkboxes()

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
            hdri_name, ok = QtWidgets.QInputDialog.getText(self, "Enter HDRI Name", "Name:", text=file_name)
            if not ok or not hdri_name:
                return
            current_date = datetime.datetime.now().isoformat()
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO hdri (file_path, preview_path, name, upload_date) VALUES (?, ?, ?, ?)",
                ("", "", hdri_name, current_date),
            )
            conn.commit()
            cursor.execute("SELECT last_insert_rowid()")
            hdri_id = cursor.fetchone()[0]
            conn.close()
            folder_name = f"{hdri_id:05d}_{hdri_name}"
            hdri_folder = os.path.join(HDRI_STORAGE_FOLDER, folder_name)
            os.makedirs(hdri_folder, exist_ok=True)
            new_file_path = os.path.join(hdri_folder, os.path.basename(file_path))
            shutil.copy(file_path, new_file_path)
            preview_path = os.path.join(hdri_folder, "preview.jpg")
            self.generate_preview(new_file_path, preview_path)
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("UPDATE hdri SET file_path = ?, preview_path = ? WHERE id = ?",
                           (new_file_path, preview_path, hdri_id))
            conn.commit()
            conn.close()
            self.load_hdri_images()
            self.populate_filter_checkboxes()

    def delete_hdri(self, hdri_id, hdri_path):
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
                cursor.execute("DELETE FROM hdri WHERE id = ?", (hdri_id,))
                conn.commit()
                conn.close()
                self.load_hdri_images()
                self.populate_filter_checkboxes()
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "Error", f"Error deleting HDRI: {e}")

    def apply_hdri(self, hdri_path):
        try:
            selected_nodes = hou.selectedNodes()
            if selected_nodes:
                node = selected_nodes[0]
                found_parm = None
                for parm in node.parms():
                    if parm.name().lower() in ["file", "filename", "env_map"]:
                        found_parm = parm
                        break
                if found_parm:
                    found_parm.set(hdri_path)
                    print(f"HDRI applied to selected node '{node.path()}': {hdri_path}")
                    # Copy HDRI path to the clipboard.
                    QtWidgets.QApplication.clipboard().setText(hdri_path)
                    self.close()
                    return
                else:
                    print(f"Selected node '{node.path()}' has no matching parameter.")
            obj = hou.node("/obj")
            light_name = "hdri_env_light"
            env_light = obj.node(light_name)
            if env_light is None:
                env_light = obj.createNode("envlight", light_name)
            parm_set = False
            for param_name in ["env_map", "file", "filename"]:
                parm = env_light.parm(param_name)
                if parm is not None:
                    parm.set(hdri_path)
                    parm_set = True
                    break
            if parm_set:
                print(f"HDRI applied on environment light: {hdri_path}")
            else:
                print("No matching parameter found on environment light.")
            # Copy HDRI path to the clipboard.
            QtWidgets.QApplication.clipboard().setText(hdri_path)
            self.close()
        except Exception as e:
            print(f"Error applying HDRI: {e}")


def launch_hdri_loader():
    global hdr_loader
    hdr_loader = HDRIPreviewLoader()
    hdr_loader.show()

launch_hdri_loader()
