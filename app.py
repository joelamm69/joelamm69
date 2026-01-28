"""
PDF Column Extraction Web Application
A Flask app that allows users to upload PDFs, extract table data,
and search/filter by column values.
"""

import os
from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename
import pdfplumber

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
ALLOWED_EXTENSIONS = {'pdf'}

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


def allowed_file(filename):
    """Check if file has allowed extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def extract_tables_from_pdf(pdf_path):
    """
    Extract table data from a PDF file.
    Returns a list of dictionaries with headers and rows.
    """
    all_data = []
    headers = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            # Extract tables from the page
            tables = page.extract_tables()

            for table in tables:
                if not table:
                    continue

                for row_idx, row in enumerate(table):
                    if not row:
                        continue

                    # Clean up the row data
                    cleaned_row = [str(cell).strip() if cell else '' for cell in row]

                    # Try to identify header row (usually first row with column names)
                    if row_idx == 0 and page_num == 0 and not headers:
                        # Check if this looks like a header row
                        if any(h in ' '.join(cleaned_row).lower() for h in ['quote', 'part', 'description', 'qty', 'price']):
                            headers = cleaned_row
                            continue

                    # Skip empty rows or summary rows
                    if not any(cleaned_row) or cleaned_row[0].startswith('CRM Total'):
                        continue

                    all_data.append(cleaned_row)

    return headers, all_data


def parse_quote_review_pdf(pdf_path):
    """
    Parse the Daily Quote Review PDF format specifically.
    This handles the specific structure of the quote review reports.
    """
    headers = [
        'Quote #', 'PartNum', 'Description', 'Vendor', 'Qty',
        'AddDate', 'Exp. Close', 'Added By', 'State', 'Customer Name',
        'ListEach', 'Ext_Price', 'Summary', 'Milestone'
    ]

    rows = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            # Extract text and try to parse it
            text = page.extract_text()
            if not text:
                continue

            lines = text.split('\n')

            for line in lines:
                # Skip header lines, empty lines, and summary lines
                if not line.strip():
                    continue
                if 'DAILY QUOTE REVIEW' in line:
                    continue
                if 'Printed:' in line:
                    continue
                if 'Quote #' in line and 'PartNum' in line:
                    continue
                if 'Quote Type:' in line:
                    continue
                if 'Total After Discount' in line:
                    continue
                if line.strip().startswith('CRM'):
                    continue

                # Try to parse data lines (they start with a quote number)
                parts = line.split()
                if parts and parts[0].isdigit() and len(parts[0]) >= 6:
                    # This looks like a quote line
                    rows.append({
                        'raw': line,
                        'quote_num': parts[0]
                    })

            # Also try table extraction
            tables = page.extract_tables()
            for table in tables:
                if not table:
                    continue
                for row in table:
                    if row and row[0] and str(row[0]).strip().isdigit():
                        cleaned = [str(cell).strip() if cell else '' for cell in row]
                        # Create a dictionary mapping headers to values
                        row_dict = {}
                        for i, header in enumerate(headers):
                            if i < len(cleaned):
                                row_dict[header] = cleaned[i]
                            else:
                                row_dict[header] = ''
                        rows.append(row_dict)

    return headers, rows


def smart_extract_pdf(pdf_path):
    """
    Smart extraction that tries multiple methods to get the best data.
    """
    headers = [
        'Quote #', 'PartNum', 'Description', 'Vendor', 'Qty',
        'AddDate', 'Exp. Close', 'Added By', 'State', 'Customer Name',
        'ListEach', 'Ext_Price', 'Summary', 'Milestone'
    ]

    rows = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            # Try table extraction first
            tables = page.extract_tables()

            for table in tables:
                if not table:
                    continue

                for row in table:
                    if not row:
                        continue

                    # Clean the row
                    cleaned = [str(cell).strip() if cell else '' for cell in row]

                    # Skip if it's a header row or empty
                    if 'Quote #' in cleaned or 'PartNum' in cleaned:
                        continue
                    if not any(cleaned):
                        continue

                    # Skip summary/total rows
                    first_cell = cleaned[0] if cleaned else ''
                    if 'Total' in first_cell or 'Quote Type' in first_cell:
                        continue

                    # Check if first cell looks like a quote number (6+ digits)
                    if first_cell.isdigit() and len(first_cell) >= 6:
                        row_dict = {}
                        for i, header in enumerate(headers):
                            if i < len(cleaned):
                                row_dict[header] = cleaned[i]
                            else:
                                row_dict[header] = ''
                        rows.append(row_dict)

    return headers, rows


@app.route('/')
def index():
    """Render the main page."""
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle PDF file upload and extraction."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': 'Only PDF files are allowed'}), 400

    # Save the uploaded file
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    try:
        # Extract data from PDF
        headers, rows = smart_extract_pdf(filepath)

        return jsonify({
            'success': True,
            'headers': headers,
            'rows': rows,
            'total_rows': len(rows)
        })
    except Exception as e:
        return jsonify({'error': f'Error processing PDF: {str(e)}'}), 500
    finally:
        # Clean up uploaded file
        if os.path.exists(filepath):
            os.remove(filepath)


@app.route('/search', methods=['POST'])
def search_data():
    """Search uploaded data by column and value."""
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No data provided'}), 400

    rows = data.get('rows', [])
    search_column = data.get('column', '')
    search_value = data.get('value', '').lower()

    if not search_column or not search_value:
        return jsonify({'results': rows})

    # Filter rows where the column contains the search value
    results = []
    for row in rows:
        cell_value = str(row.get(search_column, '')).lower()
        if search_value in cell_value:
            results.append(row)

    return jsonify({'results': results})


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
