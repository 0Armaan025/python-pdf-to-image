import os
from pdf2image import convert_from_path
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__)

# Create a folder to store the uploaded PDFs and images
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Set the directory for static file serving
app.config['STATIC_FOLDER'] = 'static'
os.makedirs(app.config['STATIC_FOLDER'], exist_ok=True)

@app.route("/convert_pdf/", methods=["POST"])
def convert_pdf():
    # Get the uploaded file
    file = request.files.get('file')
    if not file:
        return jsonify({"error": "No file uploaded"}), 400

    # Save the uploaded PDF file
    pdf_file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(pdf_file_path)

    # Convert PDF to images
    images = convert_from_path(pdf_file_path, dpi=300)

    # Save images and generate URLs
    image_urls = []
    for i, img in enumerate(images):
        img_path = os.path.join(app.config['STATIC_FOLDER'], f"page_{i + 1}.png")
        img.save(img_path, "PNG")
        image_urls.append(f"/static/{os.path.basename(img_path)}")

    return jsonify({"images": image_urls})

@app.route('/static/<filename>')
def send_image(filename):
    return send_from_directory(app.config['STATIC_FOLDER'], filename)

if __name__ == "__main__":
    app.run(debug=True)
