import os
import time
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests

from bs4 import BeautifulSoup
import urllib

import urllib.parse

app = Flask(__name__)
CORS(app)


DOWNLOAD_DIRECTORY = './downloads'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
}


def clear_previous_files():
    """
    Clears the contents of the download directory, creating it if necessary.
    """
    try:
        if os.path.exists(DOWNLOAD_DIRECTORY):
            for filename in os.listdir(DOWNLOAD_DIRECTORY):
                file_path = os.path.join(DOWNLOAD_DIRECTORY, filename)
                if os.path.isfile(file_path):
                    os.remove(file_path)
        else:
            os.makedirs(DOWNLOAD_DIRECTORY)
    except Exception as e:
        print(f"Error clearing previous files: {str(e)}")


def download_book_from_mirror(mirror_url):
    """
    Downloads the book from the provided mirror URL by parsing the 'GET' anchor tag.
    Args:
        mirror_url (str): The URL to fetch the book page from.
    Returns:
        dict: Dictionary with the download URL and file extension, or an error message.
    """
    try:
        # Fetch the HTML content of the mirror page
        response = requests.get(mirror_url, headers=HEADERS, timeout=180)
        response.raise_for_status()

        # Parse the HTML content
        soup = BeautifulSoup(response.text, 'html.parser')
        anchor_tag = soup.find('h2').find('a', string='GET')  # Locate the anchor tag with 'GET'

        if not anchor_tag:
            return {"error": "Download link not found on the provided page."}

        # Extract the URL of the book
        book_url = anchor_tag['href']

        # Fetch the book file with retry logic
        max_retries = 5
        retry_delay = 3  # seconds
        for attempt in range(max_retries):
            try:
                book_response = requests.get(book_url, headers=HEADERS, stream=True, timeout=180)
                book_response.raise_for_status()
                break
            except (requests.exceptions.RequestException, requests.exceptions.ConnectionError) as e:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Double the delay for the next attempt
                else:
                    return {"error": f"Failed to download the book: {str(e)}"}

        # Get the filename from the URL
        filename = urllib.parse.unquote(book_url.split('/')[-1])
        file_path = os.path.join(DOWNLOAD_DIRECTORY, filename)

        # Save the file locally
        os.makedirs(DOWNLOAD_DIRECTORY, exist_ok=True)
        with open(file_path, 'wb') as file:
            for chunk in book_response.iter_content(chunk_size=1024):
                if chunk:
                    file.write(chunk)

        # Generate the file extension and download URL
        file_extension = os.path.splitext(filename)[1].lower()
        download_url = f"{request.host_url.rstrip('/')}/downloads/{filename}"

        return {"download_url": download_url, "file_extension": file_extension}
    except Exception as e:
        return {"error": str(e)}


@app.route('/download', methods=['POST'])
def download_endpoint():
    """
    Flask endpoint to trigger book download from a mirror.
    Expects a JSON payload with 'mirror_url'.
    """
    try:
        data = request.get_json()
        mirror_url = data.get('mirror_url')

        if not mirror_url:
            return jsonify({"error": "Missing 'mirror_url' in the request body."}), 400

        download_result = download_book_from_mirror(mirror_url)

        if "error" in download_result:
            print(f"Download error: {download_result['error']}")
            return jsonify({"error": download_result["error"]}), 500

        return jsonify(download_result), 200
    except Exception as e:
        print(f"Unhandled server error: {str(e)}")
        return jsonify({"error": f"Server error: {str(e)}"}), 500


@app.route('/downloads/<path:filename>')
def serve_file_from_downloads(filename):
    """
    Serves the file from the 'downloads' directory.
    """
    try:
        safe_filename = os.path.basename(filename)  # Sanitize the filename
        file_path = os.path.join(DOWNLOAD_DIRECTORY, safe_filename)

        if not os.path.exists(file_path):
            return jsonify({"error": "File not found"}), 404

        return send_from_directory(DOWNLOAD_DIRECTORY, safe_filename)
    except Exception as e:
        print(f"Error serving file: {str(e)}")
        return jsonify({"error": f"Error serving file: {str(e)}"}), 500


@app.route('/<filename>')
def serve_file2(filename):
    """
    Serves the file from the download directory.
    """
    return send_from_directory("/",filename)




# Function to download the book from the mirror
# Ensure you only have one download_book_from_mirror function


