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
import threading
import backoff
import faulthandler
import sys
# 导入 LangChain 所需的库
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama.llms import OllamaLLM
from urllib.parse import urlparse, parse_qs, unquote

def print_tracebacks():
    threading.Timer(120, print_tracebacks).start()
    faulthandler.dump_traceback()

# print_tracebacks()






Model = "qwen2.5:14b"
os.environ["OPENAI_API_KEY"] = "your_openai_api_key"
llm = OllamaLLM(model=Model, base_url="http://localhost:11434")

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# QQ邮箱 IMAP 设置
IMAP_SERVER = 'imap.qq.com'
EMAIL_ACCOUNT = os.getenv('QQ_EMAIL')
PASSWORD = os.getenv('QQ_PASSWORD')

# Firecrawl API 设置
FIRECRAWL_API_KEY = os.getenv('FIRECRAWL_API_KEY')
FIRECRAWL_API_URL = 'http://140.143.139.183:3002/v1'

# 定义邮箱过滤条件
SENDER_EMAIL = 'scholaralerts-noreply@google.com'
DAYS_RECENT = 3  # 设置要过滤的最近天数

def create_process_chain():
    template = """
你是一名专业的学术内容处理专家，能够高效地清理、翻译和总结学术论文，确保技术术语的准确性和学术严谨性。

请清理以下网页内容，将其转换为学术论文的格式，然后将清理后的内容翻译成中文，并总结主要内容。
请确保输出的格式中，论文标题使用一级标题（#），其他部分（研究问题、方法、创新点和结论）使用二级标题（##）。

内容如下：

{markdown_content}

输出翻译后的论文内容（中文），格式如下：

# 标题
## 研究问题
## 方法
## 创新点
## 结论

请以 Markdown 格式呈现，不要输出任何无关内容，参考文献也不需要输出。
标题、研究问题、方法、创新点和结论都必须输出中文。
"""
    prompt = ChatPromptTemplate.from_template(template)
    chain = prompt | llm
    return chain

def create_paper_type_chain():
    template = """
你是一名文献领域分类专家，擅长通过分析文献的研究问题、方法和结论，准确判断其所属的学术领域。

请阅读以下论文内容，分析其研究问题、方法和结论，判断该论文属于'大模型/AI Agent'领域还是'室内定位/惯性导航'领域。
请基于论文的核心研究内容和技术领域进行判断，而不是仅仅依赖于关键词。
如果该论文的主要研究内容涉及自然语言处理、生成式模型、人工智能代理、大规模语言模型、检索增强生成（RAG）等，则属于'大模型/AI Agent'领域；
如果主要涉及室内定位技术、惯性导航系统、传感器融合、定位算法、惯性测量等，则属于'室内定位/惯性导航'领域。
如果不属于上述两个领域，请返回'忽略'。

论文内容如下：

{content}

请只输出文献类型：'大模型/AI Agent' 或 '室内定位/惯性导航'；如果不属于这两种类型，返回 '忽略'。不要输出任何其他内容。
"""
    prompt = ChatPromptTemplate.from_template(template)
    chain = prompt | llm
    return chain

@backoff.on_exception(backoff.expo, imaplib.IMAP4.error, max_tries=5)
def get_emails():
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(EMAIL_ACCOUNT, PASSWORD)
        mail.select("inbox")
        result, data = mail.search(None, 'FROM', SENDER_EMAIL)
        email_ids = data[0].split()
        return mail, email_ids
    except Exception as e:
        logging.error(f"Error fetching emails: {e}")
        return None, []

def decode_content(part):
    charset = part.get_content_charset() or 'utf-8'
    payload = part.get_payload(decode=True)

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

        if email_message['From'] and SENDER_EMAIL not in email_message['From']:
            logging.info(f"Email ID {email_id} is not from the expected sender.")
            return None
        subject = email_message['Subject']
        if "新的" not in subject:
            logging.info(f"Email ID {email_id} subject does not contain '新的'.")
            return None

        email_date = parsedate_to_datetime(email_message['Date'])
        now = datetime.now(email_date.tzinfo)
        if email_date < now - timedelta(days=DAYS_RECENT):
            logging.info(f"Email ID {email_id} is older than the specified range.")
            print(f"Email ID {email_id} is older than the specified range.")
            return None

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
        parsed_url = urlparse(input_url)
        query_params = parse_qs(parsed_url.query)
        encoded_url = query_params.get('url', [None])[0]
        
        if not encoded_url:
            logging.error(f"No 'url' parameter found in {input_url}")
            return None

        final_url = unquote(encoded_url)
        logging.info(f"Decoded URL: {final_url}")
        return final_url
    except Exception as e:
        logging.error(f"Error resolving final URL for {input_url}: {e}")
        return None

