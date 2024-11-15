import os
import fitz  # PyMuPDF
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS  
from concurrent.futures import ThreadPoolExecutor  

app = Flask(__name__)

CORS(app)

UPLOAD_FOLDER = 'uploads'
STATIC_FOLDER = 'static'

def clear_previous_files():
    if os.path.exists(UPLOAD_FOLDER):
        for filename in os.listdir(UPLOAD_FOLDER):
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            os.remove(file_path)
    else:
        os.makedirs(UPLOAD_FOLDER)

    if os.path.exists(STATIC_FOLDER):
        for filename in os.listdir(STATIC_FOLDER):
            file_path = os.path.join(STATIC_FOLDER, filename)
            os.remove(file_path)
    else:
        os.makedirs(STATIC_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['STATIC_FOLDER'] = STATIC_FOLDER

executor = ThreadPoolExecutor(max_workers=15)

def convert_page_to_image(pdf_document, page_num):
    page = pdf_document.load_page(page_num)
    pixmap = page.get_pixmap(dpi=300)
    image_path = os.path.join(STATIC_FOLDER, f"page_{page_num + 1}.png")
    pixmap.save(image_path)
    return f"/static/{os.path.basename(image_path)}"

@app.route("/convert_pdf/", methods=["POST"])
def convert_pdf():
    clear_previous_files()
    
    file = request.files.get('file')
    if not file:
        return jsonify({"error": "No file uploaded"}), 400

    pdf_file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(pdf_file_path)

    pdf_document = fitz.open(pdf_file_path)

    futures = []
    for page_num in range(pdf_document.page_count):
        future = executor.submit(convert_page_to_image, pdf_document, page_num)
        futures.append(future)

    image_urls = [future.result() for future in futures]

    return jsonify({"images": image_urls})

@app.route('/static/<filename>')
def send_image(filename):
    return send_from_directory(STATIC_FOLDER, filename)

if __name__ == "__main__":  
    app.run(debug=True)
