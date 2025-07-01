import os
import json
import re
import tempfile
import pandas as pd
import zipfile
import uuid

PLACEHOLDER_PATTERN = re.compile(
    r'\\?"\{[^{}]+\}\\?"|'
    r'\{\d+\}|'
    r'\{\{.*?\}\}|'
    r'\{[^{}]+\}|'
    r'\{[^{}]*|'
    r'<[^>]+>|'
    r'%\w+|'
    r'\$\w+'
)

def clean_filename_for_match(name):
    base = os.path.splitext(name)[0]
    parts = re.split(r'[-_.]', base)
    if len(parts) > 1:
        last = parts[-1]
        if (
            len(last) <= 7 and (
                last.istitle() or last.islower() or re.fullmatch(r'[a-z]{2}(-[A-Z]{2})?', last)
            )
        ):
            parts.pop()
    return '-'.join(parts).lower()

def load_properties_from_path(file_path):
    props = {}
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip() and '=' in line and not line.startswith('#'):
                    key, val = line.split('=', 1)
                    props[key.strip()] = val.strip()
        return props, None
    except Exception as e:
        return None, str(e)

def load_json_from_path(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f), None
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

def run_final_comparison_from_zip(source_files, translated_zip_file):
    report_data = []
    temp_dir = tempfile.mkdtemp()
    translated_dir = os.path.join(temp_dir, "translated")

    with zipfile.ZipFile(translated_zip_file, 'r') as zip_ref:
        zip_ref.extractall(translated_dir)

    source_map = {}
    for src in source_files:
        filename = src.filename
        cleaned = clean_filename_for_match(filename)
        ext = os.path.splitext(filename)[1]
        path = os.path.join(temp_dir, filename)
        src.save(path)

        data, err = (load_json_from_path(path) if ext == '.json' else load_properties_from_path(path))
        if err:
            report_data.append({
                "File Name": filename, "Language": "", "Error Type": "Source Error", "Error Details": err,
                "Missing Keys": "", "Extra Keys": "", "Placeholder Mismatches": "",
                "Quote Structure Mismatches": "", "Untranslated Keys": ""
            })
            continue
        source_map[cleaned] = (filename, data)

    for lang in os.listdir(translated_dir):
        lang_path = os.path.join(translated_dir, lang)
        if not os.path.isdir(lang_path):
            continue
        for file in os.listdir(lang_path):
            tgt_path = os.path.join(lang_path, file)
            cleaned_tgt = clean_filename_for_match(file)
            ext = os.path.splitext(file)[1]

            if cleaned_tgt in source_map:
                src_filename, source_data = source_map[cleaned_tgt]
            else:
                matched = False
                for key in source_map:
                    if cleaned_tgt in key or key in cleaned_tgt:
                        src_filename, source_data = source_map[key]
                        matched = True
                        break
                if not matched:
                    report_data.append({
                        "File Name": file, "Language": lang, "Error Type": "No matching source file",
                        "Error Details": f"{file} unmatched",
                        "Missing Keys": "", "Extra Keys": "", "Placeholder Mismatches": "",
                        "Quote Structure Mismatches": "", "Untranslated Keys": ""
                    })
                    continue

            tgt_data, err = (load_json_from_path(tgt_path) if ext == '.json' else load_properties_from_path(tgt_path))
            if err:
                report_data.append({
                    "File Name": file, "Language": lang, "Error Type": "Target Error",
                    "Error Details": err,
                    "Missing Keys": "", "Extra Keys": "", "Placeholder Mismatches": "",
                    "Quote Structure Mismatches": "", "Untranslated Keys": ""
                })
                continue

            result = compare_files(source_data, tgt_data, lang, file)
            report_data.append(result)

    # Save to temp file with UUID token
    token = str(uuid.uuid4())
    output_path = os.path.join(tempfile.gettempdir(), f"{token}.xlsx")
    pd.DataFrame(report_data).to_excel(output_path, index=False)
    return output_path, token
