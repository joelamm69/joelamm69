# PDF Quote Extractor

A web application that extracts table data from Daily Quote Review PDFs and allows you to search/filter by any column.

## Features

- Upload PDF files via drag-and-drop or file picker
- Automatic table extraction from PDFs
- Search by any column (Quote #, PartNum, Customer Name, State, etc.)
- Clean, responsive web interface
- Real-time filtering of results

## Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd joelamm69
   ```

2. **Create a virtual environment (recommended):**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

## Running the Application

1. **Start the Flask server:**
   ```bash
   python app.py
   ```

2. **Open your browser and go to:**
   ```
   http://localhost:5000
   ```

## Usage

1. **Upload a PDF** - Click the upload area or drag and drop your Daily Quote Review PDF
2. **View extracted data** - The table will display all rows extracted from the PDF
3. **Search/Filter** - Select a column from the dropdown, enter a search value, and click Search
4. **Clear filter** - Click "Clear Filter" to show all rows again

## Supported Columns

The application is optimized for Daily Quote Review PDFs with these columns:
- Quote #
- PartNum
- Description
- Vendor
- Qty
- AddDate
- Exp. Close
- Added By
- State
- Customer Name
- ListEach
- Ext_Price
- Summary
- Milestone

## Example Searches

- Find all quotes for a specific customer: Select "Customer Name" and enter the customer name
- Find quotes by state: Select "State" and enter "NY" or "IL"
- Find quotes by sales rep: Select "Added By" and enter the name
- Find a specific part: Select "PartNum" and enter the part number

## Technology Stack

- **Backend:** Python, Flask
- **PDF Processing:** pdfplumber
- **Frontend:** HTML, CSS, JavaScript
