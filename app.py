from flask import Flask, request, render_template, jsonify
import os

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process_file():
    # Check if the file exists in the request
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'})
    
    file = request.files['file']
    # Check if a file was actually selected
    if file.filename == '':
        return jsonify({'error': 'No selected file'})
    
    # Process the file
    if file:
        try:
            # Read the file content
            content = file.read().decode('utf-8')
            
            # Do the text processing
            processed = {}
            processed['word_count'] = len(content.split())
            processed['char_count'] = len(content)
            
            # Convert to uppercase - truncate if too long
            upper_text = content.upper()
            if len(upper_text) > 1000:
                processed['uppercase'] = upper_text[:1000] + '...'
            else:
                processed['uppercase'] = upper_text
            
            # Return both original and processed data
            return jsonify({
                'original': content,
                'processed': processed
            })
        except Exception as e:
            return jsonify({'error': str(e)})



def extract_data(content, command_input):
    print(content)
    cmd = "rxcmd"
    command_input = command_input.lower()
    # entries = content.split('DB1kPtr')[1:]  # split entries
    
    results = []
    content = content.split("\n")
    for entry in content:
        entry_lower = entry.lower()
        rxcmd_pos = entry_lower.find(cmd)
        if rxcmd_pos == -1:
            continue        

        if command_input == "all"  or (command_input != "all" and entry_lower.find(f"rxcmd: {command_input}") > 0):
            # Find data after 'rtrt 0'
            rtrt_pos = entry_lower.find('rtrt 0')
            print(rtrt_pos, entry_lower)
            if rtrt_pos == -1:
                continue
        
            # Extract everything after 'rtrt 0'
            data_after = entry[rtrt_pos + len('RtRt 0'):].strip().split()[0:]
            # data_str = entry[rtrt_pos + len('RtRt 0'):].strip()
            
            results.append(data_after)
    
    return results



@app.route('/command-process', methods=['POST'])
def process_command():
    # Check if the file exists in the request
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'})
    
    file = request.files['file']
    # Check if a file was actually selected
    if file.filename == '':
        return jsonify({'error': 'No selected file'})
    
    # Process the file
    command_input = request.form.get('command_input') or "all"
    if not command_input:
        return jsonify({'error': 'RxCmd value is required'})
    #hi
    if file:
        try:
            content = file.read().decode('utf-8')
            extracted_data = extract_data(content, command_input)
            return jsonify({'command_input': command_input, 'command_output': extracted_data})
        except Exception as e:
            return jsonify({'error': str(e)})




if __name__ == '__main__':
    app.run(debug=True, port=5000)