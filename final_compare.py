import os
import json
import re
import tempfile
import pandas as pd
import zipfile
import uuid
from datetime import datetime
from difflib import SequenceMatcher

LANGUAGE_NAMES = set()  # Now dynamically filled from filenames

PLACEHOLDER_PATTERN = re.compile(
    r'\?"\{[^{}]+\}\?"|'
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

def extract_language_from_filename(name):
    parts = re.split(r'[-_]', os.path.splitext(name)[0])
    if parts:
        last_part = parts[-1].lower()
        if re.match(r'^[a-z]{2,3}(-[A-Z]{2})?$', last_part) or last_part.isalpha():
            LANGUAGE_NAMES.add(last_part)
            return last_part
    return "unknown"

def clean_filename_for_match(name):
    base = os.path.splitext(name)[0]
    parts = re.split(r'[-_]', base)
    if parts and parts[-1].lower() in LANGUAGE_NAMES:
        parts.pop()
    elif re.match(r'^[a-z]{2,3}(-[A-Z]{2})?$', parts[-1], re.IGNORECASE):
        parts.pop()
    base = ''.join(parts)
    base = re.sub(r'\d+', '', base)
    return re.sub(r'[^a-zA-Z0-9]', '', base).lower()

def fix_encoding(s):
    try:
        return s.encode('latin1').decode('utf-8')
    except:
        return s

def load_properties_from_path(file_path):
    props = {}
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip() and '=' in line and not line.startswith('#'):
                    key, val = line.split('=', 1)
                    props[key.strip()] = fix_encoding(val.strip())
        return props, None
    except Exception as e:
        return None, str(e)

def load_json_from_path(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f), None
    except json.JSONDecodeError as e:
        explanation = str(e)
        line_info = f"line {e.lineno}, column {e.colno}"
        bad_key = ""

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                if e.lineno - 1 < len(lines):
                    broken_line = lines[e.lineno - 1].strip()
                    key_match = re.search(r'"([^"]+)"\s*:', broken_line)
                    if key_match:
                        bad_key = key_match.group(1)
        except:
            pass

        recovered = {}
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                raw_text = f.read()
                matches = re.findall(r'"([^"]+)"\s*:\s*"((?:[^"\\]|\\.)*)"', raw_text)
                for k, v in matches:
                    recovered[k] = fix_encoding(v)
            return recovered, f"{bad_key} - JSON error at {line_info}: {explanation}"
        except Exception as inner:
            return None, f"Unrecoverable JSON error at {line_info}: {explanation} / {inner}"

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

def check_tag_mismatch(src, tgt):
    issues = []
    src_tags = re.findall(r'</?([a-zA-Z][a-zA-Z0-9]*)[^>]*?>', src)
    tgt_tags = re.findall(r'</?([a-zA-Z][a-zA-Z0-9]*)[^>]*?>', tgt)
    if set(src_tags) != set(tgt_tags):
        issues.append(("HTML Tag Mismatch", f"Tag sets differ. Source: {set(src_tags)}, Target: {set(tgt_tags)}"))
    return issues

def check_partial_translation(src, tgt):
    if len(src) > 10 and len(tgt) > 10:
        ratio = SequenceMatcher(None, src, tgt).ratio()
        if 0.7 <= ratio < 1.0:
            return [("Partial Translation", f"Similarity too high ({int(ratio*100)}%) but not identical.")]
    return []

def check_acronym_mismatch(src, tgt):
    issues = []
    acronyms = re.findall(r'\b[A-Z]{2,}\b', src)
    for ac in acronyms:
        if ac not in tgt:
            issues.append(("Acronym Mismatch", f"Acronym '{ac}' not found in target."))
    return issues

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
            src_str = str(src_val)
            tgt_str = str(tgt_val)

            if src_str == tgt_str:
                issues.append(("Untranslated Key", "Source and target values are identical."))
            elif set(PLACEHOLDER_PATTERN.findall(src_str)) != set(PLACEHOLDER_PATTERN.findall(tgt_str)):
                issues.append(("Placeholder Mismatch", "Mismatch in placeholder usage."))
            else:
                issues.extend(check_spacing_mismatches(src_str, tgt_str))

            issues.extend(check_tag_mismatch(src_str, tgt_str))
            issues.extend(check_partial_translation(src_str, tgt_str))
            if re.search(r'\s{2,}', tgt_str):
                issues.append(("Formatting Issue", "Double spaces found in translation."))
            issues.extend(check_acronym_mismatch(src_str, tgt_str))

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

    # Extract ZIP
    with zipfile.ZipFile(translated_zip_file, 'r') as zip_ref:
        zip_ref.extractall(translated_dir)

    # Load source files
    source_map = {}
    for src in source_files:
        filename = src.filename
        ext = os.path.splitext(filename)[1].lower()
        base_name = os.path.splitext(os.path.basename(filename))[0].lower()
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

        source_map[base_name] = (filename, data)

    # Process translated files (flat OR subfolder)
    for root, dirs, files in os.walk(translated_dir):
        for file in files:
            tgt_path = os.path.join(root, file)
            rel_path = os.path.relpath(tgt_path, translated_dir)

            ext = os.path.splitext(file)[1].lower()
            tgt_base = os.path.splitext(file)[0].lower()

            # Try to get language from subfolder if present
            path_parts = os.path.normpath(rel_path).split(os.sep)
            lang = path_parts[0] if len(path_parts) > 1 else extract_language_from_filename(file)

            # Try to find matching source by prefix
            matched = False
            for src_base, (src_filename, source_data) in source_map.items():
                if tgt_base.startswith(src_base):
                    matched = True
                    break

            if not matched:
                all_report_rows.append({
                    "File Name": file,
                    "Language": lang,
                    "Issue Type": "No matching source file",
                    "Key": file,
                    "Source": "", "Target": "", "Details": "No source match for prefix"
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
                    "Key": err.split(" - ")[0] if " - " in err else err,
                    "Source": "", "Target": "", 
                    "Details": err if " - " not in err else err.split(" - ")[1]
                })
                if not tgt_data:
                    continue

            issues = compare_files(source_data, tgt_data, lang, file)
            all_report_rows.extend(issues)

    # Generate report
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

