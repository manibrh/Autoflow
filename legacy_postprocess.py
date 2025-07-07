import os
import json
import zipfile
import xml.etree.ElementTree as ET
import langcodes

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
    version = root.attrib.get('version')

    translations = {}

    if version == '1.2':
        ns = 'urn:oasis:names:tc:xliff:document:1.2'
        nsmap = {'ns': ns}
        has_namespace = root.tag.startswith("{")

        def q(tag): return f"{{{ns}}}{tag}" if has_namespace else tag

        file_node = root.find(q("file"))
        if file_node is None:
            raise ValueError("❌ XLIFF 1.2: <file> element not found")

        original_name = file_node.attrib.get('original')
        target_lang = file_node.attrib.get('target-language', 'xx')

        for tu in root.findall(f".//{q('trans-unit')}"):
            key = tu.attrib.get('resname')
            if not key:
                continue
            tgt = tu.find(q("target"))
            src = tu.find(q("source"))
            val = ''.join(tgt.itertext()) if tgt is not None else ''.join(src.itertext()) if src is not None else ''
            translations[key] = val

    elif version == '2.0':
        ns = 'urn:oasis:names:tc:xliff:document:2.0'
        file_node = root.find(f".//{{{ns}}}file")
        if file_node is None:
            raise ValueError("❌ XLIFF 2.0: <file> element not found")

        original_name = file_node.attrib.get('id')
        target_lang = root.attrib.get('trgLang', 'xx')

        for unit in root.findall(f".//{{{ns}}}unit"):
            key = unit.attrib.get('id')
            if not key:
                continue
            seg = unit.find(f".//{{{ns}}}segment")
            if seg is None:
                continue
            tgt = seg.find(f"{{{ns}}}target")
            src = seg.find(f"{{{ns}}}source")
            val = ''.join(tgt.itertext()) if tgt is not None else ''.join(src.itertext()) if src is not None else ''
            translations[key] = val

    else:
        raise ValueError(f"❌ Unsupported XLIFF version: {version}")

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
