#utils.py
import os

def load_data(folder=None):
    """
    Load all .txt files from the data folder.
    Returns a list of lines stripped of whitespace.
    """
    if folder is None:
        folder = os.path.join(os.path.dirname(__file__), "data")

    data = []

    if not os.path.exists(folder):
        return data

    for file in os.listdir(folder):
        if file.endswith(".txt"):
            path = os.path.join(folder, file)
            with open(path, "r", encoding="utf-8") as f:
                 text = f.read()
                 
                 paragraphs = text.split("\n\n")
                 for para in paragraphs:
                     if para.strip():
                         data.append(para.strip())

    return data


