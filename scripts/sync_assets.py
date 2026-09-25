import os
import shutil
import hashlib

def get_file_hash(path):
    hash_md5 = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def sync_assets():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    source_fonts = os.path.join(root, 'assets', 'fonts')
    
    destinations = [
        os.path.join(root, 'backend', 'fonts'),
        os.path.join(root, 'frontend', 'public', 'fonts'),
        os.path.join(root, 'remotion', 'public', 'fonts')
    ]
    
    if not os.path.exists(source_fonts):
        print(f"Source folder {source_fonts} does not exist.")
        return

    fonts = [f for f in os.listdir(source_fonts) if f.endswith('.ttf')]
    print(f"Found {len(fonts)} fonts in source.")

    for dest in destinations:
        os.makedirs(dest, exist_ok=True)
        for font in fonts:
            src_path = os.path.join(source_fonts, font)
            dest_path = os.path.join(dest, font)
            
            should_copy = True
            if os.path.exists(dest_path):
                if get_file_hash(src_path) == get_file_hash(dest_path):
                    should_copy = False
            
            if should_copy:
                shutil.copy2(src_path, dest_path)
                print(f"Copied {font} to {os.path.relpath(dest, root)}")
            else:
                pass # print(f"Up to date: {font} in {os.path.relpath(dest, root)}")

if __name__ == "__main__":
    print("Syncing centralized assets...")
    sync_assets()
    print("Done.")
