import os
import time
import requests
import concurrent.futures
import logging
import imaplib
import email
from email import policy
from email.parser import BytesParser
from email.utils import parsedate_to_datetime
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from datetime import datetime, timedelta
import quopri
import base64
import re
import backoff
import re
from urllib.parse import urlparse, parse_qs, unquote
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
FIRECRAWL_API_URL = 'http://140.143.139.183:3002/v1'

# Define the email criteria
SENDER_EMAIL = 'scholaralerts-noreply@google.com'
DAYS_RECENT = 2  # Set this to the number of recent days you want to filter emails by

Model = "qwen2:7b"

@backoff.on_exception(backoff.expo, imaplib.IMAP4.error, max_tries=5)
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

    # Handle different encoding methods
    if part['Content-Transfer-Encoding'] == 'quoted-printable':
        decoded_content = quopri.decodestring(payload).decode(charset, errors='ignore')
    elif part['Content-Transfer-Encoding'] == 'base64':
        decoded_content = base64.b64decode(payload).decode(charset, errors='ignore')
    else:
        decoded_content = payload.decode(charset, errors='ignore')
    
    return decoded_content
    

@backoff.on_exception(backoff.expo, imaplib.IMAP4.error, max_tries=5)
def fetch_email_content(mail, email_id):
    try:
        logging.info(f"Fetching email ID: {email_id}")
        result, data = mail.fetch(email_id, "(RFC822)")
        if result != 'OK':
            logging.error(f"Failed to fetch email ID: {email_id}, result: {result}")
            return None

        raw_email = data[0][1]
        email_message = email.message_from_bytes(raw_email, policy=policy.default)

        # Check the sender
        if email_message['From'] and SENDER_EMAIL not in email_message['From']:
            logging.info(f"Email ID {email_id} is not from the expected sender.")
            return None

        # Check the date
        email_date = parsedate_to_datetime(email_message['Date'])
        now = datetime.now(email_date.tzinfo)
        if email_date < now - timedelta(days=DAYS_RECENT):
            logging.info(f"Email ID {email_id} is older than the specified range.")
            return None

        # Extract content from the email
        content = ""
        if email_message.is_multipart():
            for part in email_message.walk():
                if part.get_content_type() in ["text/plain", "text/html"]:
                    content += decode_content(part)
        else:
            content = decode_content(email_message)

        return content

    except Exception as e:
        logging.error(f"Error getting email content for email ID: {email_id}: {e}")
        return None



headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
        'cookie': 'HSID=A_DD98WEIxsZsZc1D; SSID=Acev8bMzZMZ-CHBqd; APISID=ol9iD2CnHWFkjR6A/AphA9fyLgdows48j1; SAPISID=bAFbrV_vxE88zUON/AAEQDZY3Ih52DjQC5; __Secure-1PAPISID=bAFbrV_vxE88zUON/AAEQDZY3Ih52DjQC5; __Secure-3PAPISID=bAFbrV_vxE88zUON/AAEQDZY3Ih52DjQC5; GSP=LM=1713536331:S=Ht2EeIZJY6yo2fZm; SEARCH_SAMESITE=CgQI15sB; SID=g.a000mgg5DJ-LGRng_4NuGlwwJt7hy3rrcY8qMQEuphLK51otZLugCQoRX_ZOGhvP7J3Rn96EYgACgYKAc4SARUSFQHGX2MihSJ1TjKlro8BtaQxUFPIFRoVAUF8yKpQEdi69tnxJWObbNCwGRwP0076; __Secure-1PSID=g.a000mgg5DJ-LGRng_4NuGlwwJt7hy3rrcY8qMQEuphLK51otZLugDJa2sr68sT5C5rIL9Y-7awACgYKAdoSARUSFQHGX2MiNg8zEzovcDHkdr4cgF3spBoVAUF8yKoYKdFZNXJBOE27-ktp_7pG0076; __Secure-3PSID=g.a000mgg5DJ-LGRng_4NuGlwwJt7hy3rrcY8qMQEuphLK51otZLugtlCOMMTsX_xLmhJoO9xZBQACgYKAQASARUSFQHGX2MiKvDoa4FyklqtfomMLEWNbRoVAUF8yKo2QJIh6OtPUA33Y1tEMo2J0076; OGPC=19026797-10:19026792-1:; AEC=AVYB7crBKOo4i964_5eZ8CCIJaZF8UWX2_LOibVbtHdFs1_KiLwhwYHHkVY; mp_851392464b60e8cc1948a193642f793b_mixpanel=%7B%22distinct_id%22%3A%20%22%24device%3A191a8b2019c54c-033061441b06e-26001051-1fa400-191a8b2019c54c%22%2C%22%24device_id%22%3A%20%22191a8b2019c54c-033061441b06e-26001051-1fa400-191a8b2019c54c%22%2C%22%24initial_referrer%22%3A%20%22%24direct%22%2C%22%24initial_referring_domain%22%3A%20%22%24direct%22%2C%22%24search_engine%22%3A%20%22google%22%7D; NID=517=AoAMxNP9bhSOqgEQcSGFD0iIr4iD7bakt1iS_O7k2vVCTQbQRIRoPv-xfmnti1Tbkol0XPIymFXqnGQfjaABZS4AO5NLHvc1jbfO1f1W9J8SGe-S09L8XeOb4gWwmc7bGzqTdciYNbr-s4qtE8u19kORMTZpF83CJ4K76QTRnO4r5gD1y9FAGBiuZU3BEAAsZ4vSD_65XsURB0menj3fT7f6SL1T3dpKGMs3CYcvHTGeNpmg28cZcBoy9lSLpL_DgUqANemzSH0M0122OcOxZQDbnyzvIbJFwjxfDZvHu_JmsAXhkaV3CvFWchEuoQwVeI4KD00I7BECid1jK0t3kfKJmoK-Krs5pwnjH5tlBQc1S9wch63iwRaHuWw; __Secure-1PSIDTS=sidts-CjIBUFGoh9Vky5sr-opqPumhtnS-qvPlJFg6tNH4gHNEwhLXNPFy6ZOBv1BvVcg2tA4TMhAA; __Secure-3PSIDTS=sidts-CjIBUFGoh9Vky5sr-opqPumhtnS-qvPlJFg6tNH4gHNEwhLXNPFy6ZOBv1BvVcg2tA4TMhAA; SIDCC=AKEyXzUDbTwWHUL1HgPSCPqT3ihD2tCB7i1sz_7v6U2AEAitv3NKQ9yPXIaABW_z_Qlp-oWnL8s; __Secure-1PSIDCC=AKEyXzXKYtFYJ65HpUdHecxScdqtX5_GESv0JgFUDc5TZxlQPbwk2eQpEAqFR4YCzRiJNKuSpBmE; __Secure-3PSIDCC=AKEyXzUlsC7gD9jgjrS4U7iYLyfwUxySJJIbZRMSsdodrW830O7SMg8uKnawUmh0ycg_lmnhaRk',
        'priority': 'u=0, i',
        'sec-ch-ua': '"Not=A?Brand";v="8", "Chromium";v="129", "Google Chrome";v="129"',
        'sec-ch-ua-arch': '"x86"',
        'sec-ch-ua-bitness': '"64"',
        'sec-ch-ua-full-version-list': '"Not=A?Brand";v="8.0.0.0", "Chromium";v="129.0.6668.12", "Google Chrome";v="129.0.6668.12"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-model': '""',
        'sec-ch-ua-platform': '"Windows"',
        'sec-ch-ua-platform-version': '"19.0.0"',
        'sec-ch-ua-wow64': '?0',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'none',
        'sec-fetch-user': '?1',
        'upgrade-insecure-requests': '1',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36'
    }

