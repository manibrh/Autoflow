import os
import shutil
import tempfile
import zipfile
import pandas as pd
import uuid
from flask import Flask, render_template, request, send_file

from tep_preprocess import run_tep_preprocessing
from tep_postprocess import run_tep_postprocessing
from legacy_preprocess import run_legacy_preprocessing
from legacy_postprocess import run_legacy_postprocessing
from final_compare import run_final_comparison_from_zip

app = Flask(__name__)
app.secret_key = 'localization_secret'

TEMP_OUTPUT = "static/processed_files"
os.makedirs(TEMP_OUTPUT, exist_ok=True)

@app.route('/')
def index():
    return render_template('ui.html')

@app.route('/userguide')
def userguide():
    return render_template('userguide.html')

@app.route('/final_compare', methods=['POST'])
def final_compare():
    try:
        source_files = request.files.getlist('source_files')
        translated_zip = request.files.get('translated_zip')

        if not source_files or not translated_zip:
            return render_template("error.html", message="Missing source files or translated ZIP")

        # ✅ Updated to capture full report data including spacing mismatches
        output_path, token, report_name, report_data = run_final_comparison_from_zip(source_files, translated_zip)

        # ✅ Create headers and rows for preview table
        df = pd.DataFrame(report_data)
        headers = df.columns.tolist()
        rows = df.fillna('').values.tolist()

        return render_template("compare_results.html", headers=headers, rows=rows,
                               report_url=f"/temp_download/{token}", report_name=report_name)

    except Exception as e:
        return render_template("error.html", message=str(e))

@app.route('/temp_download/<token>')
def temp_download(token):
    temp_dir = tempfile.gettempdir()
    for fname in os.listdir(temp_dir):
        if fname.startswith(token + "__") and fname.endswith(".xlsx"):
            path = os.path.join(temp_dir, fname)
            original_name = fname.split("__", 1)[1]
            return send_file(path, as_attachment=True, download_name=original_name)
    return "File not found", 404

@app.route('/process', methods=['POST'])
def process():
    workflow = request.form.get('workflow')
    process_type = request.form.get('processType')

    with tempfile.TemporaryDirectory() as temp_dir:
        input_dir = os.path.join(temp_dir, 'Input')
        output_dir = os.path.join(temp_dir, 'Output')
        os.makedirs(input_dir, exist_ok=True)
        os.makedirs(output_dir, exist_ok=True)

        try:
            if workflow == 'legacy' and process_type == 'preprocess':
                for file in request.files.getlist('source_files'):
                    filename = file.filename
                    if filename:
                        file.save(os.path.join(input_dir, f"source_{filename}"))

                target_zip = request.files.get('target_zip')
                if target_zip and target_zip.filename:
                    zip_path = os.path.join(input_dir, 'target_langs.zip')
                    target_zip.save(zip_path)
                    extract_dir = os.path.join(input_dir, 'targets')
                    os.makedirs(extract_dir, exist_ok=True)
                    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                        zip_ref.extractall(extract_dir)

            else:
                for file in request.files.getlist('files'):
                    filename = file.filename
                    if filename:
                        file.save(os.path.join(input_dir, filename))

            if workflow == 'tep':
                if process_type == 'preprocess':
                    run_tep_preprocessing(input_dir, output_dir)
                else:
                    run_tep_postprocessing(input_dir, output_dir)
                errors = []
            else:
                if process_type == 'preprocess':
                    errors = run_legacy_preprocessing(input_dir, output_dir)
                else:
                    run_legacy_postprocessing(input_dir, output_dir)
                    errors = []

            # Clear and copy to TEMP_OUTPUT
            if os.path.exists(TEMP_OUTPUT):
                shutil.rmtree(TEMP_OUTPUT)
            shutil.copytree(output_dir, TEMP_OUTPUT)

            # Create ZIP
            zip_path = os.path.join(TEMP_OUTPUT, "batch.zip")
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, _, files in os.walk(TEMP_OUTPUT):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, TEMP_OUTPUT)
                        if not arcname.endswith("batch.zip"):
                            zipf.write(file_path, arcname)

            output_files = []
            for root, _, files in os.walk(TEMP_OUTPUT):
                for file in files:
                    rel_path = os.path.relpath(os.path.join(root, file), TEMP_OUTPUT)
                    if not rel_path.endswith("batch.zip"):
                        output_files.append(rel_path.replace("\\", "/"))

            return render_template("results.html", files=output_files, errors=errors)

        except Exception as e:
            return render_template("error.html", message=str(e))

@app.route('/download/<path:filename>')
def download(filename):
    file_path = os.path.join(TEMP_OUTPUT, filename)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    return "File not found", 404

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
