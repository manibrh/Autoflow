import os
import json
import xml.etree.ElementTree as ET

def read_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def read_properties(path):
    data = {}
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip() and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                data[k.strip()] = v.strip()
    return data

def write_xliff(data_keys, input_file, output_file, src_lang='en', tgt_lang='xx', src_data=None, tgt_data=None):
    xliff = ET.Element('xliff', {'version': '1.2'})
    file_tag = ET.SubElement(xliff, 'file', {
        'source-language': src_lang,
        'target-language': tgt_lang,
        'datatype': 'plaintext',
        'original': os.path.basename(input_file)
    })
    body = ET.SubElement(file_tag, 'body')

    for i, key in enumerate(data_keys, start=1):
        tu = ET.SubElement(body, 'trans-unit', {'id': str(i), 'resname': key})
        ET.SubElement(tu, 'source').text = src_data.get(key, '')
        ET.SubElement(tu, 'target').text = tgt_data.get(key, '')

    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    ET.ElementTree(xliff).write(output_file, encoding='utf-8', xml_declaration=True)

def run_legacy_preprocessing(input_dir, output_dir):
    errors = []

    source_files = {
        f.replace("source_", ""): os.path.join(input_dir, f)
        for f in os.listdir(input_dir)
        if f.startswith("source_") and os.path.isfile(os.path.join(input_dir, f))
    }

    targets_root = os.path.join(input_dir, "targets")
    if not os.path.exists(targets_root):
        raise Exception("Target ZIP not extracted or missing.")

    for lang_code in os.listdir(targets_root):
        lang_folder = os.path.join(targets_root, lang_code)
        if not os.path.isdir(lang_folder):
            continue

        for base_name, source_path in source_files.items():
            target_path = os.path.join(lang_folder, base_name)
            if not os.path.exists(target_path):
                errors.append(f"❌ Missing target for {base_name} in {lang_code}")
                continue

            ext = os.path.splitext(base_name)[1].lower()
            try:
                if ext == '.json':
                    try:
                        src_data = read_json(source_path)
                        tgt_data = read_json(target_path)
                    except Exception as e:
                        errors.append(f"❌ JSON read error in {lang_code}/{base_name}: {str(e)}")
                        continue
                elif ext == '.properties':
                    src_data = read_properties(source_path)
                    tgt_data = read_properties(target_path)
                else:
                    errors.append(f"❌ Unsupported file type: {base_name}")
                    continue

                common_keys = [k for k in src_data if k in tgt_data]
                if not common_keys:
                    errors.append(f"⚠️ No common keys found in {base_name} ({lang_code})")
                    continue

                output_file = os.path.join(output_dir, lang_code, base_name.replace(ext, ".xliff"))
                write_xliff(
                    data_keys=common_keys,
                    input_file=target_path,
                    output_file=output_file,
                    tgt_lang=lang_code,
                    src_data=src_data,
                    tgt_data=tgt_data
                )

            except Exception as e:
                errors.append(f"❌ Failed processing {base_name} in {lang_code}: {str(e)}")

    return errors
