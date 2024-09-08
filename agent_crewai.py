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
from crewai import Agent, Task, Crew
from langchain_ollama import ChatOllama

# 设置 Ollama API 环境变量
# os.environ["OLLAMA_API_KEY"] = "your_ollama_api_key"
llm = ChatOllama(model="qwen2:7b", base_url="http://localhost:11434")


# 定义内容清理 Agent
clean_content_agent = Agent(
    role="网页内容清理专家",
    goal="清理并结构化网页内容，去除不必要的元素，提取有意义的文本。",
    backstory="你是清理网页内容的专家，专注于将网页内容结构化为清晰、可读的Markdown格式。",
    allow_delegation=False,
    verbose=True,
    llm=llm
)

# 定义翻译 Agent
translate_agent = Agent(
    role="学术翻译专家",
    goal="将清理后的学术内容翻译成中文，确保学术严谨性和清晰度。",
    backstory="你是一名专业翻译，擅长学术文本的翻译，确保技术术语在中文翻译中的准确性。",
    allow_delegation=False,
    verbose=True,
    llm=llm
)

# 定义总结 Agent
summarize_agent = Agent(
    role="研究总结专家",
    goal="总结翻译后的内容，重点包括背景、研究问题、方法和创新点。",
    backstory="你是一名经验丰富的学术研究人员，能够将复杂的论文浓缩为简洁且信息丰富的总结。",
    allow_delegation=False,
    verbose=True,
    llm=llm
)

def create_clean_content_task(markdown_content):
    return Task(
        description=f"清理并结构化以下网页内容，将其转换为学术论文的格式：\n\n{markdown_content}",
        agent=clean_content_agent,
        expected_output="输出论文内容，包含：标题、摘要、引言、方法、结果、结论。用Markdown格式输出。"
    )

def create_translate_task():
    return Task(
        description="将清理后的网页内容翻译成中文，保持Markdown的结构和学术术语的准确性。",
        agent=translate_agent,
        expected_output="翻译后的学术内容（中文），以Markdown格式呈现，保留原始结构和标题。"
    )

def create_summarize_task():
    return Task(
        description="总结翻译后的网页内容，总结的格式：\n\n# 标题\n## 研究问题\n## 提出方法\n## 创新点\n\n确保每个部分保持原意。",
        agent=summarize_agent,
        expected_output="总结后的论文内容，以Markdown格式呈现，保留原始结构和标题。"
    )

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

    max_attempts = 20  # 1 minute total waiting time
    for _ in range(max_attempts):
        result = firecrawl_check_crawl(job_id)
        if result and result['status'] == 'completed':
            return {"markdown":result['data'][0]['markdown'] ,"metadata":result['data'][0]['metadata']} # Assuming we want the first page's markdown
        elif result and result['status'] == 'failed':
            logging.error(f"Crawl job failed for URL: {url}")
            return None
        time.sleep(6)  # Wait for 5 seconds before checking again
    
    logging.error(f"Crawl job timed out for URL: {url}")
    return None




def process_paper(url):
    markdown_content = firecrawl_crawl(url)
    logging.info(f"Processing paper markdown_content: {markdown_content}")
    if markdown_content and markdown_content['markdown']:
        crew = Crew(
            agents=[clean_content_agent, translate_agent, summarize_agent],
            tasks=[
                create_clean_content_task(markdown_content['markdown']),
                create_translate_task(),
                create_summarize_task()
            ]
        )

        result = crew.kickoff()
        
        # Format the final output
        formatted_output = f"""
        {result}
        ## 原文链接
        {url}
        """
        return formatted_output
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
    # 取年月日 时分秒作为文件名
    now = datetime.now()
    now_str = now.strftime("%Y%m%d%H%M%S")
    with open(now_str+'.md', 'w', encoding='utf-8') as f:
        for result in results:
            if result:
                f.write(f"{result}\n\n")
            

if __name__ == "__main__":
    main()
