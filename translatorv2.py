#!/usr/bin/env python3
import os
import base64
import datetime
import re
import time # Toegevoegd voor retry delay
from bs4 import BeautifulSoup
from email.mime.text import MIMEText
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from openai import OpenAI, APIError, APIConnectionError, RateLimitError, InternalServerError # Specifieke exceptions toegevoegd
from dotenv import load_dotenv

load_dotenv()

def env_flag(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}

def get_llm_config():
    provider = os.getenv("LLM_PROVIDER", "openai").strip().lower()

    if provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        model = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
        base_url = os.getenv("OPENAI_BASE_URL")
    elif provider == "deepseek":
        api_key = os.getenv("DEEPSEEK_API_KEY")
        model = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
        base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    else:
        raise ValueError(
            "Unsupported LLM_PROVIDER. Use 'openai' or 'deepseek'."
        )

    if not api_key:
        raise ValueError(
            f"Missing API key for provider '{provider}'. "
            f"Set {'OPENAI_API_KEY' if provider == 'openai' else 'DEEPSEEK_API_KEY'}."
        )

    return {
        "provider": provider,
        "model": model,
        "base_url": base_url,
        "api_key": api_key,
    }

LLM_CONFIG = get_llm_config()
client = OpenAI(
    api_key=LLM_CONFIG["api_key"],
    base_url=LLM_CONFIG["base_url"],
)

SCOPES = ['https://www.googleapis.com/auth/gmail.modify']
TARGET_EMAILS = [
    "baskalter@gmail.com",
    "kalter44@hotmail.com",
    "eric.kalter@gmail.com",
    "sparkimark@hotmail.com"
]
FORWARD_TO = ["baskalter@gmail.com", "kalter44@hotmail.com"]
TEST_SUBJECT_CONTAINS = os.getenv("TEST_SUBJECT_CONTAINS", "").strip()
TEST_FROM = os.getenv("TEST_FROM", "").strip().lower()
TEST_FORWARD_TO = os.getenv("TEST_FORWARD_TO", "baskalter@hotmail.com").strip()
TEST_MARK_READ = env_flag("TEST_MARK_READ", default=False)
TEST_MODE = bool(TEST_SUBJECT_CONTAINS or TEST_FROM)

def translate_to_dutch(text):
    max_retries = 10
    retry_delay_seconds = 600 # 10 minuten
    last_exception = None

    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=LLM_CONFIG["model"],
                messages=[
                    {"role": "system", "content": "You are a professional Dutch translator."},
                    {"role": "user", "content": f"Translate the following text to Dutch:\n\n{text}"}
                ],
                temperature=0.3,
            )
            return response.choices[0].message.content.strip()
        except (InternalServerError, APIConnectionError, RateLimitError) as e:
            last_exception = e
            print(f"OpenAI API error: {e}. Attempt {attempt + 1} of {max_retries}. Retrying in {retry_delay_seconds} seconds...")
            time.sleep(retry_delay_seconds)
        except APIError as e: # Vang andere generieke API fouten
            last_exception = e
            print(f"General OpenAI API error: {e}. Attempt {attempt + 1} of {max_retries}. Retrying in {retry_delay_seconds} seconds...")
            time.sleep(retry_delay_seconds)
        except Exception as e: # Vang onverwachte fouten
            print(f"An unexpected error occurred during translation: {e}")
            raise # Her-raise onverwachte fouten direct

    if last_exception:
        print(f"Failed to translate after {max_retries} attempts.")
        raise last_exception # Her-raise de laatst opgevangen OpenAI fout

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
    message['to'] = ", ".join(to) if isinstance(to, list) else to
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

def build_search_query():
    if TEST_MODE:
        query_parts = []
        if TEST_SUBJECT_CONTAINS:
            escaped_subject = TEST_SUBJECT_CONTAINS.replace('"', '\\"')
            query_parts.append(f'subject:"{escaped_subject}"')
        if TEST_FROM:
            query_parts.append(f"from:{TEST_FROM}")
        return " ".join(query_parts)

    after = get_month_range()
    return f"is:unread after:{after}"