# Ensure the required directories exist

# Function to download the book from the mirror
# Ensure you only have one download_book_from_mirror function






def fetch_additional_info(link):
    try:
        response = requests.get(link)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        return soup.get_text(separator="\n", strip=True)
    except Exception as e:
        return f"Could not fetch additional info: {e}"

def search_libgen_non_fiction(book_name_or_isbn):
    url = "https://libgen.is/search.php"
    params = {
        "req": book_name_or_isbn,
        "open": "0",
        "res": "100",
        "view": "simple",
        "phrase": "1",
        "column": "def",
    }

    try:
        response = requests.get(url, params=params)
        print(f"Searching LibGen with URL: {url}, Parameters: {params}")

        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        results_table = soup.find("table", {"class": "c"})
        if not results_table:
            return []

        rows = results_table.find_all("tr")[1:]
        data = []

        for row in rows:
            cols = row.find_all("td")
            if len(cols) > 9:
                title = cols[2].text.strip()
                extension = cols[8].text.strip()

                # Ensure only PDF or EPUB formats are considered
                if "pdf" not in extension.lower() and "epub" not in extension.lower():
                    continue

                title_td = cols[2]
                title_anchors = title_td.find_all("a")

                detail_page_link = "N/A"
                for anchor in title_anchors:
                    href = anchor.get("href", "")
                    if href.startswith("book/index.php?md5="):
                        detail_page_link = "https://libgen.is/" + href
                        break

                mirror_links = []
                mirror_col = cols[9]
                mirror_anchors = mirror_col.find_all("a")
                for anchor in mirror_anchors:
                    href = anchor.get("href", "")
                    if href.startswith("http://library.lol/"):
                        mirror_links.append(href)

                data.append([title, detail_page_link, mirror_links])

        return data

    except Exception as e:
        print(f"An error occurred while searching non-fiction: {e}")
        return []

def search_libgen_fiction(book_name_or_isbn):
    
    base_url = "https://libgen.is/fiction/"
    
    # Check if the input is an ISBN (length of 10 or 13, and only digits)
    if len(book_name_or_isbn) in [10, 13] and book_name_or_isbn.isdigit():
        # Search by ISBN
        search_url = base_url + f"?q=ISBN+{book_name_or_isbn}"
    else:
        # Search by book name/title
        search_url = base_url + f"?q={book_name_or_isbn.replace(' ', '+')}"
    
    try:
        print('We are searching at', search_url)
        response = requests.get(search_url)
        response.raise_for_status()
        
        # Parse the HTML content of the page
        soup = BeautifulSoup(response.text, 'html.parser')

        # Locate the table containing the search results
        results_table = soup.find("table", {"class": "catalog"})
        if not results_table:
            return []  # No results found

        rows = results_table.find_all("tr")[1:]  # Skipping the header row
        data = []

        # Iterate over each row to extract relevant information
        for row in rows:
            cols = row.find_all("td")
            if len(cols) > 5:
                # Extract the title (third column)
                title_td = cols[2]
                title_anchors = title_td.find_all("a")
                title = title_anchors[0].text.strip() if title_anchors else "N/A"
                
                # Extract the details page link (URL)
                detail_page_link = "https://libgen.is" + title_anchors[0].get("href", "") if title_anchors else "N/A"

                # Extract file type and size (fifth column)
                extension = cols[4].text.strip()

                # Filter based on file type (PDF/EPUB)
                if "pdf" not in extension.lower() and "epub" not in extension.lower():
                    continue  # Skip if the file is neither PDF nor EPUB
                
                # Extract mirror links (sixth column)
                mirror_links = []
                mirror_col = cols[5]
                mirror_anchors = mirror_col.find_all("a")
                for anchor in mirror_anchors:
                    href = anchor.get("href", "")
                    if href.startswith("http://library.lol/"):
                        mirror_links.append(href)

                # Append book info to the result list
                data.append([title, detail_page_link, mirror_links])

        return data

    except Exception as e:
        print(f"An error occurred while searching in fiction: {e}")
        return []

