import os
import time
import requests
import concurrent.futures
import logging
import imaplib
from email import policy
from email.parser import BytesParser
from email.utils import parsedate_to_datetime
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from datetime import datetime, timedelta
import quopri
import base64

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# QQ email IMAP settings
IMAP_SERVER = 'imap.qq.com'
EMAIL_ACCOUNT = os.getenv('QQ_EMAIL')
PASSWORD = os.getenv('QQ_PASSWORD')

# Firecrawl API settings
FIRECRAWL_API_KEY = os.getenv('FIRECRAWL_API_KEY')
FIRECRAWL_API_URL = 'https://api.firecrawl.dev/v1'

# Define the email criteria
SENDER_EMAIL = 'scholaralerts-noreply@google.com'
DAYS_RECENT = 1  # Set this to the number of recent days you want to filter emails by

Model = "qwen2:7b"

def get_emails():
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(EMAIL_ACCOUNT, PASSWORD)
        mail.select("inbox")  # Select inbox
        result, data = mail.search(None, 'FROM', SENDER_EMAIL)
        email_ids = data[0].split()
        return mail, email_ids
    except Exception as e:
        logging.error(f"Error fetching emails: {e}")
        return None, []

def decode_content(part):
    charset = part.get_content_charset() or 'utf-8'
    payload = part.get_payload(decode=True)

    # 处理不同的编码方式
    if part['Content-Transfer-Encoding'] == 'quoted-printable':
        decoded_content = quopri.decodestring(payload).decode(charset, errors='ignore')
    elif part['Content-Transfer-Encoding'] == 'base64':
        decoded_content = base64.b64decode(payload).decode(charset, errors='ignore')
    else:
        decoded_content = payload.decode(charset, errors='ignore')
    
    return decoded_content
    

def fetch_email_content(mail, email_id):
    try:
        result, data = mail.fetch(email_id, "(RFC822)")
        msg_content = data[0][1]
        msg = BytesParser(policy=policy.default).parsebytes(msg_content)

        # Check the sender
        if msg['From'] and SENDER_EMAIL not in msg['From']:
            return None  # Skip emails not from the specified sender
        
        # Check the date
        email_date = parsedate_to_datetime(msg['Date'])
        now = datetime.now(email_date.tzinfo)  # 确保 now 带有与 email_date 相同的时区信息
        if email_date < now - timedelta(days=DAYS_RECENT):
            return None  # Skip emails older than the specified number of days

        # Extract content from the email
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get('Content-Disposition'))

                if content_type == "text/plain" and 'attachment' not in content_disposition:
                    return decode_content(part)
                elif content_type == "text/html" and 'attachment' not in content_disposition:
                    return decode_content(part)
        else:
            content_type = msg.get_content_type()
            if content_type == "text/plain" or content_type == "text/html":
                return decode_content(msg)
    except Exception as e:
        logging.error(f"Error getting email content: {e}")
    return None

def extract_urls(content):
    print('content',content)
    soup = BeautifulSoup(content, 'html.parser')
    return [a['href'] for a in soup.find_all('a', href=True) if a['href'].startswith('http')]

def firecrawl_submit_crawl(url):
    try:
        response = requests.post(
            f'{FIRECRAWL_API_URL}/crawl',
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {FIRECRAWL_API_KEY}'
            },
            json={
                'url': url,
                'limit': 100,
                'scrapeOptions': {
                    'formats': ['markdown']
                }
            }
        )
        response.raise_for_status()
        data = response.json()
        if data.get('success'):
            return data['id']
        else:
            logging.error(f"Crawl job submission failed for URL: {url}")
            return None
    except requests.RequestException as e:
        logging.error(f"Error submitting crawl job: {e}")
    return None

def firecrawl_check_crawl(job_id):
    try:
        response = requests.get(
            f'{FIRECRAWL_API_URL}/crawl/{job_id}',
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {FIRECRAWL_API_KEY}'
            }
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logging.error(f"Error checking crawl job: {e}")
    return None

def firecrawl_crawl(url):
    print(f"Processing URL: {url}")
    job_id = firecrawl_submit_crawl(url)
    if not job_id:
        return None

    max_attempts = 12  # 1 minute total waiting time
    for _ in range(max_attempts):
        result = firecrawl_check_crawl(job_id)
        if result and result['status'] == 'completed':
            return result['data'][0]['markdown']  # Assuming we want the first page's markdown
        elif result and result['status'] == 'failed':
            logging.error(f"Crawl job failed for URL: {url}")
            return None
        time.sleep(30)  # Wait for 5 seconds before checking again
    
    logging.error(f"Crawl job timed out for URL: {url}")
    return None

def ollama_request(prompt):
    try:
        response = requests.post('http://localhost:11434/api/chat', json={
            "model": Model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False
        })
        response.raise_for_status()
        return response.json()['message']['content']
    except requests.RequestException as e:
        logging.error(f"Error in Ollama request: {e}")
        return None

def translate_text(text):
    return ollama_request(f"请将以下论文内容提取标题，摘要并翻译成中文：\n\n{text}") or "翻译失败"

def summarize_paper(content):
    return ollama_request(f"请分析以下论文内容，按背景，解决问题，提出方法，创新点来总结：\n\n{content}") or "摘要总结失败"

def process_paper(url):
    markdown_content = firecrawl_crawl(url)
    if markdown_content:
        translated_content = translate_text(markdown_content)
        summary = summarize_paper(translated_content)
        return {
            'url': url,
            'translated_content': translated_content,
            'summary': summary
        }
    return None

def main():
    mail, email_ids = get_emails()
    if len(email_ids) == 0:
        logging.info("No emails found.")
        return

    all_paper_urls = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        email_contents = list(executor.map(lambda email_id: fetch_email_content(mail, email_id), email_ids))
        for content in email_contents:
            if content:  # Filter out None values
                all_paper_urls.extend(extract_urls(content))

        results = list(executor.map(process_paper, all_paper_urls))

    with open('research_summary.md', 'w', encoding='utf-8') as f:
        for result in results:
            if result:
                f.write(f"# URL: {result['url']}\n\n")
                f.write(f"## 译文内容\n{result['translated_content']}\n\n")
                f.write(f"## 论文总结\n{result['summary']}\n\n")
                f.write("---\n\n")

if __name__ == "__main__":
    main()