def extract_urls(content):
    logging.info('Extracting URLs from content')
    soup = BeautifulSoup(content, 'html.parser')
    urls = [a['href'] for a in soup.find_all('a', href=True, class_='gse_alrt_title') if a['href'].startswith('http')]

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
            },
            timeout=15
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
            return {"markdown": result['data'][0]['markdown'], "metadata": result['data'][0]['metadata']}
        elif result and result['status'] == 'failed':
            logging.error(f"Crawl job failed for URL: {url}")
            return None
        time.sleep(10)
    
    logging.error(f"Crawl job timed out for URL: {url}")
    return None

def process_paper(url):
    markdown_content = firecrawl_crawl(url)
    logging.info(f"Processing paper markdown_content: {markdown_content}")
    if markdown_content is not None and markdown_content['markdown'].strip():
        # 创建处理链
        process_chain = create_process_chain()
        result = process_chain.invoke({"markdown_content": markdown_content['markdown']})

        # 判断类型
        paper_type_chain = create_paper_type_chain()
        paper_type = paper_type_chain.invoke({"content": result})
        logging.info(f"Paper type: {paper_type}")
        print(f"Paper type: {paper_type}")
        if "忽略" in paper_type:
            logging.info(f"Ignoring paper from URL: {url}")
            print(f"Ignoring paper from URL: {url}")
            return None

        # 根据类型设置文件名称
        now = datetime.now()
        now_str = now.strftime("%Y%m%d")
        if "大模型/AI Agent" in paper_type:
            output_file = f"{now_str}_大模型"
        elif "室内定位/惯性导航" in paper_type:
            output_file = f"{now_str}_室内定位"
        else:
            logging.warning(f"Unrecognized type for paper from URL: {url}")
            return None

        # 格式化最终输出
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

    # 去重
    all_paper_urls = list(set(all_paper_urls))
    print(f'-----------all size: {len(all_paper_urls)}')

    # 保存所有 URL
    now = datetime.now()
    now_str = now.strftime("%Y%m%d")
    with open(f"{now_str}_all_urls.txt", 'w', encoding='utf-8') as f:
        for url in all_paper_urls:
            f.write(f"{url}\n")

    # 读取已处理的 URL
    sucess_urls = []
    if os.path.exists(f"{now_str}_urls.txt"):
        with open(f"{now_str}_urls.txt", 'r', encoding='utf-8') as f:
            for line in f.readlines():
                sucess_urls.append(line.strip())

    count = 0
    for url in all_paper_urls:
        if url in sucess_urls:
            logging.info(f"URL: {url} has been processed before.")
            count += 1
            print(f'-----------all size: {len(all_paper_urls)} ;current size: {count}------------------')
            continue
        result = process_paper(url)
        if result:
            output_file, formatted_output = result
            # 判断文件是否存在，如果不存在创建文件增加 metadata
            if not os.path.exists(output_file + ".md"):
                with open(output_file + ".md", 'w', encoding='utf-8') as f:
                    f.write(f"--- \nlang: zh-CN \ntitle: {output_file} \ndescription: {output_file} \n--- \n\n")
            with open(output_file + ".md", 'a', encoding='utf-8') as f:
                f.write(f"{formatted_output}\n\n")
            logging.info(f"Processed and wrote result for URL: {url}")
            # 写入成功的 URL
            with open(f"{now_str}_urls.txt", 'a', encoding='utf-8') as f:
                f.write(f"{url}\n")
        else:
            logging.warning(f"Failed to process URL: {url}")
        count += 1
        print(f'-----------all size: {len(all_paper_urls)} ;current size: {count}------------------')

    logging.info("All papers processed.")

if __name__ == "__main__":
    main()
