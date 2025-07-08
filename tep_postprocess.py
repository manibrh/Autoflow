import os
import json
import zipfile
import xml.etree.ElementTree as ET
import langcodes

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

def write_output(translations, original_name, lang_code, output_dir):
    lang_name = langcodes.get(lang_code).language_name().title()
    lang_folder = os.path.join(output_dir, lang_code)
    os.makedirs(lang_folder, exist_ok=True)

    base_name = os.path.splitext(original_name)[0]
    ext = os.path.splitext(original_name)[1].lower()
    output_file = f"{base_name}-{lang_name}{ext}"
    output_path = os.path.join(lang_folder, output_file)

    # Unescape function to normalize backslashes and quotes
    def unescape_text(text):
        try:
            return text.encode('utf-8').decode('unicode_escape')
        except:
            return text

    if ext == ".json":
        cleaned_translations = {
            k: unescape_text(v) for k, v in translations.items()
        }
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(cleaned_translations, f, indent=4, ensure_ascii=False)

    elif ext == ".properties":
        with open(output_path, 'w', encoding='utf-8') as f:
            for k, v in translations.items():
                cleaned_val = unescape_text(v).replace('\n', '\\n')
                # Escape = and : for properties format
                cleaned_val = cleaned_val.replace('=', '\\=').replace(':', '\\:')
                f.write(f"{k}={cleaned_val}\n")

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
