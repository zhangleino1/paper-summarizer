import os
import requests
import base64
import concurrent.futures
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from bs4 import BeautifulSoup
from serpapi import GoogleSearch

# Google API设置
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
TOKEN_PATH = 'token.json'
CREDENTIALS_PATH = 'credentials.json'

def gmail_authenticate():
    """通过Google API进行认证"""
    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, 'w') as token:
            token.write(creds.to_json())
    return build('gmail', 'v1', credentials=creds)

def get_unread_emails(service):
    """获取未读的谷歌学术订阅邮件"""
    results = service.users().messages().list(userId='me', q='from:scholaralerts-noreply@google.com is:unread').execute()
    messages = results.get('messages', [])
    email_data = []
    if not messages:
        print("No new emails found.")
    else:
        for msg in messages:
            msg_id = msg['id']
            message = service.users().messages().get(userId='me', id=msg_id).execute()
            payload = message['payload']
            headers = payload.get("headers")
            for header in headers:
                if header.get('name') == 'Subject':
                    subject = header.get('value')
            parts = payload.get("parts")[0]
            data = parts['body']['data']
            decoded_data = base64.urlsafe_b64decode(data).decode('utf-8')
            email_data.append({
                'id': msg_id,
                'subject': subject,
                'body': decoded_data
            })
    return email_data

def extract_paper_urls(email_body):
    """从邮件正文中提取论文链接"""
    soup = BeautifulSoup(email_body, 'html.parser')
    urls = []
    for link in soup.find_all('a', href=True):
        if "scholar.google.com" in link['href']:
            urls.append(link['href'])
    return urls

def fetch_paper_details(url):
    """抓取论文的标题和摘要"""
    search = GoogleSearch({
        "q": url,
        "api_key": "YOUR_SERPAPI_KEY"
    })
    results = search.get_dict()
    soup = BeautifulSoup(results['organic_results'][0]['snippet'], 'html.parser')
    title = soup.title.string if soup.title else "No title found"
    abstract = soup.find('meta', {'name': 'description'})['content'] if soup.find('meta', {'name': 'description'}) else "No abstract found"
    return title, abstract

def translate_text(text):
    """使用Ollama大模型翻译文本"""
    response = requests.post(
        "http://localhost:11434/api/chat",
        json={
            "model": "llama3",
            "messages": [{"role": "user", "content": f"Translate this: {text}"}],
            "stream": False
        }
    )
    result = response.json()
    return result['message']['content']

def analyze_abstract(abstract):
    """使用Ollama大模型整理摘要"""
    response = requests.post(
        "http://localhost:11434/api/chat",
        json={
            "model": "llama3",
            "messages": [{"role": "user", "content": f"Analyze this abstract: {abstract}"}],
            "stream": False
        }
    )
    result = response.json()
    return result['message']['content']

def format_markdown(title, original_abstract, translated_abstract, analysis):
    """将结果输出为Markdown格式"""
    markdown_text = f"# {title}\n\n**Original Abstract:**\n{original_abstract}\n\n**Translated Abstract:**\n{translated_abstract}\n\n**Analysis:**\n{analysis}\n"
    return markdown_text

def process_paper(url):
    """处理每篇论文，抓取详情，翻译和分析"""
    title, original_abstract = fetch_paper_details(url)
    translated_abstract = translate_text(original_abstract)
    analysis = analyze_abstract(translated_abstract)
    return format_markdown(title, original_abstract, translated_abstract, analysis)

def main():
    service = gmail_authenticate()
    emails = get_unread_emails(service)

    for email in emails:
        print(f"Processing email: {email['subject']}")
        paper_urls = extract_paper_urls(email['body'])
        
        with concurrent.futures.ThreadPoolExecutor() as executor:
            markdown_results = list(executor.map(process_paper, paper_urls))
        
        for result in markdown_results:
            print(result)
            # 这里你可以将result保存到文件或数据库

if __name__ == "__main__":
    main()
