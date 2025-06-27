import os
import json
import xml.etree.ElementTree as ET

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

def write_output(translations, original_name, lang_code, output_dir):
    lang_dir = os.path.join(output_dir, lang_code)
    os.makedirs(lang_dir, exist_ok=True)

    base_name = os.path.splitext(original_name)[0]
    ext = os.path.splitext(original_name)[1].lower()
    output_path = os.path.join(lang_dir, f"{base_name}{ext}")

    if ext == ".json":
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(translations, f, indent=4, ensure_ascii=False)
    elif ext == ".properties":
        with open(output_path, 'w', encoding='utf-8') as f:
            for k, v in translations.items():
                f.write(f"{k}={v}\n")

def run_tep_postprocessing(input_dir, output_dir):
    for filename in os.listdir(input_dir):
        if filename.endswith('.xliff'):
            xliff_path = os.path.join(input_dir, filename)
            translations, original_name, target_lang = read_xliff(xliff_path)
            write_output(translations, original_name, target_lang, output_dir)
