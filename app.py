from flask import Flask, request, render_template, jsonify
import os
import re
import requests
from datetime import datetime
from dotenv import load_dotenv
from git import Repo
import tempfile
import shutil
import threading
import time

load_dotenv()
app = Flask(__name__)


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'})
    
    try:
        content = file.read().decode('utf-8')
        processed = {
            'word_count': len(content.split()),
            'char_count': len(content),
            'uppercase': content.upper()[:1000] + ('...' if len(content) > 1000 else '')
        }
        return jsonify({'original': content, 'processed': processed})
    except Exception as e:
        return jsonify({'error': str(e)})

def extract_data(content, command_input):
    lines = content.splitlines()
    extracted = []
    rxcmd_filter = command_input.lower().strip()

    for idx, line in enumerate(lines, start=1):
        lower_line = line.lower()
        if 'rxcmd' not in lower_line:
            continue
        
        rxcmd_match = re.search(r'rxcmd:\s*(0x[a-f0-9]+)', lower_line)
        rxcmd = rxcmd_match.group(1) if rxcmd_match else ''

        if rxcmd_filter != 'all' and rxcmd != rxcmd_filter:
            continue

        sw_match = re.search(r'sw\s*:\s*(0x[a-f0-9]+)', lower_line)
        sw = sw_match.group(1) if sw_match else ''

        rt_match = re.search(r'rt\s((?:[0-9a-f]{2}\s+)*)(?=rtrt)', lower_line)
        rt = rt_match.group(1).strip() if rt_match else ''

        data_match = re.search(r'rtrt 0\s*(.*)', lower_line)
        data = data_match.group(1).strip() if data_match else ''

        extracted.append({
            'line': idx,
            'rxcmd': rxcmd,
            'sw': sw,
            'rt': rt,
            'data': data
        })
    return extracted


@app.route('/command-process', methods=['POST'])
def process_command():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'})

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'})

    command_input = request.form.get('command') or 'all'

    try:
        content = file.read().decode('utf-8')
        extracted_data = extract_data(content, command_input)
        return jsonify({'data': extracted_data})
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/export-to-gitlab', methods=['POST'])
def export_to_gitlab():
    file = request.files.get('file')
    filter_applied = request.form.get('filter', 'all').strip() or 'all'
    if not file:
        return jsonify({'error': 'No file provided.'}), 400

    try:
        filename_base = os.path.splitext(file.filename)[0]
        csv_filename = f"{filename_base}_{filter_applied}.csv"

        content = file.read().decode('utf-8')
        extracted_data = extract_data(content, filter_applied)

        csv_lines = ["Line,RxCmd,SW,RT,Data After RtRt 0"]
        for row in extracted_data:
            csv_lines.append(f"{row['line']},{row['rxcmd']},{row['sw']},{row['rt']},{row['data']}")
        csv_content = "\n".join(csv_lines)

        # Environment variables
        GIT_TOKEN = os.environ.get('GITLAB_TOKEN')
        GIT_REPO_URL = os.environ.get('GITLAB_REPO_URL')
        GIT_BRANCH = os.environ.get('GITLAB_BRANCH', 'main')
        GIT_FOLDER_PATH = os.environ.get('GITLAB_FOLDER_PATH', 'exports/')

        # Clone repo with authentication
        # repo_url_with_token = GIT_REPO_URL.replace('https://', f'https://{GIT_TOKEN}@')
        # temp_dir = tempfile.mkdtemp()
        # repo = Repo.clone_from(repo_url_with_token, temp_dir, branch=GIT_BRANCH)

        # Instead of tempfile.mkdtemp(), use a folder in your own project directory
        temp_dir = os.path.join(os.getcwd(), "cloned_repo")

        # Only clone if the folder doesn't exist (avoid re-cloning)
        if not os.path.exists(temp_dir):
            repo_url_with_token = GIT_REPO_URL.replace('https://', f'https://{GIT_TOKEN}@')
            repo = Repo.clone_from(repo_url_with_token, temp_dir, branch=GIT_BRANCH)
        else:
            repo = Repo(temp_dir)  # Reuse the existing local clone

        # Save CSV inside exports/
        folder_path = os.path.join(temp_dir, GIT_FOLDER_PATH)
        os.makedirs(folder_path, exist_ok=True)
        file_path = os.path.join(folder_path, csv_filename)

        with open(file_path, 'w') as f:
            f.write(csv_content)
        repo.git.pull('origin', GIT_BRANCH)
        # Commit and push
        repo.index.add([os.path.relpath(file_path, temp_dir)])
        repo.index.commit(f"Add structured log {csv_filename}")
        origin = repo.remote(name='origin')
        origin.push()
        # Safe background delete to avoid Windows file lock error
        def delayed_delete(path):
            time.sleep(5)  # wait 5 seconds to let Git release locks
            try:
                shutil.rmtree(path)
            except Exception as e:
                print(f"Cleanup failed: {e}")

        threading.Thread(target=delayed_delete, args=(temp_dir,), daemon=True).start()

        #shutil.rmtree(temp_dir)

        return jsonify({"message": f"CSV exported to GitHub repo in {GIT_FOLDER_PATH}{csv_filename}"}), 200
        

    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5000)