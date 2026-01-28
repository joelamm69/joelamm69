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
    Uses text-based parsing optimized for Daily Quote Review PDFs.
    """
    import re

    headers = [
        'Quote #', 'PartNum', 'Description', 'Vendor', 'Qty',
        'AddDate', 'Exp. Close', 'Added By', 'State', 'Customer Name',
        'ListEach', 'Ext_Price', 'Summary', 'Milestone'
    ]

    # US State abbreviations for parsing
    states = ['AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
              'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
              'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
              'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
              'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY', 'DC']

    rows = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            # Extract text from the page
            text = page.extract_text()
            if not text:
                continue

            lines = text.split('\n')

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # Skip non-data lines
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
                if line.startswith('CRM Total'):
                    continue
                if 'Quote Ext. Price' in line:
                    continue

                # Check if line starts with a quote number (7 digits)
                match = re.match(r'^(\d{7})\s+(.+)$', line)
                if not match:
                    continue

                quote_num = match.group(1)
                rest_of_line = match.group(2)

                # Skip "Quote Type:" lines
                if rest_of_line.startswith('Quote Type:'):
                    continue

                # Parse the rest of the line
                row_dict = {'Quote #': quote_num}

                # Try to extract fields using patterns
                # Pattern: PartNum, Description, Vendor, Qty, AddDate, Exp.Close, AddedBy, State, CustomerName, ListEach, Ext_Price, Summary, Milestone

                # Find dates (pattern: M/DD/YY or MM/DD/YY)
                date_pattern = r'\d{1,2}/\d{1,2}/\d{2}'
                dates = re.findall(date_pattern, rest_of_line)

                # Find prices (pattern: number with comma and decimal like 1,234.56 or 0.00)
                price_pattern = r'[\d,]+\.\d{2}'
                prices = re.findall(price_pattern, rest_of_line)

                # Find state - look for 2-letter state code
                state_found = ''
                for state in states:
                    # Look for state code that appears after a name (preceded by letter, followed by space or end)
                    state_match = re.search(r'[a-zA-Z](' + state + r')(?:\s|$)', rest_of_line)
                    if state_match:
                        state_found = state
                        break

                # Find milestone (usually "Incomplete - X%")
                milestone_match = re.search(r'(Incomplete\s*-\s*\d+%|Complete\s*-\s*\d+%)', rest_of_line, re.IGNORECASE)
                milestone = milestone_match.group(1) if milestone_match else ''

                # Extract part number (alphanumeric, right after quote number)
                parts = rest_of_line.split()
                if parts:
                    row_dict['PartNum'] = parts[0]

                # Try to find vendor code (usually 3-5 chars like AVA-C, ADT)
                vendor_match = re.search(r'\s([A-Z]{2,5}(?:-[A-Z])?)\s+\d+\s+\d{1,2}/', rest_of_line)
                if vendor_match:
                    row_dict['Vendor'] = vendor_match.group(1)

                    # Find quantity (number before dates)
                    qty_match = re.search(r'\s([A-Z]{2,5}(?:-[A-Z])?)\s+(\d+)\s+\d{1,2}/', rest_of_line)
                    if qty_match:
                        row_dict['Qty'] = qty_match.group(2)

                # Assign dates
                if len(dates) >= 1:
                    row_dict['AddDate'] = dates[0]
                if len(dates) >= 2:
                    row_dict['Exp. Close'] = dates[1]

                # Assign prices
                if len(prices) >= 1:
                    row_dict['ListEach'] = prices[-2] if len(prices) >= 2 else prices[0]
                if len(prices) >= 2:
                    row_dict['Ext_Price'] = prices[-1]

                row_dict['State'] = state_found
                row_dict['Milestone'] = milestone

                # Try to extract description (between part number and vendor)
                if 'Vendor' in row_dict and row_dict['PartNum']:
                    desc_match = re.search(
                        re.escape(row_dict['PartNum']) + r'\s+(.+?)\s+' + re.escape(row_dict.get('Vendor', '')),
                        rest_of_line
                    )
                    if desc_match:
                        row_dict['Description'] = desc_match.group(1).strip()

                # Try to extract customer name (between state and prices)
                if state_found and prices:
                    # Find text between state and first price
                    customer_pattern = state_found + r'\s+(.+?)\s+[\d,]+\.\d{2}'
                    customer_match = re.search(customer_pattern, rest_of_line)
                    if customer_match:
                        row_dict['Customer Name'] = customer_match.group(1).strip()

                # Try to extract Added By (text before state)
                if state_found:
                    # Look for name pattern before state (usually FirstName LastName or FirstName LastNameState)
                    added_by_match = re.search(r'(\d{1,2}/\d{1,2}/\d{2})\s+([A-Za-z]+\s+[A-Za-z\s]+?)' + state_found, rest_of_line)
                    if added_by_match:
                        row_dict['Added By'] = added_by_match.group(2).strip()

                # Extract summary (usually alphanumeric code before milestone)
                if milestone:
                    summary_match = re.search(r'([\w\d\-#]+)\s+' + re.escape(milestone), rest_of_line)
                    if summary_match:
                        row_dict['Summary'] = summary_match.group(1)

                # Fill in any missing headers with empty string
                for header in headers:
                    if header not in row_dict:
                        row_dict[header] = ''

                rows.append(row_dict)

    # If text extraction found nothing, try table extraction as fallback
    if not rows:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    if not table:
                        continue
                    for row in table:
                        if not row:
                            continue
                        cleaned = [str(cell).strip() if cell else '' for cell in row]
                        first_cell = cleaned[0] if cleaned else ''
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
