# utils/final_compare.py (upload-based)
import os
import json
import re
import tempfile
import pandas as pd
from werkzeug.datastructures import FileStorage

PLACEHOLDER_PATTERN = re.compile(
    r'\?"\{[^{}]+\}\?"|'  # Matches "{placeholder}"
    r'\{\d+\}|'             # Matches {0}, {1}
    r'\{\{.*?\}\}|'        # Matches {{placeholder}}
    r'\{[^{}]+\}|'          # Matches {placeholder}
    r'\{[^{}]*|'             # Incomplete
    r'<[^>]+>|'              # <tag>
    r'%\w+|'                 # %s
    r'\$\w+'                # $variable
)

def load_properties(file: FileStorage):
    props = {}
    try:
        lines = file.read().decode('utf-8').splitlines()
        for line_number, line in enumerate(lines, start=1):
            line = line.strip()
            if line and not line.startswith('#'):
                if '=' not in line:
                    raise ValueError(f"Invalid format at line {line_number}")
                key, value = line.split('=', 1)
                props[key.strip()] = value.strip()
        file.seek(0)
        return props, None
    except Exception as e:
        return None, str(e)

def load_json(file: FileStorage):
    try:
        return json.load(file), None
    except Exception as e:
        return None, str(e)

def compare_files(source_data, translated_data, lang, file_name):
    missing_keys, extra_keys = [], []
    placeholder_mismatches, quote_mismatches, untranslated_keys = [], [], []

    for key in source_data:
        if key not in translated_data:
            missing_keys.append(key)
        else:
            src_val, trans_val = source_data[key], translated_data[key]
            if isinstance(src_val, str) != isinstance(trans_val, str):
                quote_mismatches.append(key)
            src_str, trans_str = str(src_val).strip(), str(trans_val).strip()
            if src_str == trans_str:
                untranslated_keys.append(key)
            if set(PLACEHOLDER_PATTERN.findall(src_str)) != set(PLACEHOLDER_PATTERN.findall(trans_str)):
                placeholder_mismatches.append(key)

    for key in translated_data:
        if key not in source_data:
            extra_keys.append(key)

    return {
        "Language": lang,
        "File Name": file_name,
        "Error Type": "",
        "Error Details": "No issues found" if not any([missing_keys, extra_keys, placeholder_mismatches, quote_mismatches, untranslated_keys]) else "",
        "Missing Keys": ", ".join(missing_keys),
        "Extra Keys": ", ".join(extra_keys),
        "Placeholder Mismatches": ", ".join(placeholder_mismatches),
        "Quote Structure Mismatches": ", ".join(quote_mismatches),
        "Untranslated Keys": ", ".join(untranslated_keys)
    }

def run_final_comparison_from_uploads(source_files, translated_files):
    report_data = []
    temp_dir = tempfile.mkdtemp()

    # Map uploaded translated files by filename
    translated_map = {f.filename: f for f in translated_files}

    for src in source_files:
        file_name = src.filename
        if not file_name.endswith(('.json', '.properties')):
            continue

        if file_name not in translated_map:
            report_data.append({"File Name": file_name, "Language": "", "Error Type": "Missing Target File", "Error Details": f"{file_name} not uploaded in target", "Missing Keys": "", "Extra Keys": "", "Placeholder Mismatches": "", "Quote Structure Mismatches": "", "Untranslated Keys": ""})
            continue

        tgt = translated_map[file_name]

        # Load source
        if file_name.endswith('.json'):
            source_data, err = load_json(src)
            if err:
                report_data.append({"File Name": file_name, "Language": "", "Error Type": "JSON Error", "Error Details": err, "Missing Keys": "", "Extra Keys": "", "Placeholder Mismatches": "", "Quote Structure Mismatches": "", "Untranslated Keys": ""})
                continue
            translated_data, t_err = load_json(tgt)
        else:
            source_data, err = load_properties(src)
            if err:
                report_data.append({"File Name": file_name, "Language": "", "Error Type": "Properties Error", "Error Details": err, "Missing Keys": "", "Extra Keys": "", "Placeholder Mismatches": "", "Quote Structure Mismatches": "", "Untranslated Keys": ""})
                continue
            translated_data, t_err = load_properties(tgt)

        if t_err:
            report_data.append({"File Name": file_name, "Language": "", "Error Type": "Target File Error", "Error Details": t_err, "Missing Keys": "", "Extra Keys": "", "Placeholder Mismatches": "", "Quote Structure Mismatches": "", "Untranslated Keys": ""})
            continue

        result = compare_files(source_data, translated_data, "Uploaded", file_name)
        report_data.append(result)

    output_path = os.path.join(temp_dir, "Comparison_Report.xlsx")
    pd.DataFrame(report_data).to_excel(output_path, index=False)
    return output_path
