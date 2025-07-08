import os
import re
import zipfile
import xml.etree.ElementTree as ET
import langcodes

def read_json_raw(path):
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

    if root.tag.startswith('{'):
        ns_match = re.match(r'\{(.*)\}', root.tag)
        ns_uri = ns_match.group(1) if ns_match else ''
        ns = {'ns': ns_uri}
        file_xpath = ".//ns:file"
        trans_unit_xpath = ".//ns:trans-unit"
        source_xpath = "ns:source"
        target_xpath = "ns:target"
    else:
        ns = {}
        file_xpath = ".//file"
        trans_unit_xpath = ".//trans-unit"
        source_xpath = "source"
        target_xpath = "target"

    file_node = root.find(file_xpath, namespaces=ns)
    if file_node is None:
        raise Exception(f"❌ XLIFF: <file> element not found in {file_path}")
    
    original_name = file_node.attrib.get('original', os.path.basename(file_path))
    target_lang = file_node.attrib.get('target-language', 'xx')
    translations = {}

    for tu in root.findall(trans_unit_xpath, namespaces=ns):
        key = tu.attrib.get('resname')
        if not key:
            continue
        target_elem = tu.find(target_xpath, namespaces=ns)
        source_elem = tu.find(source_xpath, namespaces=ns)
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

            # 🧹 Remove language suffixes like -en, _en_US, -ta-IN
            base_name = re.sub(r'[-_](en|[a-z]{2}(?:[-_][A-Z]{2})?)$', '', base_name, flags=re.IGNORECASE)

            try:
                lang_name = langcodes.get(lang_code).language_name().title()
            except:
                lang_name = lang_code  # fallback to raw code

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

    if renamed_files:
        zip_path = os.path.join(output_dir, "batch.zip")
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file in renamed_files:
                zipf.write(os.path.join(output_dir, file), arcname=file)
        print(f"📦 batch.zip created with {len(renamed_files)} files.")
    else:
        print("⚠️ No output files generated.")

    return renamed_files
