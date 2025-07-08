import os
import zipfile
import xml.etree.ElementTree as ET
import langcodes
import re

XLIFF_NS = {'ns': 'urn:oasis:names:tc:xliff:document:1.2'}

def read_json_raw(path):
    """Reads JSON file with tolerant parsing (preserves malformed values)."""
    data = {}
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            match = re.match(r'\s*"([^"]+)"\s*:\s*"(.*)"\s*,?\s*$', line)
            if match:
                key, val = match.groups()
                data[key] = val
            else:
                parts = line.strip().split(":", 1)
                if len(parts) == 2:
                    key = parts[0].strip().strip('"')
                    val = parts[1].strip().rstrip(',').strip()
                    data[key] = val
    return data

def write_json_raw(data, path):
    """Writes JSON with raw values preserved (no escaping)."""
    with open(path, 'w', encoding='utf-8') as f:
        f.write("{\n")
        for i, (k, v) in enumerate(data.items()):
            comma = ',' if i < len(data) - 1 else ''
            f.write(f'  "{k}": "{v}"{comma}\n')
        f.write("}\n")

def read_properties(path):
    data = {}
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip() and not line.startswith('#') and '=' in line:
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
    file_node = root.find(".//ns:file", namespaces=XLIFF_NS)
    if file_node is None:
        raise Exception(f"❌ XLIFF 1.2: <file> element not found in {file_path}")
    
    original_name = file_node.attrib.get('original')
    target_lang = file_node.attrib.get('target-language', 'xx')
    ext = os.path.splitext(original_name)[1].lower()
    translations = {}

    for tu in root.findall(".//ns:trans-unit", namespaces=XLIFF_NS):
        key = tu.attrib.get('resname')
        if not key:
            continue
        target_elem = tu.find("ns:target", namespaces=XLIFF_NS)
        source_elem = tu.find("ns:source", namespaces=XLIFF_NS)
        value = (
            target_elem.text if target_elem is not None and target_elem.text else
            source_elem.text if source_elem is not None else ""
        )
        translations[key] = value

    return translations, original_name, target_lang

def run_legacy_postprocessing(input_dir, output_dir):
    renamed_files = []

    for filename in os.listdir(input_dir):
        if filename.endswith('.xliff'):
            xliff_path = os.path.join(input_dir, filename)
            try:
                translations, original_name, lang_code = read_xliff(xliff_path)
            except Exception as e:
                print(f"❌ Error parsing {filename}: {e}")
                continue

            ext = os.path.splitext(original_name)[1].lower()
            base_name = os.path.splitext(os.path.basename(original_name))[0]
            lang_name = langcodes.get(lang_code).language_name().title()
            lang_folder = os.path.join(output_dir, lang_code)
            os.makedirs(lang_folder, exist_ok=True)

            renamed_file = f"{base_name}-{lang_name}{ext}"
            output_path = os.path.join(lang_folder, renamed_file)

            print(f"✅ Writing: {output_path} ({len(translations)} entries)")

            if ext == ".json":
                write_json_raw(translations, output_path)
            elif ext == ".properties":
                write_properties(translations, output_path)
            else:
                print(f"⚠️ Unsupported extension: {ext}")
                continue

            renamed_files.append(os.path.relpath(output_path, output_dir))

    # Create batch.zip if any files were written
    if renamed_files:
        zip_path = os.path.join(output_dir, "batch.zip")
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(output_dir):
                for file in files:
                    if file != "batch.zip":
                        full_path = os.path.join(root, file)
                        arcname = os.path.relpath(full_path, output_dir)
                        zipf.write(full_path, arcname)
        print(f"📦 batch.zip created with {len(renamed_files)} files.")
    else:
        print("⚠️ No output files generated.")

    return renamed_files