def subject_matches_test_filter(subject):
    if not TEST_SUBJECT_CONTAINS:
        return True
    return TEST_SUBJECT_CONTAINS.lower() in subject.lower()

def sender_matches_test_filter(sender):
    if not TEST_FROM:
        return True
    return TEST_FROM in sender.lower()

def run():
    print(
        f"Using LLM provider '{LLM_CONFIG['provider']}' with model '{LLM_CONFIG['model']}'."
    )
    if TEST_MODE:
        print(
            "Test mode enabled "
            f"(subject contains: '{TEST_SUBJECT_CONTAINS or '*'}', "
            f"from: '{TEST_FROM or '*'}')."
        )

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
    query = build_search_query()
    list_kwargs = {
        'userId': user_id,
        'q': query,
    }
    if TEST_MODE:
        list_kwargs['maxResults'] = 25

    results = service.users().messages().list(**list_kwargs).execute()
    messages = results.get('messages', [])

    if TEST_MODE and messages:
        messages = list(reversed(messages))
    elif TEST_MODE:
        print("Test mode found no candidate messages.")
        return

    test_translation_sent = False

    for msg in messages:
        try:
            msg_data = service.users().messages().get(
                userId=user_id,
                id=msg['id'],
                format='metadata',
                metadataHeaders=['To', 'Cc', 'From', 'Subject']
            ).execute()
        except Exception as e:
            print(f"Skipping message {msg['id']} due to error: {e}")
            continue

        headers = {h['name']: h['value'] for h in msg_data['payload']['headers']}
        subject_header = headers.get('Subject', 'No Subject')
        from_header = headers.get('From', '')

        if TEST_MODE:
            if not subject_matches_test_filter(subject_header):
                continue
            if not sender_matches_test_filter(from_header):
                continue

        to = headers.get('To', '').lower()
        cc = headers.get('Cc', '').lower()
        recipients = f"{to},{cc}"

        if not TEST_MODE and not all(email.lower() in recipients for email in TARGET_EMAILS):
            continue

        try:
            full_msg = service.users().messages().get(userId=user_id, id=msg['id'], format='full').execute()
        except Exception as e:
            print(f"Skipping full message fetch for {msg['id']} due to error: {e}")
            continue

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
                # Als een segment hier faalt na 10x10min, stopt het hele script.
                # Dit is volgens de wens om pas een error mail te krijgen na langdurige problemen.
                translated_segment = translate_to_dutch(original)
                tag.string = translated_segment
                # Als je wilt dat het script doorgaat met de volgende mail bij een segmentfout,
                # dan moet hier alsnog een try-except (InternalServerError, etc.) omheen.
                # Voor nu laten we het zo dat het script stopt.

        html_with_translation = str(soup)

        subject = sanitize_subject(subject_header)
        provider_label = LLM_CONFIG["provider"]
        forward_recipients = [TEST_FORWARD_TO] if TEST_MODE else FORWARD_TO
        forward_subject = f"Translated ({provider_label.upper()}, NLD): {subject}"
        forward_msg = create_message(forward_recipients, forward_subject, html_with_translation, html=True)
        service.users().messages().send(userId=user_id, body=forward_msg).execute()

        if TEST_MODE:
            test_translation_sent = True
            print(
                f"Test translation forwarded for message {msg['id']} "
                f"to {TEST_FORWARD_TO}."
            )
            if TEST_MARK_READ:
                service.users().messages().modify(
                    userId=user_id,
                    id=msg['id'],
                    body={'removeLabelIds': ['UNREAD']}
                ).execute()
            break

        service.users().messages().modify(
            userId=user_id,
            id=msg['id'],
            body={'removeLabelIds': ['UNREAD']}
        ).execute()

    if TEST_MODE and not test_translation_sent:
        print("Test mode did not find a message matching the requested filters.")

if __name__ == '__main__':
    run()
