import os
import json
import re
import tempfile
import pandas as pd
import zipfile
import uuid
from datetime import datetime

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

# ✅ Improved matching logic
def clean_filename_for_match(name):
    base = os.path.splitext(name)[0]
    base = re.sub(r'\s*\(\d+\)$', '', base)  # remove (1), (2)
    base = re.sub(r'[-_](?:[a-z]{2}(?:-[A-Z]{2})?|[A-Za-z]+)$', '', base)  # remove lang code or name
    return re.sub(r'[^a-zA-Z0-9]', '', base).lower()

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

def check_spacing_mismatches(src_str, tgt_str):
    # Check for missing spaces before/after placeholders (basic check)
    spacing_issues = []
    src_placeholders = PLACEHOLDER_PATTERN.findall(src_str)
    for ph in src_placeholders:
        if ph in tgt_str:
            idx = tgt_str.find(ph)
            if idx > 0 and tgt_str[idx-1].isalnum():
                spacing_issues.append(ph)
            if idx + len(ph) < len(tgt_str) and tgt_str[idx + len(ph)].isalnum():
                spacing_issues.append(ph)
    return list(set(spacing_issues))

def compare_files(source_data, translated_data, lang, file_name):
    missing_keys, extra_keys = [], []
    placeholder_mismatches, quote_mismatches, untranslated_keys = [], [], []
    spacing_mismatches = []

    for key in source_data:
        if key not in translated_data:
            missing_keys.append(key)
        else:
            src_val, tgt_val = source_data[key], translated_data[key]
            if isinstance(src_val, str) != isinstance(tgt_val, str):
                quote_mismatches.append(key)
            src_str, tgt_str = str(src_val).strip(), str(tgt_val).strip()
            if src_str == tgt_str:
                untranslated_keys.append(key)
            if set(PLACEHOLDER_PATTERN.findall(src_str)) != set(PLACEHOLDER_PATTERN.findall(tgt_str)):
                placeholder_mismatches.append(key)
            if check_spacing_mismatches(src_str, tgt_str):
                spacing_mismatches.append(key)

    for key in translated_data:
        if key not in source_data:
            extra_keys.append(key)

    return {
        "Language": lang,
        "File Name": file_name,
        "Error Type": "" if not any([missing_keys, extra_keys, placeholder_mismatches, quote_mismatches, untranslated_keys, spacing_mismatches]) else "File Issues",
        "Error Details": "No issues found" if not any([missing_keys, extra_keys, placeholder_mismatches, quote_mismatches, untranslated_keys, spacing_mismatches]) else "",
        "Missing Keys": ", ".join(missing_keys),
        "Extra Keys": ", ".join(extra_keys),
        "Placeholder Mismatches": ", ".join(placeholder_mismatches),
        "Quote Structure Mismatches": ", ".join(quote_mismatches),
        "Untranslated Keys": ", ".join(untranslated_keys),
        "Spacing Mismatches": ", ".join(spacing_mismatches)
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
        ext = os.path.splitext(filename)[1].lower()
        cleaned = f"{clean_filename_for_match(filename)}{ext}"
        path = os.path.join(temp_dir, filename)
        src.save(path)

        if ext == '.json':
            data, err = load_json_from_path(path)
        elif ext == '.properties':
            data, err = load_properties_from_path(path)
        else:
            err = f"Unsupported file type: {ext}"
            data = None

        if err:
            report_data.append({
                "File Name": filename,
                "Language": "",
                "Error Type": "Source Error",
                "Error Details": err,
                "Missing Keys": "", "Extra Keys": "", "Placeholder Mismatches": "",
                "Quote Structure Mismatches": "", "Untranslated Keys": "", "Spacing Mismatches": ""
            })
            continue

        source_map[cleaned] = (filename, data)

    for lang in os.listdir(translated_dir):
        lang_path = os.path.join(translated_dir, lang)
        if not os.path.isdir(lang_path):
            continue

        for file in os.listdir(lang_path):
            tgt_path = os.path.join(lang_path, file)
            ext = os.path.splitext(file)[1].lower()
            cleaned_tgt = f"{clean_filename_for_match(file)}{ext}"

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
                        "File Name": file,
                        "Language": lang,
                        "Error Type": "No matching source file",
                        "Error Details": f"{file} unmatched",
                        "Missing Keys": "", "Extra Keys": "", "Placeholder Mismatches": "",
                        "Quote Structure Mismatches": "", "Untranslated Keys": "", "Spacing Mismatches": ""
                    })
                    continue

            if ext == '.json':
                tgt_data, err = load_json_from_path(tgt_path)
            elif ext == '.properties':
                tgt_data, err = load_properties_from_path(tgt_path)
            else:
                err = f"Unsupported file type: {ext}"
                tgt_data = None

            if err:
                report_data.append({
                    "File Name": file,
                    "Language": lang,
                    "Error Type": "Target Error",
                    "Error Details": err,
                    "Missing Keys": "", "Extra Keys": "", "Placeholder Mismatches": "",
                    "Quote Structure Mismatches": "", "Untranslated Keys": "", "Spacing Mismatches": ""
                })
                continue

            result = compare_files(source_data, tgt_data, lang, file)
            report_data.append(result)

    # Save report
    token = str(uuid.uuid4())
    date_str = datetime.now().strftime("%d-%b-%Y")
    report_name = f"Comparison_Report_{date_str}.xlsx"
    output_path = os.path.join(tempfile.gettempdir(), f"{token}__{report_name}")
    pd.DataFrame(report_data).to_excel(output_path, index=False)

    return output_path, token, report_name, report_data
