import os
import json
import re
import tempfile
import pandas as pd
import zipfile
import uuid
from datetime import datetime

PLACEHOLDER_PATTERN = re.compile(
    r'\?"\{[^{}]+\}\?"|'    # quoted placeholders
    r'\{\d+\}|'             
    r'\{\{.*?\}\}|'         
    r'\{[^{}]+\}|'          
    r'<[^>]+>|'             
    r'%\w+|'                
    r'\$\w+'                
)

SPACING_RULES = [
    (re.compile(r'[\u0B80-\u0BFF][{]{2}'), "Missing space before placeholder"),
    (re.compile(r'[}]{2}[\u0B80-\u0BFF]'), "Missing space after placeholder"),
    (re.compile(r'[.!?:][^\s{<]'), "Missing space after punctuation"),
    (re.compile(r'}}[^\s{<]'), "Missing space after closing tag"),
    (re.compile(r'\d[\u0B80-\u0BFF\w]'), "Missing space between number and word")
]

def clean_filename_for_match(name):
    base = os.path.splitext(name)[0]
    base = re.sub(r'\s*\(\d+\)$', '', base)
    base = re.sub(r'[-_](?:[a-z]{2}(?:-[A-Z]{2})?|[A-Za-z]+)$', '', base)
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
    except json.JSONDecodeError as e:
        recovered = {}
        explanation = str(e)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                raw_text = f.read()
                matches = re.findall(r'"([^"]+)"\s*:\s*"((?:[^"\\]|\\.)*)"', raw_text)
                for k, v in matches:
                    recovered[k] = v.encode('utf-8').decode('unicode_escape')
            return recovered, f"Partial recovery due to JSON error: {explanation}"
        except Exception as inner:
            return None, f"Unrecoverable JSON error: {explanation} / {inner}"

def check_spacing_mismatches(src_str, tgt_str):
    issues = []
    src_placeholders = PLACEHOLDER_PATTERN.findall(src_str)
    for ph in src_placeholders:
        if ph in tgt_str:
            idx = tgt_str.find(ph)
            if idx > 0 and tgt_str[idx - 1].isalnum():
                issues.append(("Spacing Mismatch", f"No space before {ph}"))
            if idx + len(ph) < len(tgt_str) and tgt_str[idx + len(ph)].isalnum():
                issues.append(("Spacing Mismatch", f"No space after {ph}"))

    for pattern, label in SPACING_RULES:
        if pattern.search(tgt_str):
            issues.append(("Spacing Mismatch", label))

    return list(set(issues))

def compare_files(source_data, translated_data, lang, file_name):
    report_data = []
    all_keys = set(source_data.keys()).union(translated_data.keys())

    for key in all_keys:
        issues = []
        src_val = source_data.get(key, "")
        tgt_val = translated_data.get(key, "")

        if key not in source_data:
            issues.append(("Extra Key", "Key is present in target but missing in source."))
        elif key not in translated_data:
            issues.append(("Missing Key", "Key is present in source but missing in target."))
        elif isinstance(src_val, str) != isinstance(tgt_val, str):
            issues.append(("Quote Structure Mismatch", "Source and target value types do not match."))
        else:
            src_str = str(src_val).strip()
            tgt_str = str(tgt_val).strip()

            if src_str == tgt_str:
                issues.append(("Untranslated Key", "Source and target values are identical."))
            elif set(PLACEHOLDER_PATTERN.findall(src_str)) != set(PLACEHOLDER_PATTERN.findall(tgt_str)):
                issues.append(("Placeholder Mismatch", "Mismatch in placeholder usage."))
            else:
                issues.extend(check_spacing_mismatches(src_str, tgt_str))

        for issue_type, detail in issues:
            report_data.append({
                "File Name": file_name,
                "Language": lang,
                "Issue Type": issue_type,
                "Key": key,
                "Source": src_val,
                "Target": tgt_val,
                "Details": detail
            })

    if not report_data:
        report_data.append({
            "File Name": file_name,
            "Language": lang,
            "Issue Type": "No issues found",
            "Key": "", "Source": "", "Target": "", "Details": ""
        })

    return report_data

def run_final_comparison_from_zip(source_files, translated_zip_file):
    all_report_rows = []
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
            data, err = None, f"Unsupported file type: {ext}"

        if err:
            all_report_rows.append({
                "File Name": filename,
                "Language": "",
                "Issue Type": "Source Error",
                "Key": err,
                "Source": "", "Target": "", "Details": ""
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
                    all_report_rows.append({
                        "File Name": file,
                        "Language": lang,
                        "Issue Type": "No matching source file",
                        "Key": file,
                        "Source": "", "Target": "", "Details": ""
                    })
                    continue

            if ext == '.json':
                tgt_data, err = load_json_from_path(tgt_path)
            elif ext == '.properties':
                tgt_data, err = load_properties_from_path(tgt_path)
            else:
                tgt_data, err = None, f"Unsupported file type: {ext}"

            if err:
                all_report_rows.append({
                    "File Name": file,
                    "Language": lang,
                    "Issue Type": "Target Error",
                    "Key": err,
                    "Source": "", "Target": "", "Details": "File partially parsed for issue analysis." if tgt_data else ""
                })
                if not tgt_data:
                    continue

            issues = compare_files(source_data, tgt_data, lang, file)
            all_report_rows.extend(issues)

    token = str(uuid.uuid4())
    date_str = datetime.now().strftime("%d-%b-%Y")
    report_name = f"Comparison_Report_{date_str}.xlsx"
    output_path = os.path.join(tempfile.gettempdir(), f"{token}__{report_name}")

    df = pd.DataFrame(all_report_rows)
    with pd.ExcelWriter(output_path, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Report', index=False)
        workbook = writer.book
        worksheet = writer.sheets['Report']
        wrap_format = workbook.add_format({'text_wrap': True, 'valign': 'top'})
        for i, col in enumerate(df.columns):
            width = max(df[col].astype(str).map(len).max(), len(col)) + 5
            worksheet.set_column(i, i, width, wrap_format)

    return output_path, token, report_name, all_report_rows
