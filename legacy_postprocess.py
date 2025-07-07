import os
import json
import zipfile
import xml.etree.ElementTree as ET
import langcodes

XLIFF_NS = {'ns': 'urn:oasis:names:tc:xliff:document:1.2'}

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
    file_node = root.find(".//ns:file", namespaces=XLIFF_NS)
    original_name = file_node.attrib.get('original')
    target_lang = file_node.attrib.get('target-language', 'xx')
    ext = os.path.splitext(original_name)[1].lower()
    translations = {}

    for tu in root.findall(".//ns:trans-unit", namespaces=XLIFF_NS):
        key = tu.attrib.get('resname')
        target_elem = tu.find("ns:target", namespaces=XLIFF_NS)
        source_elem = tu.find("ns:source", namespaces=XLIFF_NS)
        value = (target_elem.text if target_elem is not None and target_elem.text else
                 source_elem.text if source_elem is not None else "")
        translations[key] = value

    return translations, original_name, target_lang

def run_legacy_postprocessing(input_dir, output_dir):
    renamed_files = []
    for filename in os.listdir(input_dir):
        if filename.endswith('.xliff'):
            xliff_path = os.path.join(input_dir, filename)
            translations, original_name, lang_code = read_xliff(xliff_path)

            ext = os.path.splitext(original_name)[1].lower()
            base_name = os.path.splitext(os.path.basename(original_name))[0]
            lang_name = langcodes.get(lang_code).language_name().title()
            lang_folder = os.path.join(output_dir, lang_code)
            os.makedirs(lang_folder, exist_ok=True)

            renamed_file = f"{base_name}-{lang_name}{ext}"
            output_path = os.path.join(lang_folder, renamed_file)

            if ext == '.json':
                original = read_json(output_path) if os.path.exists(output_path) else {}
                for k in translations:
                    if k in original:
                        original[k] = translations[k]
                write_json(original, output_path)

            elif ext == '.properties':
                original = read_properties(output_path) if os.path.exists(output_path) else {}
                for k in translations:
                    if k in original:
                        original[k] = translations[k]
                write_properties(original, output_path)

            renamed_files.append(os.path.relpath(output_path, output_dir))

    zip_path = os.path.join(output_dir, "batch.zip")
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(output_dir):
            for file in files:
                if file != "batch.zip":
                    full_path = os.path.join(root, file)
                    arcname = os.path.relpath(full_path, output_dir)
                    zipf.write(full_path, arcname)

    return renamed_files
