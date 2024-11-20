import os
import base64
import requests
import fitz  # PyMuPDF for PDF handling
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from concurrent.futures import ThreadPoolExecutor
from fpdf import FPDF  # For creating PDFs from EPUB

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = 'uploads'
STATIC_FOLDER = 'static'

# Clear previous files (same as before)
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

# Function to convert PDF pages to images
def convert_page_to_image(pdf_document, page_num):
    page = pdf_document.load_page(page_num)
    pixmap = page.get_pixmap(dpi=300)
    image_path = os.path.join(STATIC_FOLDER, f"page_{page_num + 1}.png")
    pixmap.save(image_path)
    return f"/static/{os.path.basename(image_path)}"

@app.route("/convert_pdf/", methods=["POST"])
def convert_pdf():
    clear_previous_files()

    # Get the file from the request
    file = request.files.get('file')
    if not file:
        return jsonify({"error": "No file uploaded"}), 400

    pdf_file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(pdf_file_path)

    # Open the PDF file and convert each page to an image
    try:
        pdf_document = fitz.open(pdf_file_path)
        futures = []
        for page_num in range(pdf_document.page_count):
            future = executor.submit(convert_page_to_image, pdf_document, page_num)
            futures.append(future)
        
        image_urls = [future.result() for future in futures]
        return jsonify({"images": image_urls})
    
    except Exception as e:
        return jsonify({"error": f"Failed to process the PDF: {str(e)}"}), 500

# Convert EPUB to PDF using ConvertAPI
def convert_epub_to_pdf_with_convertapi(epub_file_path):
    with open(epub_file_path, 'rb') as file:
        file_data = file.read()
    
    # Base64 encode the file content
    base64_encoded_file = base64.b64encode(file_data).decode('utf-8')

    url = "https://v2.convertapi.com/convert/epub/to/pdf"
    headers = {
        "Authorization": "Bearer token_dIjJseZq",
        "Content-Type": "application/json"
    }
    
    payload = {
        "Parameters": [
            {
                "Name": "File",
                "FileValue": {
                    "Name": os.path.basename(epub_file_path),
                    "Data": base64_encoded_file
                }
            }
        ]
    }

    response = requests.post(url, json=payload, headers=headers)

    if response.status_code == 200:
        result = response.json()
        # Retrieve the converted PDF file URL from the response
        pdf_url = result['Files'][0]['Url']
        return pdf_url
    else:
        raise Exception(f"Error during conversion: {response.text}")

@app.route("/convert_epub/", methods=["POST"])
def convert_epub():
    clear_previous_files()

    file = request.files.get('file')
    if not file:
        return jsonify({"error": "No file uploaded"}), 400

    if not file.filename.endswith('.epub'):
        return jsonify({"error": "Invalid file type. Only EPUB files are allowed."}), 400

    epub_file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(epub_file_path)

    try:
        # Use ConvertAPI to convert the EPUB to PDF
        pdf_url = convert_epub_to_pdf_with_convertapi(epub_file_path)

        # Download the PDF and save it locally for further processing
        pdf_response = requests.get(pdf_url)
        if pdf_response.status_code == 200:
            pdf_path = os.path.join(UPLOAD_FOLDER, "converted_book.pdf")
            with open(pdf_path, 'wb') as f:
                f.write(pdf_response.content)

            # Convert PDF to images (using the same logic as in convert_pdf)
            pdf_document = fitz.open(pdf_path)
            futures = []
            for page_num in range(pdf_document.page_count):
                future = executor.submit(convert_page_to_image, pdf_document, page_num)
                futures.append(future)
            
            # Wait for all futures to finish and collect results
            image_urls = [future.result() for future in futures]
            
            return jsonify({"images": image_urls})
        else:
            return jsonify({"error": "Failed to download the PDF from ConvertAPI"}), 500

    except Exception as e:
        return jsonify({"error": f"Failed to process the EPUB: {str(e)}"}), 500

@app.route('/static/<filename>')
def send_image(filename):
    return send_from_directory(STATIC_FOLDER, filename)

if __name__ == "__main__":
    app.run(debug=True)
