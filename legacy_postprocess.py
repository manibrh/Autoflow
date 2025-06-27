import os
import json
import xml.etree.ElementTree as ET

def read_json(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def write_json(data, file_path):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def read_properties(file_path):
    data = {}
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip() and not line.startswith('#') and '=' in line:
                key, val = line.split('=', 1)
                data[key.strip()] = val.strip()
    return data

def write_properties(data, file_path):
    with open(file_path, 'w', encoding='utf-8') as f:
        for k, v in data.items():
            f.write(f"{k}={v}\n")

def read_xliff(file_path):
    tree = ET.parse(file_path)
    root = tree.getroot()
    file_node = root.find(".//file")
    original_name = file_node.attrib.get('original')
    target_lang = file_node.attrib.get('target-language', 'xx')
    ext = os.path.splitext(original_name)[1].lower()
    translations = {}

    for tu in root.findall(".//trans-unit"):
        key = tu.attrib.get('resname')
        value = tu.findtext('target') or tu.findtext('source')
        translations[key] = value

    return translations, original_name, target_lang

def run_legacy_postprocessing(input_dir, output_dir):
    for filename in os.listdir(input_dir):
        if filename.endswith('.xliff'):
            xliff_path = os.path.join(input_dir, filename)
            translations, original_name, lang_code = read_xliff(xliff_path)

            ext = os.path.splitext(original_name)[1].lower()
            output_file = os.path.join(output_dir, lang_code, os.path.basename(original_name))
            os.makedirs(os.path.dirname(output_file), exist_ok=True)

            if ext == '.json':
                original = read_json(output_file) if os.path.exists(output_file) else {}
                for k in translations:
                    if k in original:
                        original[k] = translations[k]
                write_json(original, output_file)

            elif ext == '.properties':
                original = read_properties(output_file) if os.path.exists(output_file) else {}
                for k in translations:
                    if k in original:
                        original[k] = translations[k]
                write_properties(original, output_file)
