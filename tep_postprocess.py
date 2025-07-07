import os
import json
import zipfile
import xml.etree.ElementTree as ET
import langcodes

XLIFF_NS = {'ns': 'urn:oasis:names:tc:xliff:document:1.2'}

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

def write_output(translations, original_name, lang_code, output_dir):
    lang_name = langcodes.get(lang_code).language_name().title()
    lang_folder = os.path.join(output_dir, lang_code)
    os.makedirs(lang_folder, exist_ok=True)

    base_name = os.path.splitext(original_name)[0]
    ext = os.path.splitext(original_name)[1].lower()
    output_file = f"{base_name}-{lang_name}{ext}"
    output_path = os.path.join(lang_folder, output_file)

    if ext == ".json":
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(translations, f, indent=4, ensure_ascii=False)
    elif ext == ".properties":
        with open(output_path, 'w', encoding='utf-8') as f:
            for k, v in translations.items():
                f.write(f"{k}={v}\n")

    return os.path.relpath(output_path, output_dir)

def run_tep_postprocessing(input_dir, output_dir):
    renamed_files = []
    for filename in os.listdir(input_dir):
        if filename.endswith('.xliff'):
            xliff_path = os.path.join(input_dir, filename)
            translations, original_name, target_lang = read_xliff(xliff_path)
            rel_path = write_output(translations, original_name, target_lang, output_dir)
            renamed_files.append(rel_path)

    zip_path = os.path.join(output_dir, "batch.zip")
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(output_dir):
            for file in files:
                if file != "batch.zip":
                    full_path = os.path.join(root, file)
                    arcname = os.path.relpath(full_path, output_dir)
                    zipf.write(full_path, arcname)

    return renamed_files
