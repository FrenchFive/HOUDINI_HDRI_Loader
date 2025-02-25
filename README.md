# HDRI Loader for Houdini Sidefx
A tool to load the HDRI automaticly 

```python
filepath = r"path/to/github/loader.py"
with open(filepath, "r") as file:
    exec(file.read())
```
---

HDRI Preview Loader is a Python-based tool designed for managing, previewing, and applying HDRI files within Houdini. The application leverages a simple SQLite database to store metadata about HDRI files, including file paths, preview images, and various category tags. The intuitive graphical user interface (GUI) is built with PySide2, and the tool offers features such as search, filtering, and one-click HDRI application.

## Features

- **Import HDRIs:** Easily add HDRI files using a file dialog and automatically generate preview thumbnails.
- **Database Management:** Store HDRI metadata in an SQLite database with support for various predefined categories.
- **Search & Filtering:** Search HDRIs by name and filter by predefined category tags (e.g., Outdoor, Indoor, Studio, etc.).
- **Apply HDRI:** Automatically apply the selected HDRI to a Houdini node or create an environment light if none is selected.
- **Preview Regeneration:** Generate a 200x200 JPEG preview for HDRI files, with support for HDR and EXR formats.
- **Update and Delete:** Modify HDRI metadata and remove unwanted HDRIs from the database and file system.
- **PEP 8 Compliant:** The code follows PEP 8 style guidelines for clean and maintainable code.

## Requirements

- **Python 3.x**
- **Houdini** (for the `hou` module)
- **PySide2** (for the GUI)
- **OpenImageIO** (for HDR image processing)
- **NumPy**
- **Pillow (PIL)**

Houdini has all those modules pre-installed, so running the script through Houdini should be plug and play.

## Installation

1. **Clone the Repository:**

   ```bash
   git clone https://github.com/yourusername/hdri-preview-loader.git
   cd hdri-preview-loader
   ```

2. **Install Dependencies:**

   You can install the required Python packages using `pip`:

   ```bash
   pip install PySide2 numpy Pillow
   ```

   *Note:* As mentionned before Houdini should have all dependencies already installed as default

3. **Setup Houdini Environment:**

   Ensure that Houdini is installed and properly configured so that Python can import the `hou` module.

## Usage

1. **Run the Application:**

   Simply run the Python script from within Houdini's Python environment or from a terminal where Houdini's environment is configured:

   ```bash
   python hdri_preview_loader.py
   ```

2. **Selecting HDRI Storage Folder:**

   - On first launch, you will be prompted to select a folder where HDRI files and the database will be stored.
   - This path is saved in a `path.txt` file for future sessions.

3. **Managing HDRI Files:**

   - **Adding an HDRI:** Click the "Add HDRI" button, choose your file, and provide a name.
   - **Updating Metadata:** Use the "Update" button on any HDRI thumbnail to modify its metadata.
   - **Deleting an HDRI:** Remove unwanted HDRIs with the "Delete" button.

4. **Applying HDRI:**

   - Select a node in Houdini and click on an HDRI thumbnail to automatically apply the HDRI.
   - If no node is selected, the application will create or update an environment light in `/obj`.

