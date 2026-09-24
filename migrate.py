import os
import re
import glob

def migrate_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Pattern: (job|jobs[...]|j)\['field'\] or ["field"]
    # We will match anything that looks like job['x'] or jobs[x]['y']
    
    # First: jobs[x]['y'] -> jobs[x].y
    content = re.sub(r'(jobs\[[^\]]+\])\[[\'"]([a-zA-Z0-9_]+)[\'"]\]', r'\1.\2', content)
    
    # Second: job['y'] -> job.y
    content = re.sub(r'(\bjob\b)\[[\'"]([a-zA-Z0-9_]+)[\'"]\]', r'\1.\2', content)
    
    # Also j['y'] where j is a job? Let's just do j if it's explicitly assigned. 
    # Let's check for `j = jobs[job_id]` in job_queue.py
    content = re.sub(r'(\bj\b)\[[\'"]([a-zA-Z0-9_]+)[\'"]\]', r'\1.\2', content)

    # What about app.jobs[job_id]['status'] in tests?
    content = re.sub(r'(app\.jobs\[[^\]]+\])\[[\'"]([a-zA-Z0-9_]+)[\'"]\]', r'\1.\2', content)
    
    # publish_jobs[publish_id]['status'] -> publish_jobs[publish_id].status
    content = re.sub(r'(publish_jobs\[[^\]]+\])\[[\'"]([a-zA-Z0-9_]+)[\'"]\]', r'\1.\2', content)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

def main():
    root_dir = "backend"
    tests_dir = "tests"
    
    for d in [root_dir, tests_dir]:
        for root, dirs, files in os.walk(d):
            for file in files:
                if file.endswith(".py"):
                    migrate_file(os.path.join(root, file))
                    
if __name__ == "__main__":
    main()
