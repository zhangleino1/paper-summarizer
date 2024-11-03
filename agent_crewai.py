import os
import time
import requests
import logging
import imaplib
import email
from email import policy
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
from crewai import Agent, Task, Crew,LLM
from crewai.telemetry import Telemetry

import faulthandler

faulthandler.enable()
import threading
def print_tracebacks():
    threading.Timer(120, print_tracebacks).start()  # 每5秒打印一次
    faulthandler.dump_traceback()

print_tracebacks()


def noop(*args, **kwargs):
    print("Telemetry method called and noop'd\n")
    pass


for attr in dir(Telemetry):
    if callable(getattr(Telemetry, attr)) and not attr.startswith("__"):
        setattr(Telemetry, attr, noop)

Model = "ollama/qwen2.5:14b"
# 设置 Ollama API 环境变量
# os.environ["OLLAMA_API_KEY"] = "your_ollama_api_key"
os.environ["OPENAI_API_KEY"] = "your_openai_api_key"
llm = LLM(model=Model, base_url="http://localhost:11434",api_key="your_openai_api_key")
os.environ["OTEL_SDK_DISABLED"] = "True"
os.environ['CREWAI_TELEMETRY_OPT_OUT'] = 'FALSE'
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
DAYS_RECENT = 11  # Set this to the number of recent days you want to filter emails by



os.environ['CREWAI_DISABLE_TELEMETRY'] = 'true'


def process_agent():
    return Agent(
        role="学术内容处理专家",
        goal="清理网页内容，将其翻译成中文，并总结主要内容，重点包括标题、研究问题、方法、创新点和结论。",
        backstory="你是一名专业的学术内容处理专家，能够高效地清理、翻译和总结学术论文，确保技术术语的准确性和学术严谨性。",
        allow_delegation=False,
        verbose=True,
        llm=llm
    )

def create_process_task(markdown_content):
    return Task(
        description=(
            f"请清理以下网页内容，将其转换为学术论文的格式，然后将清理后的内容翻译成中文，并总结主要内容。"
            f"请确保输出的格式中，论文标题使用一级标题（#），其他部分（研究问题、方法、创新点和结论）使用二级标题（##）。"
            f"\n\n内容如下：\n\n{markdown_content}"
        ),
        agent=process_agent(),
        expected_output=(
            "输出翻译后的论文内容（中文），格式如下：\n\n"
            "# 标题\n"
            "## 研究问题\n"
            "## 方法\n"
            "## 创新点\n"
            "## 结论\n\n"
            "请以 Markdown 格式呈现，不要输出任何无关内容，参考文献也不需要输出。"
        )
    )



def paper_type_agent():
    return Agent(
        role="文献领域分类专家",
        goal="根据文献的研究内容，判断其属于'大模型/AI Agent'还是'室内定位/惯性导航'领域。",
        backstory="你是一名文献领域分类专家，擅长通过分析文献的研究问题、方法和结论，准确判断其所属的学术领域。",
        allow_delegation=False,
        verbose=True,
        llm=llm,
    )

