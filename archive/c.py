import os
import shutil

def clear_charts_folder():
    charts_dir = os.path.join(os.path.dirname(__file__), 'charts')
    if os.path.exists(charts_dir):
        shutil.rmtree(charts_dir)
        os.makedirs(charts_dir)
        print(f"Cleared charts folder: {charts_dir}")
    else:
        os.makedirs(charts_dir)
        print(f"Created charts folder: {charts_dir}")
clear_charts_folder()