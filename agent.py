import os
import base64
import requests
import concurrent.futures
import logging
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from bs4 import BeautifulSoup
from serpapi import GoogleSearch
import markdown
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Gmail API 设置
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def get_gmail_service():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('gmail', 'v1', credentials=creds)

def get_unread_scholar_emails(service):
    try:
        results = service.users().messages().list(userId='me', q='is:unread label:Scholar').execute()
        messages = results.get('messages', [])
        return messages
    except Exception as e:
        logging.error(f"Error fetching unread emails: {e}")
        return []

def get_email_content(service, msg_id):
    try:
        message = service.users().messages().get(userId='me', id=msg_id, format='full').execute()
        payload = message['payload']
        if 'parts' in payload:
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    data = part['body']['data']
                    return base64.urlsafe_b64decode(data).decode()
        elif 'body' in payload:
            data = payload['body']['data']
            return base64.urlsafe_b64decode(data).decode()
        return ''
    except Exception as e:
        logging.error(f"Error getting email content: {e}")
        return ''

def extract_paper_urls(content):
    soup = BeautifulSoup(content, 'html.parser')
    urls = [a['href'] for a in soup.find_all('a', href=True) if 'scholar.google.com' in a['href']]
    return urls

def get_paper_info(url):
    try:
        params = {
            "engine": "google_scholar",
            "q": url,
            "api_key": os.getenv("SERPAPI_API_KEY")
        }
        search = GoogleSearch(params)
        results = search.get_dict()
        if 'organic_results' in results and results['organic_results']:
            paper = results['organic_results'][0]
            return {
                'title': paper.get('title', ''),
                'abstract': paper.get('snippet', '')
            }
    except Exception as e:
        logging.error(f"Error fetching paper info: {e}")
    return None

def translate_text(text):
    try:
        response = requests.post('http://localhost:11434/api/chat', json={
            "model": "llama3",
            "messages": [
                {
                    "role": "user",
                    "content": f"请将以下文本翻译成中文：\n\n{text}"
                }
            ],
            "stream": False
        })
        return response.json()['message']['content']
    except Exception as e:
        logging.error(f"Error translating text: {e}")
        return "翻译失败"

def summarize_paper(abstract):
    try:
        response = requests.post('http://localhost:11434/api/chat', json={
            "model": "llama3",
            "messages": [
                {
                    "role": "user",
                    "content": f"请分析以下论文摘要，并提供以下信息：\n1. 当前研究问题是什么？\n2. 采用了什么方法？\n3. 创新点是什么？\n\n摘要：{abstract}"
                }
            ],
            "stream": False
        })
        return response.json()['message']['content']
    except Exception as e:
        logging.error(f"Error summarizing paper: {e}")
        return "摘要总结失败"

def process_paper(url):
    paper_info = get_paper_info(url)
    if paper_info:
        translated_title = translate_text(paper_info['title'])
        translated_abstract = translate_text(paper_info['abstract'])
        summary = summarize_paper(translated_abstract)
        return {
            'original_title': paper_info['title'],
            'translated_title': translated_title,
            'original_abstract': paper_info['abstract'],
            'translated_abstract': translated_abstract,
            'summary': summary
        }
    return None

def main():
    service = get_gmail_service()
    messages = get_unread_scholar_emails(service)

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_to_email = {executor.submit(get_email_content, service, message['id']): message['id'] for message in messages}
        
        all_paper_urls = []
        for future in concurrent.futures.as_completed(future_to_email):
            email_id = future_to_email[future]
            try:
                content = future.result()
                paper_urls = extract_paper_urls(content)
                all_paper_urls.extend(paper_urls)
            except Exception as e:
                logging.error(f"Error processing email {email_id}: {e}")

        future_to_paper = {executor.submit(process_paper, url): url for url in all_paper_urls}
        
        with open('research_summary.md', 'w', encoding='utf-8') as f:
            for future in concurrent.futures.as_completed(future_to_paper):
                url = future_to_paper[future]
                try:
                    result = future.result()
                    if result:
                        f.write(f"# {result['original_title']}\n\n")
                        f.write(f"## 译文标题\n{result['translated_title']}\n\n")
                        f.write(f"## 原文摘要\n{result['original_abstract']}\n\n")
                        f.write(f"## 译文摘要\n{result['translated_abstract']}\n\n")
                        f.write(f"## 论文总结\n{result['summary']}\n\n")
                        f.write("---\n\n")
                except Exception as e:
                    logging.error(f"Error writing results for {url}: {e}")

if __name__ == "__main__":
    main()