def scrape_detail_page(detail_url):
    try:
        response = requests.get(detail_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # Find the table containing the details
        table = soup.find('table')
        if not table:
            return {"status": "error", "message": "No table found on the page."}

        # Initialize a dictionary to store the extracted data
        filtered_data = {}

        # Iterate over the rows in the table and extract key-value pairs
        rows = table.find_all('tr')
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 2:
                key = cols[0].text.strip()
                value = cols[1].text.strip()
                

                # Assign data to the dictionary based on key
                if key == "Title":
                    filtered_data["title"] = value
                elif key == "Author(s):":
                    filtered_data["author"] = value
                elif key == "Publisher:":
                    filtered_data["publisher"] = value
                elif key == "Year:":
                    filtered_data["year"] = value
                elif key == "Language:":
                    filtered_data["language"] = value
                elif key == "ISBN:":
                    filtered_data["isbn"] = value
                
                elif key == "Size:":
                    filtered_data["size"] = value
                elif key == "Pages (biblio\\tech):":
                    filtered_data["pages"] = value
      

        # Extract additional information if present (e.g., description, torrent info)
        description_tag = soup.find('div', {'class': 'description'})
        if description_tag:
            filtered_data["description"] = description_tag.text.strip()

        torrent_info_tag = soup.find(string="Torrent per 1000 files")
        if torrent_info_tag:
            filtered_data["torrent_info"] = torrent_info_tag.find_next('td').text.strip()

        contents_tag = soup.find('div', {'class': 'table-of-contents'})
        if contents_tag:
            filtered_data["table_of_contents"] = contents_tag.text.strip()

        # Return the structured JSON data
        return filtered_data

    except Exception as e:
        return {"status": "error", "message": f"Could not scrape the table data: {e}"}





def scrape_isbn_from_detail_page(detail_url):
    try:
        response = requests.get(detail_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        table = soup.find('table')
        if not table:
            return None

        rows = table.find_all('tr')
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 2:
                key = cols[0].text.strip()
                value = cols[1].text.strip()

                if key == "ISBN:":
                    return value
        return None
    except Exception as e:
        print(f"Error while scraping ISBN: {e}")
        return None

def search_libgen(book_name):
    non_fiction_results = search_libgen_non_fiction(book_name)
    fiction_results = search_libgen_fiction(book_name)

    # Combine both results
    combined_results = non_fiction_results + fiction_results

    if combined_results:
        response_data = []
        for idx, result in enumerate(combined_results, 1):
            title = result[0]
            detail_page_link = result[1]
            mirror_links = result[2]

            # Scrape ISBN from detail page
            isbn = None
            if detail_page_link != "N/A":
                isbn = scrape_isbn_from_detail_page(detail_page_link)

            response_data.append({
                "id": idx,
                "title": title,
                "detail_page_link": detail_page_link,
                "mirror_links": mirror_links,
                "isbn": isbn
            })
        return response_data
    else:
        return []


@app.route('/search', methods=['GET'])
def search_books():
    book_name = request.args.get('book_name', '')
    if book_name:
        books = search_libgen(book_name)
        if books:
            return jsonify({"status": "success", "data": books}), 200
        else:
            return jsonify({"status": "failure", "message": "No books found for that, sorry :("}), 404
    else:
        return jsonify({"status": "failure", "message": "Please provide a book name."}), 400

@app.route('/book_details', methods=['GET'])
def book_details():
    isbn = request.args.get('isbn', '')
    book_name = request.args.get('book_name', '')

    if not isbn and not book_name:
        return jsonify({"status": "failure", "message": "Please provide either an ISBN or book name."}), 400
    
    # Default search to book name if ISBN is not provided
    if isbn:
        books = search_libgen(isbn)  # Search by ISBN
    elif book_name:
        books = search_libgen(book_name)  # Search by book name
    else:
        books = []

    if books:
        selected_book = books[0]  # Get the first result from the search
        
        # Check if the book has a valid detail page link
        detail_page_url = selected_book.get("detail_page_link", "N/A")
        
        if detail_page_url != "N/A":
            table_data = scrape_detail_page(detail_page_url)  # Scrape details from the detail page
            return jsonify({"status": "success", "data": table_data}), 200
        else:
            return jsonify({"status": "failure", "message": "Detail page not available."}), 404
    else:
        return jsonify({"status": "failure", "message": "Book not found with provided ISBN or name."}), 404



if __name__ == '__main__':
    clear_previous_files()  # Clear any pre-existing files before starting
    app.run(debug=True, host='0.0.0.0', port=5000)