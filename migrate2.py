import os
import re

def migrate_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # job.get('field') -> getattr(job, 'field', None)
    # job.get("field") -> getattr(job, 'field', None)
    content = re.sub(r'(\bjob\b|\bj\b|\bjobs\[[^\]]+\])\.get\([\'"]([a-zA-Z0-9_]+)[\'"]\)', r'getattr(\1, "\2", None)', content)
    
    # job.get('field', default) -> getattr(job, 'field', default)
    # We can use a simpler regex for the two-arg version
    content = re.sub(r'(\bjob\b|\bj\b|\bjobs\[[^\]]+\])\.get\([\'"]([a-zA-Z0-9_]+)[\'"]\s*,\s*([^\)]+)\)', r'getattr(\1, "\2", \3)', content)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

def main():
    for d in ["backend", "tests"]:
        for root, dirs, files in os.walk(d):
            for file in files:
                if file.endswith(".py"):
                    migrate_file(os.path.join(root, file))
                    
if __name__ == "__main__":
    main()
