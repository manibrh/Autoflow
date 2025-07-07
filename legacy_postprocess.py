import os
import json
import zipfile
import xml.etree.ElementTree as ET
import langcodes

XLIFF_NS = {
    '1.2': {'ns': 'urn:oasis:names:tc:xliff:document:1.2'},
    '2.0': {'ns': 'urn:oasis:names:tc:xliff:document:2.0'}
}

def read_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def write_json(data, path):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def read_properties(path):
    data = {}
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                k, v = line.split('=', 1)
                data[k.strip()] = v.strip()
    return data

def write_properties(data, path):
    with open(path, 'w', encoding='utf-8') as f:
        for k, v in data.items():
            f.write(f"{k}={v}\n")

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
        translations = {}

        for tu in root.findall(f".//{{{ns}}}trans-unit"):
            key = tu.attrib.get('resname')
            tgt = tu.find(f"{{{ns}}}target")
            src = tu.find(f"{{{ns}}}source")
            val = (tgt.text if tgt is not None and tgt.text else
                   src.text if src is not None else "")
            translations[key] = val

    elif version == '2.0':
        ns = XLIFF_NS['2.0']['ns']
        target_lang = root.attrib.get('trgLang', 'xx')
        file_node = root.find(f".//{{{ns}}}file")
        original_name = file_node.attrib.get('id')
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

def run_legacy_postprocessing(input_dir, output_dir):
    renamed_files = []
    for fname in os.listdir(input_dir):
        if fname.endswith('.xliff'):
            fpath = os.path.join(input_dir, fname)
            translations, original_name, lang_code = read_xliff(fpath)

            ext = os.path.splitext(original_name)[1].lower()
            base = os.path.splitext(os.path.basename(original_name))[0]
            lang_name = langcodes.get(lang_code).language_name().title()
            lang_folder = os.path.join(output_dir, lang_code)
            os.makedirs(lang_folder, exist_ok=True)

            renamed_file = f"{base}-{lang_name}{ext}"
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
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for root, _, files in os.walk(output_dir):
            for f in files:
                if f != "batch.zip":
                    full = os.path.join(root, f)
                    arc = os.path.relpath(full, output_dir)
                    zipf.write(full, arc)

    return renamed_files