def create_paper_type_task(content):
    return Task(
        description=(
            f"请阅读以下论文内容，分析其研究问题、方法和结论，判断该论文属于'大模型/AI Agent'领域还是'室内定位/惯性导航'领域。"
            f"请基于论文的核心研究内容和技术领域进行判断，而不是仅仅依赖于关键词。"
            f"如果该论文的主要研究内容涉及自然语言处理、生成式模型、人工智能代理、大规模语言模型、检索增强生成（RAG）等，则属于'大模型/AI Agent'领域；"
            f"如果主要涉及室内定位技术、惯性导航系统、传感器融合、定位算法、惯性测量等，则属于'室内定位/惯性导航'领域。"
            f"如果不属于上述两个领域，请返回'忽略'。"
            f"\n\n论文内容如下：\n\n{content}"
        ),
        agent=paper_type_agent(),
        expected_output=(
            "请只输出文献类型：'大模型/AI Agent' 或 '室内定位/惯性导航'；"
            "如果不属于这两种类型，返回 '忽略'。不要输出任何其他内容。"
        )
    )



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
        print(f"Fetching email ID: {email_id}")
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
        subject = email_message['Subject']
        if "新的" not in subject:
            logging.info(f"Email ID {email_id} subject does not contain '新的'.")
            return None

        # Check the date
        email_date = parsedate_to_datetime(email_message['Date'])
        now = datetime.now(email_date.tzinfo)
        if email_date < now - timedelta(days=DAYS_RECENT):
            logging.info(f"Email ID {email_id} is older than the specified range.")
            print(f"Email ID {email_id} is older than the specified range.")
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
    print(f"Submitting crawl job for URL: {url}")
    try:
        response = requests.post(
            f'{FIRECRAWL_API_URL}/crawl',
            headers={
                'Content-Type': 'application/json',
            },
            json={
                'url': url,
                'limit': 1,
                'scrapeOptions': {
                    'formats': ['markdown']
                },
                "maxDepth": 0,
                "limit": 1,
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
    logging.info(f"Checking crawl job: {job_id}")
    print(f"Checking crawl job: {job_id}")
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
    print(f"Processing URL: {url}")
    job_id = firecrawl_submit_crawl(url)
    if not job_id:
        return None

    max_attempts = 120  # 1 minute total waiting time
    for _ in range(max_attempts):
        result = firecrawl_check_crawl(job_id)
        logging.info(f"Crawl job result: {result}") 
        print(f"Crawl job result: {result}") 
        if result and result['status'] == 'completed':
            return {"markdown":result['data'][0]['markdown'] ,"metadata":result['data'][0]['metadata']} # Assuming we want the first page's markdown
        elif result and result['status'] == 'failed':
            logging.error(f"Crawl job failed for URL: {url}")
            return None
        time.sleep(10)  # Wait for 5 seconds before checking again
    
    logging.error(f"Crawl job timed out for URL: {url}")
    return None




def process_paper(url):
    markdown_content = firecrawl_crawl(url)
    logging.info(f"Processing paper markdown_content: {markdown_content}")
    if markdown_content is not None  and markdown_content['markdown'].strip():
        
        # 添加类型判断
        crew = Crew(
                agents=[process_agent()],
                tasks=[create_process_task(markdown_content['markdown'])],
                share_crew=False,
                verbose=True
            )

        result = crew.kickoff().raw
        
        # 判断类型
        paper_type_crew = Crew(
            agents=[paper_type_agent()],
            tasks=[create_paper_type_task(result)],
            share_crew=False,
            verbose=True
        )
        paper_type = paper_type_crew.kickoff().raw
        logging.info(f"Paper type: {paper_type}")
        print(f"Paper type: {paper_type}")
        if "忽略" in paper_type :
            logging.info(f"Ignoring paper from URL: {url}")
            print(f"Ignoring paper from URL: {url}")
            return None

        # 根据类型设置文件名称
        now = datetime.now()
        now_str = now.strftime("%Y%m%d")
        if "大模型/AI Agent" in paper_type  :
            output_file = f"{now_str}_大模型"
        elif "室内定位/惯性导航" in paper_type :
            output_file = f"{now_str}_室内定位"
        else:
            logging.warning(f"Unrecognized type for paper from URL: {url}")
            return None

        # Format the final output
        formatted_output = f"""{result} \n\n## 原文链接\n{url} \n\n"""
        return output_file, formatted_output
    return None

def main():
    mail, email_ids = get_emails()
    if not mail or len(email_ids) == 0:
        logging.info("No emails found or connection failed.")
        return

    all_paper_urls = []
    for email_id in email_ids:
        content = fetch_email_content(mail, email_id)
        if content:
            all_paper_urls.extend(extract_urls(content))
    # print size
    print(f'-----------all size: {len(all_paper_urls)}')
    # all_paper_urls 写入文件
    now = datetime.now()
    now_str = now.strftime("%Y%m%d")
    with open(f"{now_str}_all_urls.txt", 'w', encoding='utf-8') as f:
        for url in all_paper_urls:
            f.write(f"{url}\n")

    # 根据今天的日期获取对应的文件，读取文件内容，返回一个数组 对应元素是Url
    # 读取文件内容
    sucess_urls = []
    now = datetime.now()
    now_str = now.strftime("%Y%m%d")
    if  os.path.exists(f"{now_str}_urls.txt"):
        with open(f"{now_str}_urls.txt", 'r', encoding='utf-8') as f:
            for line in f.readlines():
                sucess_urls.append(line.strip())

    count = 0;
    for url in all_paper_urls:
        if url in sucess_urls:
            logging.info(f"URL: {url} has been processed before.")
            count += 1
            print(f'-----------all size: {len(all_paper_urls)} ;current size: {count}------------------')
            continue
        result = process_paper(url)
        if result:
            output_file, formatted_output = result
            # 判断文件是否存在，如果不存在创建文件增加metadata
            if not os.path.exists(output_file+".md"):
                with open(output_file+".md", 'w', encoding='utf-8') as f:
                    f.write(f"--- \nlang: zh-CN \ntitle: {output_file} \ndescription: {output_file} \n--- \n\n")
            with open(output_file+".md", 'a', encoding='utf-8') as f:
                f.write(f"{formatted_output}\n\n")
            logging.info(f"Processed and wrote result for URL: {url}")
            # 写入成功的url
            with open(f"{now_str}_urls.txt", 'a', encoding='utf-8') as f:
                f.write(f"{url}\n")
        else:
            logging.warning(f"Failed to process URL: {url}")
        count += 1
        # print all and current count
        print(f'-----------all size: {len(all_paper_urls)} ;current size: {count}------------------')

    logging.info("All papers processed.")
            

if __name__ == "__main__":
    main()
