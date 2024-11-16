from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import urllib

app = Flask(__name__)
CORS(app)

def fetch_additional_info(link):
    try:
        response = requests.get(link)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        return soup.get_text(separator="\n", strip=True)
    except Exception as e:
        return f"Could not fetch additional info: {e}"

def search_libgen_non_fiction(book_name_or_isbn):
    url = "https://libgen.is/"
    search_url = url + "search.php"
    
    # Check if the input looks like an ISBN (length of 13 or 10)
    if len(book_name_or_isbn) in [10, 13] and book_name_or_isbn.isdigit():
        params = {"req": "ISBN " + book_name_or_isbn}  # Search with "ISBN" prefix
    else:
        params = {"req": book_name_or_isbn}  # Regular search by title

    try:
        response = requests.get(search_url, params=params)
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

                if "pdf" not in extension.lower():
                    continue

                title_td = cols[2]
                title_anchors = title_td.find_all("a")

                detail_page_link = "N/A"
                for anchor in title_anchors:
                    href = anchor.get("href", "")
                    if href.startswith("book/index.php?md5="):
                        detail_page_link = href
                        break

                detail_page_link = url + detail_page_link if detail_page_link != "N/A" else "N/A"

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
        print(f"An error occurred while searching in non-fiction: {e}")
        return []

def search_libgen_fiction(book_name_or_isbn):
    url = "https://libgen.is/"
    search_url = url + "fiction/search.php"
    
    # Check if the input looks like an ISBN (length of 13 or 10)
    if len(book_name_or_isbn) in [10, 13] and book_name_or_isbn.isdigit():
        params = {"req": "ISBN " + book_name_or_isbn}  # Search with "ISBN" prefix
    else:
        params = {"req": book_name_or_isbn}  # Regular search by title

    try:
        response = requests.get(search_url, params=params)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        results_table = soup.find("table", {"class": "catalog"})
        if not results_table:
            return []

        rows = results_table.find_all("tr")[1:]
        data = []

        for row in rows:
            cols = row.find_all("td")
            if len(cols) > 5:
                title = cols[1].text.strip()
                extension = cols[4].text.strip()

                if "pdf" not in extension.lower():
                    continue

                title_td = cols[1]
                title_anchors = title_td.find_all("a")

                detail_page_link = "N/A"
                for anchor in title_anchors:
                    href = anchor.get("href", "")
                    if href.startswith("fiction/"):
                        detail_page_link = "https://libgen.is/" + href
                        break

                mirror_links = []
                mirror_col = cols[5]
                mirror_anchors = mirror_col.find_all("a")
                for anchor in mirror_anchors:
                    href = anchor.get("href", "")
                    if href.startswith("http://library.lol/"):
                        mirror_links.append(href)

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



def download_book_from_mirror(mirror_url):
    try:
        response = requests.get(mirror_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        get_section = soup.find('h2', string="GET")
        if not get_section:
            return "No download link found."

        download_link = get_section.find_next('a').get('href', '')
        if not download_link:
            return "No valid download link found."
        
        download_url = urllib.parse.urljoin(mirror_url, download_link)

        file_response = requests.get(download_url)
        file_response.raise_for_status()

        filename = download_url.split("/")[-1]
        with open(filename, 'wb') as file:
            file.write(file_response.content)

        return f"Book downloaded successfully: {filename}"

    except Exception as e:
        return f"Failed to download the book: {e}"

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
    results = search_libgen_non_fiction(book_name)
    
    if not results:
        results = search_libgen_fiction(book_name)

    if results:
        response_data = []
        for idx, result in enumerate(results, 1):
            title = result[0]
            detail_page_link = result[1]
            mirror_links = result[2]

            # Scrape the ISBN from the detail page
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

@app.route('/download', methods=['GET'])
def download_book():
    book_id = request.args.get('book_id', type=int)
    book_name = request.args.get('book_name', '')
    
    if not book_name or not book_id:
        return jsonify({"status": "failure", "message": "Please provide book name and book ID."}), 400

    books = search_libgen(book_name)
    
    if book_id > len(books) or book_id <= 0:
        return jsonify({"status": "failure", "message": "Invalid book ID."}), 404

    book = books[book_id - 1]
    mirror_links = book["mirror_links"]
    
    if mirror_links:
        download_results = []
        for mirror_url in mirror_links:
            download_result = download_book_from_mirror(mirror_url)
            download_results.append(download_result)
        return jsonify({"status": "success", "message": "Download initiated.", "data": download_results}), 200
    else:
        return jsonify({"status": "failure", "message": "No download links available."}), 404

if __name__ == "__main__":
    app.run(debug=True, port=8080)