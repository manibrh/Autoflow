import os
import re
import xml.etree.ElementTree as ET

def read_json_raw(file_path):
    raw_lines = {}
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            match = re.match(r'\s*"([^"]+)"\s*:\s*"((?:[^"\\]|\\.)*)"\s*,?\s*$', line)
            if match:
                key, val = match.groups()
                raw_lines[key] = val
    return raw_lines

def read_properties(file_path):
    data = {}
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip() and not line.startswith('#') and '=' in line:
                key, val = line.split('=', 1)
                data[key.strip()] = val.strip()
    return data

def write_xliff(data, input_file, output_file, src_lang='en', tgt_lang='fr', version='1.2'):
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    if version == '1.2':
        xliff = ET.Element('xliff', {'version': '1.2'})
        file_tag = ET.SubElement(xliff, 'file', {
            'source-language': src_lang,
            'target-language': tgt_lang,
            'datatype': 'plaintext',
            'original': os.path.basename(input_file)
        })
        body = ET.SubElement(file_tag, 'body')

        for i, (key, value) in enumerate(data.items(), start=1):
            tu = ET.SubElement(body, 'trans-unit', {'id': str(i), 'resname': key})

            # Raw-preserve <source>
            source = ET.SubElement(tu, 'source')
            source.text = None
            tu.remove(source)
            tu.append(ET.fromstring(f"<source>{value}</source>"))

            ET.SubElement(tu, 'target').text = ''

        tree = ET.ElementTree(xliff)

    elif version == '2.0':
        ns = "urn:oasis:names:tc:xliff:document:2.0"
        ET.register_namespace('', ns)
        xliff = ET.Element(f'{{{ns}}}xliff', {
            'version': '2.0',
            'srcLang': src_lang,
            'trgLang': tgt_lang
        })
        file_tag = ET.SubElement(xliff, f'{{{ns}}}file', {
            'id': os.path.basename(input_file)
        })

        for i, (key, value) in enumerate(data.items(), start=1):
            unit = ET.SubElement(file_tag, f'{{{ns}}}unit', {'id': str(i)})
            segment = ET.SubElement(unit, f'{{{ns}}}segment')

            src = ET.SubElement(segment, f'{{{ns}}}source')
            src.text = value

            ET.SubElement(segment, f'{{{ns}}}target').text = ''

        tree = ET.ElementTree(xliff)

    else:
        raise ValueError("Unsupported XLIFF version. Use '1.2' or '2.0'.")

    tree.write(output_file, encoding='utf-8', xml_declaration=True)

def run_tep_preprocessing(input_dir, output_dir, version='1.2'):
    for filename in os.listdir(input_dir):
        full_path = os.path.join(input_dir, filename)
        base, ext = os.path.splitext(filename)
        if ext.lower() == '.json':
            data = read_json_raw(full_path)
        elif ext.lower() == '.properties':
            data = read_properties(full_path)
        else:
            continue
        output_file = os.path.join(output_dir, f"{base}.xliff")
        write_xliff(data, full_path, output_file, version=version)
