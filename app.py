from flask import Flask, render_template, request, redirect, send_file, flash
import requests
from bs4 import BeautifulSoup
import pandas as pd
import os
import io
import logging
import glob
import time

logging.basicConfig(
    filename='scraper.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "fallback_secret")

OUTPUT_PATH = "output/dynamic_scraped_output.xlsx"

def scrape_dynamic(session, url, selectors, attr_type="text"):
    results = []
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'}
    try:
        res = session.get(url, headers=headers, timeout=10, allow_redirects=True)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")
        for selector in selectors:
            elements = soup.select(selector)
            for el in elements:
                value = el.get_text(strip=True) if attr_type == "text" else el.get(attr_type) or "N/A"
                results.append({"URL": url, "Selector": selector, "Content": value})
        time.sleep(1)
        return results
    except requests.exceptions.RequestException as e:
        logging.error(f"Request error while scraping {url}: {e}")
        raise
    except Exception as e:
        logging.error(f"Unexpected error while scraping {url}: {e}")
        raise

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/scrape', methods=['POST'])
def scrape_route():
    urls_input = request.form.get('urls', '').strip()
    selectors_input = request.form.get('selectors', '').strip()
    attr_type = request.form.get('attribute', 'text').strip()
    proxy_input = request.form.get('proxy', '').strip()

    if not urls_input or not selectors_input:
        flash("Please enter all required fields.")
        logging.warning("Missing required form fields")
        return redirect('/')

    urls = [u.strip() for u in urls_input.split(",") if u.strip()]
    selectors = [s.strip() for s in selectors_input.split(",") if s.strip()]
    proxies = {"http": proxy_input, "https": proxy_input} if proxy_input else None

    try:
        with requests.Session() as session:
            if proxies:
                session.proxies.update(proxies)
                logging.info(f"Using proxy: {proxy_input}")

            all_data = []
            for url in urls:
                logging.info(f"Scraping URL: {url}")
                data = scrape_dynamic(session, url, selectors, attr_type)
                all_data.extend(data)

        if not all_data:
            flash("No data scraped.")
            logging.warning("No data scraped")
            return redirect('/')

        df = pd.DataFrame(all_data)
        os.makedirs("output", exist_ok=True)
        with pd.ExcelWriter(OUTPUT_PATH, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='ScrapedData')

        flash("Scraping complete. Click 'Download Excel' to get the file.")
        logging.info("Scraping complete.")
        return redirect('/')

    except Exception as e:
        logging.error(f"Scraping error: {e}")
        flash(f"Error: {e}")
        return redirect('/')

@app.route('/download')
def download_excel():
    if os.path.exists(OUTPUT_PATH):
        return send_file(OUTPUT_PATH, as_attachment=True)
    else:
        flash("No Excel file found. Please scrape data first.")
        return redirect('/')

@app.route('/history')
def history():
    files = sorted(glob.glob("output/*.xlsx"), reverse=True)
    filenames = [os.path.basename(f) for f in files]
    return render_template('history.html', files=filenames)

@app.route('/logs')
def logs():
    try:
        with open("scraper.log", "r") as f:
            lines = f.readlines()[-100:]
        return render_template('logs.html', logs=lines)
    except Exception as e:
        flash(f"Error reading log file: {e}")
        return redirect('/')

if __name__ == '__main__':
    app.run(debug=True)
