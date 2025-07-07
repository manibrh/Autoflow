import os
import json
import zipfile
import xml.etree.ElementTree as ET
import langcodes

XLIFF_NS = {
    '1.2': {'ns': 'urn:oasis:names:tc:xliff:document:1.2'},
    '2.0': {'ns': 'urn:oasis:names:tc:xliff:document:2.0'}
}

def read_xliff(file_path):
    tree = ET.parse(file_path)
    root = tree.getroot()

    if root.tag.endswith('xliff') and 'version' in root.attrib:
        version = root.attrib['version']
    else:
        raise ValueError("Unknown XLIFF format")

    if version == '1.2':
        ns = XLIFF_NS['1.2']['ns']
        file_node = root.find(f".//{{{ns}}}file")
        original_name = file_node.attrib.get('original')
        target_lang = file_node.attrib.get('target-language', 'xx')
        ext = os.path.splitext(original_name)[1].lower()
        translations = {}

        for tu in root.findall(f".//{{{ns}}}trans-unit"):
            key = tu.attrib.get('resname')
            tgt = tu.find(f"{{{ns}}}target")
            src = tu.find(f"{{{ns}}}source")
            value = (tgt.text if tgt is not None and tgt.text else
                     src.text if src is not None else "")
            translations[key] = value

    elif version == '2.0':
        ns = XLIFF_NS['2.0']['ns']
        target_lang = root.attrib.get('trgLang', 'xx')
        file_node = root.find(f".//{{{ns}}}file")
        original_name = file_node.attrib.get('id')
        ext = os.path.splitext(original_name)[1].lower()
        translations = {}

        for unit in root.findall(f".//{{{ns}}}unit"):
            seg = unit.find(f".//{{{ns}}}segment")
            src = seg.find(f"{{{ns}}}source")
            tgt = seg.find(f"{{{ns}}}target")
            key = unit.attrib.get("id")
            value = (tgt.text if tgt is not None and tgt.text else
                     src.text if src is not None else "")
            translations[key] = value

    else:
        raise ValueError("Unsupported XLIFF version")

    return translations, original_name, target_lang

def write_output(translations, original_name, lang_code, output_dir):
    lang_name = langcodes.get(lang_code).language_name().title()
    base_name = os.path.splitext(original_name)[0]
    ext = os.path.splitext(original_name)[1].lower()

    lang_folder = os.path.join(output_dir, lang_code)
    os.makedirs(lang_folder, exist_ok=True)

    output_path = os.path.join(lang_folder, f"{base_name}-{lang_name}{ext}")

    if ext == ".json":
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(translations, f, ensure_ascii=False, indent=4)
    elif ext == ".properties":
        with open(output_path, 'w', encoding='utf-8') as f:
            for k, v in translations.items():
                f.write(f"{k}={v}\n")

    return os.path.relpath(output_path, output_dir)

def run_tep_postprocessing(input_dir, output_dir):
    renamed_files = []
    for fname in os.listdir(input_dir):
        if fname.endswith('.xliff'):
            fpath = os.path.join(input_dir, fname)
            translations, original_name, lang_code = read_xliff(fpath)
            rel = write_output(translations, original_name, lang_code, output_dir)
            renamed_files.append(rel)

    zip_path = os.path.join(output_dir, "batch.zip")
    with zipfile.ZipFile(zip_path, 'w') as z:
        for root, _, files in os.walk(output_dir):
            for f in files:
                if f != "batch.zip":
                    full = os.path.join(root, f)
                    z.write(full, os.path.relpath(full, output_dir))

    return renamed_files
