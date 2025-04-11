# end product?
#!/usr/bin/env python3
import os
import base64
import datetime
import re
import html
from bs4 import BeautifulSoup
from email.mime.text import MIMEText
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SCOPES = ['https://www.googleapis.com/auth/gmail.modify']
TARGET_EMAILS = [
    "baskalter@gmail.com",
    "kalter44@hotmail.com",
    "eric.kalter@gmail.com",
    "sparkimark@hotmail.com"
]
FORWARD_TO = "kalter44@hotmail.com"

def translate_to_dutch(text):
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a professional Dutch translator."},
            {"role": "user", "content": f"Translate the following text to Dutch:\n\n{text}"}
        ],
        temperature=0.3,
    )
    return response.choices[0].message.content.strip()

def get_service():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('gmail', 'v1', credentials=creds)

def get_month_range():
    now = datetime.datetime.now()
    start = datetime.datetime(now.year, now.month, 1)
    return int(start.timestamp())

def sanitize_subject(subject):
    return re.sub(r'[^a-zA-Z0-9 ]', '', subject)

def create_message(to, subject, message_text, html=False):
    if html:
        message = MIMEText(message_text, 'html')
    else:
        message = MIMEText(message_text)
    message['to'] = to
    message['subject'] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    return {'raw': raw}

def extract_html_from_parts(parts):
    for part in parts:
        if part['mimeType'] == 'text/html' and 'data' in part['body']:
            return base64.urlsafe_b64decode(part['body']['data']).decode()
        elif 'parts' in part:
            nested = extract_html_from_parts(part['parts'])
            if nested:
                return nested
    return ""

def run():
    def extract_text_from_parts(parts):
        for part in parts:
            if part['mimeType'] == 'text/html' and 'data' in part['body']:
                return base64.urlsafe_b64decode(part['body']['data']).decode()
            elif 'parts' in part:
                nested = extract_text_from_parts(part['parts'])
                if nested:
                    return nested
        return ""

    service = get_service()
    user_id = 'me'
    after = get_month_range()
    query = f"is:unread after:{after}"

    results = service.users().messages().list(userId=user_id, q=query).execute()
    messages = results.get('messages', [])

    for msg in messages:
        msg_data = service.users().messages().get(userId=user_id, id=msg['id'], format='metadata', metadataHeaders=['To', 'Cc', 'From', 'Subject']).execute()
        headers = {h['name']: h['value'] for h in msg_data['payload']['headers']}
        to = headers.get('To', '').lower()
        cc = headers.get('Cc', '').lower()
        recipients = f"{to},{cc}"

        if not all(email.lower() in recipients for email in TARGET_EMAILS):
            continue

        full_msg = service.users().messages().get(userId=user_id, id=msg['id'], format='full').execute()
        payload = full_msg['payload']
        parts = payload.get('parts', [])
        message_body = ""

        if 'data' in payload.get('body', {}):
            message_body = base64.urlsafe_b64decode(payload['body']['data']).decode()
        elif parts:
            message_body = extract_text_from_parts(parts)
        else:
            message_body = ""

        html_content = extract_html_from_parts(parts)
        soup = BeautifulSoup(html_content or message_body, "html.parser")
        text_blocks = soup.get_text(separator="\n").strip().split("\n")
        cleaned_lines = []

        skip_patterns = re.compile(
            r'(read in app|comment|share|like|unsubscribe|author|date|support|gift|reaction|'
            r'https://substackcdn\.com|\.png|\.jpg|\.svg|restack|subscribed|start writing|©|market street|pm[bB])',
            re.IGNORECASE
        )

        for line in text_blocks:
            line = line.strip()
            if not line or skip_patterns.search(line):
                continue
            if line.lower() in {'give', 'start', 'subscribed', 'restack'}:
                continue
            if line.startswith('http') and 'substackcdn' in line:
                continue
            cleaned_lines.append(line)

        cleaned_text = ' '.join(cleaned_lines)
        cleaned_text = re.sub(r'\s{2,}', ' ', cleaned_text).strip()
        translated_text = translate_to_dutch(cleaned_text)

        for tag in soup.find_all(["p", "span", "li", "h1", "h2", "h3"]):
            original = tag.get_text(strip=True)
            if original and len(original) > 20 and "unsubscribe" not in original.lower():
                translated = translate_to_dutch(original)
                tag.string = translated

        html_with_translation = str(soup)

        subject = sanitize_subject(headers.get('Subject', 'No Subject'))
        forward_msg = create_message(FORWARD_TO, f"Translated (NLD): {subject}", html_with_translation, html=True)
        service.users().messages().send(userId=user_id, body=forward_msg).execute()
        
        service.users().messages().modify(
            userId=user_id,
            id=msg['id'],
            body={'removeLabelIds': ['UNREAD']}
        ).execute()

if __name__ == '__main__':
    run()
