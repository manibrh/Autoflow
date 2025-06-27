import os
import json
import xml.etree.ElementTree as ET

def read_json(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def read_properties(file_path):
    data = {}
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip() and not line.startswith('#') and '=' in line:
                key, val = line.split('=', 1)
                data[key.strip()] = val.strip()
    return data

def write_xliff(data, input_file, output_file, src_lang='en', tgt_lang='fr'):
    xliff = ET.Element('xliff', {'version': '1.2'})
    file_tag = ET.SubElement(xliff, 'file', {
        'source-language': src_lang,
        'target-language': tgt_lang,
        'datatype': 'plaintext',
        'original': os.path.basename(input_file)
    })
    body = ET.SubElement(file_tag, 'body')

    for i, (key, value) in enumerate(data.items(), start=1):
        tu = ET.SubElement(body, 'trans-unit', {'id': str(i), 'resname': key})
        ET.SubElement(tu, 'source').text = value

    tree = ET.ElementTree(xliff)
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    tree.write(output_file, encoding='utf-8', xml_declaration=True)

def run_tep_preprocessing(input_dir, output_dir):
    for filename in os.listdir(input_dir):
        full_path = os.path.join(input_dir, filename)
        base, ext = os.path.splitext(filename)
        if ext.lower() == '.json':
            data = read_json(full_path)
        elif ext.lower() == '.properties':
            data = read_properties(full_path)
        else:
            continue
        output_file = os.path.join(output_dir, f"{base}.xliff")
        write_xliff(data, full_path, output_file)
