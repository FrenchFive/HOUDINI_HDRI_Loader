# HDRI Loader for Houdini SideFX 🚀🌌

HDRI Loader is a powerful and intuitive tool designed to manage, preview, and apply HDRI files directly within Houdini. It helps you efficiently organize your HDRI library, prevent duplicate imports with perceptual hashing (pHash), and seamlessly integrate HDRIs into your scenes.

---

## Features ✨

- **Easy HDRI Import**  
  📂 Quickly add HDRIs using a file dialog and automatically generate high-quality preview thumbnails.

- **Smart Database Management**  
  💾 Store HDRI metadata (file paths, preview images, names, upload dates, and unique image hashes) in an SQLite database, preventing duplicate entries.

- **Search & Filtering**  
  🔍 Search HDRIs by name and filter by customizable tags. Easily add, update, or delete tags for better organization.

- **Seamless Houdini Integration**  
  🎬 Apply the selected HDRI directly to a Houdini node, or create/update an environment light if no node is selected.

- **Preview Generation**  
  🖼️ Generate 200x200 JPEG previews with brightness and gamma adjustments. Supports HDR, EXR, and standard image formats.

- **Code Guideline**  
  🐍 Built using Python with adherence to PEP 8 guidelines for clarity and maintainability.

---

## Requirements 📋

- **Python 3.x**
- **Houdini** (SideFX) with Python environment
- **PySide2** (for the GUI)
- **OpenImageIO** (for HDR image processing)
- **NumPy** (for numerical computations)
- **Pillow (PIL)** (for image manipulation)

> *Note:* Houdini usually comes with these modules pre-installed, so running the script from within Houdini should be seamless.

---

## Installation 🔧

1. **Clone the Repository:**

   ```bash
   git clone https://github.com/yourusername/hdri-loader-houdini.git
   cd hdri-loader-houdini
   ```

2. **Install Dependencies (if needed):**

   If you're running the script outside Houdini's built-in Python environment, install the required packages:

   ```bash
   pip install PySide2 numpy Pillow OpenImageIO
   ```

   *Tip:* Houdini's Python environment often includes these dependencies by default.

---

## Usage 🚀

1. **Launch Houdini:**

   Open Houdini and run the following Python snippet in the Houdini Python shell:

   ```python
   filepath = r"path/to/hdri_loader.py"
   with open(filepath, "r") as file:
       exec(file.read())
   ```

2. **Select HDRI Storage Folder:**

   - On the first run, you'll be prompted to choose a folder where HDRI files and the SQLite database will be stored.
   - This path is saved in a `path.txt` file for future sessions.

3. **Manage Your HDRIs:**

   - **Add HDRI:** Click the "Add HDRI" button to import new HDRI files.
   - **Update Metadata:** Use the "Update" option on any HDRI thumbnail to modify its name and tags.
   - **Delete HDRI:** Remove unwanted HDRIs from both the database and the file system.

4. **Apply HDRI:**

   - Select a node in Houdini and click on an HDRI thumbnail to automatically apply it.
   - If no node is selected, the tool creates or updates an environment light in `/obj`.

---

## Code Overview 📜

- **pHash Implementation:**  
  Computes a perceptual hash for each image to detect duplicates and ensure uniqueness.

- **Database Management:**  
  Utilizes SQLite to store and manage HDRI metadata, including custom tag columns.

- **GUI Built with PySide2:**  
  Provides an interactive interface for managing HDRI files with search, filtering, and preview capabilities.

- **Preview Generation:**  
  Generates optimized 200x200 JPEG previews with brightness and gamma corrections using PIL and OpenImageIO.

---

## Acknowledgements 🙏

A huge thank you to these resources for their invaluable help:

- [HackerFactor - Looks Like It](https://www.hackerfactor.com/blog/index.php?/archives/432-Looks-Like-It.html)  
  Their insights and implementation details inspired the pHash algorithm.

- [JohannesBuchner's imagehash on GitHub](https://github.com/JohannesBuchner/imagehash/tree/master)  
  An amazing project that provided great examples and ideas for perceptual image hashing.

---

Enjoy managing your HDRIs and elevate your Houdini projects with ease! 😄🎥