def get_final_url(input_url):
    try:
        # 提取并解码url参数
        parsed_url = urlparse(input_url)
        query_params = parse_qs(parsed_url.query)
        encoded_url = query_params.get('url', [None])[0]
        
        if not encoded_url:
            logging.error(f"No 'url' parameter found in {input_url}")
            return None

        final_url = unquote(encoded_url)
        logging.info(f"Decoded URL: {final_url}")
        return final_url
    except requests.RequestException as e:
        logging.error(f"Error resolving final URL for {input_url}: {e}")
        return None

def extract_urls(content):
    logging.info('Extracting URLs from content')
    soup = BeautifulSoup(content, 'html.parser')
    urls = [a['href'] for a in soup.find_all('a', href=True, class_='gse_alrt_title') if a['href'].startswith('http')]

    # Resolve final URLs for any redirects
    final_urls = []
    for url in urls:
        final_url = get_final_url(url)
        if final_url:
            final_urls.append(final_url)
    
    return final_urls


def firecrawl_submit_crawl(url):
    logging.info(f"Submitting crawl job for URL: {url}")
    try:
        response = requests.post(
            f'{FIRECRAWL_API_URL}/crawl',
            headers={
                'Content-Type': 'application/json',
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
            }
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logging.error(f"Error checking crawl job: {e}")
    return None

def firecrawl_crawl(url):
    logging.info(f"Processing URL: {url}")
    job_id = firecrawl_submit_crawl(url)
    if not job_id:
        return None

    max_attempts = 12  # 1 minute total waiting time
    for _ in range(max_attempts):
        result = firecrawl_check_crawl(job_id)
        if result and result['status'] == 'completed':
            return {"markdown":result['data'][0]['markdown'] ,"metadata":result['data'][0]['metadata']} # Assuming we want the first page's markdown
        elif result and result['status'] == 'failed':
            logging.error(f"Crawl job failed for URL: {url}")
            return None
        time.sleep(10)  # Wait for 5 seconds before checking again
    
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

def translate_text_with_title(content):
    prompt = (
        f"请将以下论文内容提取标题、摘要并翻译成中文。"
        f"返回时包括以下信息：\n"
        f"1. 原始标题\n"
        f"2. 原始摘要内容\n"
        f"3. 翻译后的标题\n"
        f"4. 翻译后的摘要\n\n"
        f"{content}"
    )
    return ollama_request(prompt) or "翻译失败"

def summarize_paper_with_title(content):
    prompt = (
        f"请分析以下论文内容，并按以下要求总结：\n"
        f"1. 背景\n"
        f"2. 解决的问题\n"
        f"3. 提出的方法\n"
        f"4. 创新点\n"
        f"返回时包括翻译后的标题和总结内容：\n\n"
        f"{content}"
    )
    return ollama_request(prompt) or "摘要总结失败"

def process_paper(url):
    markdown_content = firecrawl_crawl(url)
    logging.info(f"Processing paper markdown_content: {markdown_content}")
    if markdown_content:
        translated_content = translate_text_with_title(markdown_content)
        summary = summarize_paper_with_title(translated_content)
        return {
            'url': url,
            'original_content': markdown_content,
            'translated_content': translated_content,
            'summary': summary
        }
    return None

def main():
    mail, email_ids = get_emails()
    if not mail or len(email_ids) == 0:
        logging.info("No emails found or connection failed.")
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
                f.write(f"## 原始内容\n{result['original_content']}\n\n")
                f.write(f"## 译文内容\n{result['translated_content']}\n\n")
                f.write(f"## 论文总结\n{result['summary']}\n\n")
                f.write("---\n\n")

if __name__ == "__main__":
    main()
