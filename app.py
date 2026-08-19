import os
import re
import json
import base64
from datetime import datetime
from email.mime.text import MIMEText

import gspread
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from serpapi import GoogleSearch
from openai import OpenAI


# ============================================================
# CONFIGURATION
# ============================================================

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY") or os.getenv("SERPAPI_KEY")

SHEET_NAME = os.getenv("SHEET_NAME", "Hospital Support Emails")

KNOWLEDGE_BASE_FILE = os.getenv(
    "KNOWLEDGE_BASE_FILE",
    "knowledge_base.txt"
)

GOOGLE_CREDENTIALS_FILE = "credentials.json"
GOOGLE_TOKEN_FILE = "token.json"

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

CONFIDENCE_THRESHOLD = 70

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]


# ============================================================
# CLIENT
# ============================================================

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY is missing from .env")

if not SERPAPI_API_KEY:
    raise RuntimeError("SERPAPI_API_KEY is missing from .env")

client = OpenAI(api_key=OPENAI_API_KEY)


# ============================================================
# GOOGLE AUTHENTICATION
# ============================================================

def connect_google():
    print("🔄 Connecting to Google...")

    creds = None

    if os.path.exists(GOOGLE_TOKEN_FILE):
        try:
            creds = Credentials.from_authorized_user_file(
                GOOGLE_TOKEN_FILE,
                SCOPES
            )
        except Exception:
            creds = None

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception:
            creds = None

    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(
            GOOGLE_CREDENTIALS_FILE,
            SCOPES
        )

        creds = flow.run_local_server(
            port=0,
            access_type="offline",
            prompt="consent"
        )

        with open(GOOGLE_TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

    gmail = build(
        "gmail",
        "v1",
        credentials=creds
    )

    sheets_client = gspread.authorize(creds)

    # Confirm connected Gmail account
    profile = gmail.users().getProfile(
        userId="me"
    ).execute()

    connected_email = profile.get("emailAddress")

    print(f"📧 Connected Gmail: {connected_email}")
    print("✅ Gmail connected")
    print("✅ Google Sheets connected")

    return gmail, sheets_client


# ============================================================
# KNOWLEDGE BASE
# ============================================================

def load_knowledge_base():
    if not os.path.exists(KNOWLEDGE_BASE_FILE):
        print("⚠️ Knowledge base file not found.")
        return ""

    with open(
        KNOWLEDGE_BASE_FILE,
        "r",
        encoding="utf-8"
    ) as file:
        return file.read()


# ============================================================
# GOOGLE SHEET
# ============================================================

def get_sheet(sheets):
    spreadsheet = sheets.open(SHEET_NAME)
    worksheet = spreadsheet.sheet1

    headers = [
        "Timestamp",
        "From",
        "Subject",
        "Email",
        "Hospital Related",
        "Category",
        "Agent 1 Answer",
        "Agent 1 Confidence",
        "Agent 2 Decision",
        "Agent 2 Confidence",
        "Validation Reason",
        "Web Search Used",
        "Web Search Query",
        "Web Validation Confidence",
        "Agent 3 Response",
        "Final Status",
    ]

    first_row = worksheet.row_values(1)

    if first_row != headers:
        worksheet.clear()
        worksheet.append_row(headers)

    return worksheet


# ============================================================
# EMAIL HELPERS
# ============================================================

def decode_body(data):
    if not data:
        return ""

    try:
        decoded = base64.urlsafe_b64decode(
            data.encode("utf-8")
        ).decode("utf-8", errors="ignore")

        return decoded
    except Exception:
        return ""


def clean_email_body(text):
    if not text:
        return ""

    # Remove CSS
    text = re.sub(
        r"<style.*?>.*?</style>",
        " ",
        text,
        flags=re.DOTALL | re.IGNORECASE
    )

    # Remove scripts
    text = re.sub(
        r"<script.*?>.*?</script>",
        " ",
        text,
        flags=re.DOTALL | re.IGNORECASE
    )

    # Remove HTML
    text = re.sub(
        r"<[^>]+>",
        " ",
        text
    )

    # Remove CSS blocks
    text = re.sub(
        r"\{[^{}]*\}",
        " ",
        text
    )

    # Remove excessive whitespace
    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


def extract_email_body(payload):
    if not payload:
        return ""

    mime_type = payload.get("mimeType", "")

    if mime_type == "text/plain":
        body = payload.get("body", {}).get("data")
        return decode_body(body)

    parts = payload.get("parts", [])

    plain_parts = []

    for part in parts:
        part_type = part.get("mimeType", "")

        if part_type == "text/plain":
            data = part.get("body", {}).get("data")

            if data:
                plain_parts.append(
                    decode_body(data)
                )

        elif part.get("parts"):
            nested = extract_email_body(part)

            if nested:
                plain_parts.append(nested)

    if plain_parts:
        return "\n".join(plain_parts)

    if mime_type == "text/html":
        body = payload.get("body", {}).get("data")

        if body:
            return clean_email_body(
                decode_body(body)
            )

    return ""


def get_header(headers, name):
    for header in headers:
        if header.get("name", "").lower() == name.lower():
            return header.get("value", "")

    return ""


def get_new_email(gmail):
    result = gmail.users().messages().list(
        userId="me",
        q="is:unread",
        maxResults=1
    ).execute()

    messages = result.get("messages", [])

    if not messages:
        return None

    message_id = messages[0]["id"]

    message = gmail.users().messages().get(
        userId="me",
        id=message_id,
        format="full"
    ).execute()

    payload = message.get("payload", {})

    headers = payload.get("headers", [])

    sender = get_header(headers, "From")
    subject = get_header(headers, "Subject")

    body = extract_email_body(payload)

    body = clean_email_body(body)

    return {
        "id": message_id,
        "from": sender,
        "subject": subject,
        "body": body,
    }


def send_email(
    gmail,
    to_email,
    subject,
    body,
    thread_id=None
):
    message = MIMEText(
        body,
        "plain",
        "utf-8"
    )

    message["to"] = to_email
    message["subject"] = subject

    raw_message = base64.urlsafe_b64encode(
        message.as_bytes()
    ).decode("utf-8")

    request_body = {
        "raw": raw_message
    }

    if thread_id:
        request_body["threadId"] = thread_id

    gmail.users().messages().send(
        userId="me",
        body=request_body
    ).execute()


def mark_as_read(gmail, message_id):
    gmail.users().messages().modify(
        userId="me",
        id=message_id,
        body={
            "removeLabelIds": ["UNREAD"]
        }
    ).execute()


# ============================================================
# MEMORY
# ============================================================

def get_memory(sheet):
    try:
        records = sheet.get_all_records()
        return records[-10:]
    except Exception:
        return []


def memory_text(memory):
    if not memory:
        return "No previous conversation history."

    output = []

    for item in memory:
        output.append(
            f"""
Previous email:
From: {item.get('From', '')}
Subject: {item.get('Subject', '')}
Category: {item.get('Category', '')}
Answer: {item.get('Agent 1 Answer', '')}
Final Response: {item.get('Agent 3 Response', '')}
"""
        )

    return "\n".join(output)


# ============================================================
# JSON HELPER
# ============================================================

def extract_json(text):
    if not text:
        return {}

    text = text.strip()

    # Remove markdown fences
    text = re.sub(
        r"```json",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"```",
        "",
        text
    )

    text = text.strip()

    try:
        return json.loads(text)
    except Exception:
        pass

    match = re.search(
        r"\{.*\}",
        text,
        flags=re.DOTALL
    )

    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            pass

    return {}


# ============================================================
# AGENT 1 - RAG AGENT
# ============================================================

def rag_agent(email, knowledge_base, memory):
    print("\n🤖 Agent 1 - RAG Agent")

    prompt = f"""
You are Agent 1, the Hospital RAG Agent.

Your job is to answer hospital patient-support emails using ONLY
the supplied hospital knowledge base and previous memory.

IMPORTANT:

A topic being generally related to a hospital is NOT enough to give
high confidence.

You must determine whether the knowledge base actually contains
information that supports answering the SPECIFIC question.

For example:

If the knowledge base discusses general billing complaints but does
NOT contain the hospital's overseas insurance acceptance policy,
do NOT pretend that the policy is known.

In that case:
- hospital_related = true
- supported_by_knowledge_base = false
- confidence must be below 70

Use confidence as follows:

90-100:
The exact issue/question is clearly supported by the knowledge base.

70-89:
The issue is supported reasonably well, but some details are limited.

40-69:
The email is hospital-related, but the specific answer is not
adequately supported by the knowledge base.

0-39:
Not enough information or unrelated.

NEVER invent hospital policies.

If the specific information is unavailable, say that the information
is not available in the knowledge base and that external validation
is required.

Return ONLY valid JSON:

{{
  "hospital_related": true or false,
  "category": "category",
  "supported_by_knowledge_base": true or false,
  "answer": "answer",
  "confidence": number
}}

EMAIL:
From: {email['from']}
Subject: {email['subject']}
Body:
{email['body']}

KNOWLEDGE BASE:
{knowledge_base}

PREVIOUS MEMORY:
{memory_text(memory)}
"""

    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        temperature=0,
        messages=[
            {
                "role": "system",
                "content": prompt
            }
        ]
    )

    raw = response.choices[0].message.content

    result = extract_json(raw)

    if not result:
        result = {
            "hospital_related": False,
            "category": "UNKNOWN",
            "supported_by_knowledge_base": False,
            "answer": "",
            "confidence": 0
        }

    confidence = float(
        result.get("confidence", 0)
    )

    hospital_related = bool(
        result.get("hospital_related", False)
    )

    supported = bool(
        result.get(
            "supported_by_knowledge_base",
            False
        )
    )

    # ========================================================
    # CRITICAL CONFIDENCE GUARD
    # ========================================================
    #
    # If the model says the specific answer is NOT supported
    # by the KB, we NEVER allow confidence >= 70.
    #
    if hospital_related and not supported:
        confidence = min(
            confidence,
            60
        )

    if not hospital_related:
        confidence = 100

    result["confidence"] = int(
        max(
            0,
            min(
                100,
                confidence
            )
        )
    )

    result["hospital_related"] = hospital_related
    result["supported_by_knowledge_base"] = supported

    print("\n🤖 AGENT 1 RESULT")
    print(
        f"Hospital Related: "
        f"{result['hospital_related']}"
    )
    print(
        f"Category: "
        f"{result.get('category', 'UNKNOWN')}"
    )
    print(
        f"Supported by KB: "
        f"{result.get('supported_by_knowledge_base')}"
    )
    print(
        f"\nAnswer:\n"
        f"{result.get('answer', '')}"
    )
    print(
        f"\nConfidence: "
        f"{result['confidence']}%"
    )

    return result


# ============================================================
# AGENT 2 - VALIDATION AGENT
# ============================================================

def validation_agent(email, rag_result, knowledge_base):
    print("\n🔍 Agent 2 - Validation Agent")

    if not rag_result.get("hospital_related", False):
        result = {
            "decision": "IGNORE_NON_HOSPITAL",
            "confidence": 100,
            "reason": (
                "Email is unrelated to hospital "
                "patient support."
            )
        }

        print("\n🔍 AGENT 2 RESULT")
        print("Validation Confidence: 100%")
        print(
            "Decision: IGNORE_NON_HOSPITAL"
        )
        print(
            f"Reason: {result['reason']}"
        )

        return result

    confidence = rag_result.get(
        "confidence",
        0
    )

    supported = rag_result.get(
        "supported_by_knowledge_base",
        False
    )

    if confidence < CONFIDENCE_THRESHOLD:
        result = {
            "decision": "WEB_SEARCH_REQUIRED",
            "confidence": confidence,
            "reason": (
                "The specific patient question is "
                "not sufficiently supported by the "
                "hospital knowledge base."
            )
        }

    elif not supported:
        result = {
            "decision": "WEB_SEARCH_REQUIRED",
            "confidence": confidence,
            "reason": (
                "The response lacks sufficient "
                "knowledge-base support."
            )
        }

    else:
        result = {
            "decision": "SEND_TO_AGENT_3",
            "confidence": confidence,
            "reason": (
                "Agent 1's response is supported "
                "by the hospital knowledge base."
            )
        }

    print("\n🔍 AGENT 2 RESULT")
    print(
        f"Validation Confidence: "
        f"{result['confidence']}%"
    )
    print(
        f"Decision: "
        f"{result['decision']}"
    )
    print(
        f"Reason: "
        f"{result['reason']}"
    )

    return result


# ============================================================
# SERPAPI WEB SEARCH
# ============================================================

def web_search(query):
    print("\n🌐 SerpAPI Web Search")

    params = {
        "engine": "google",
        "q": query,
        "api_key": SERPAPI_API_KEY,
        "num": 5,
    }

    search = GoogleSearch(params)

    results = search.get_dict()

    organic = results.get(
        "organic_results",
        []
    )

    cleaned = []

    for item in organic[:5]:
        cleaned.append(
            {
                "title": item.get(
                    "title",
                    ""
                ),
                "snippet": item.get(
                    "snippet",
                    ""
                ),
                "link": item.get(
                    "link",
                    ""
                ),
            }
        )

    print(
        f"✅ Found {len(cleaned)} web results"
    )

    return cleaned


# ============================================================
# WEB RESULT VALIDATION
# ============================================================

def validate_web_results(
    email,
    search_results
):
    print("\n🔎 Validating Web Results")

    results_text = "\n\n".join(
        [
            f"""
TITLE: {item['title']}
SNIPPET: {item['snippet']}
URL: {item['link']}
"""
            for item in search_results
        ]
    )

    prompt = f"""
You are the Web Validation Agent for a hospital
customer-support system.

Determine whether the search results actually help
answer the patient's question.

Do NOT invent hospital-specific facts.

Search results:

{results_text}

Patient email:

Subject:
{email['subject']}

Body:
{email['body']}

Return ONLY JSON:

{{
  "confidence": number,
  "decision": "USE_WEB_RESULTS" or "RETRY_SEARCH",
  "reason": "short explanation"
}}

Confidence rules:

90-100 = highly relevant and trustworthy
70-89 = sufficiently relevant
40-69 = partially relevant
0-39 = unrelated
"""

    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        temperature=0,
        messages=[
            {
                "role": "system",
                "content": prompt
            }
        ]
    )

    result = extract_json(
        response.choices[0].message.content
    )

    if not result:
        result = {
            "confidence": 0,
            "decision": "RETRY_SEARCH",
            "reason": "Unable to validate search results."
        }

    print("\n🌐 WEB VALIDATION RESULT")
    print(
        f"Confidence: "
        f"{result.get('confidence', 0)}%"
    )
    print(
        f"Decision: "
        f"{result.get('decision')}"
    )
    print(
        f"Reason: "
        f"{result.get('reason')}"
    )

    return result


# ============================================================
# AGENT 3 - EMAIL RESPONSE AGENT
# ============================================================

def email_response_agent(
    email,
    rag_result,
    web_results=None
):
    print("\n📨 Agent 3 - Email Response Agent")

    web_text = ""

    if web_results:
        web_text = "\n".join(
            [
                f"{item['title']}: "
                f"{item['snippet']}"
                for item in web_results
            ]
        )

    prompt = f"""
You are Agent 3, the Hospital Email Response Agent.

Write a professional, empathetic and concise email
response to the patient.

Patient:
{email['from']}

Subject:
{email['subject']}

Original email:
{email['body']}

Agent 1 category:
{rag_result.get('category', 'UNKNOWN')}

Agent 1 answer:
{rag_result.get('answer', '')}

Validated web information:
{web_text}

Rules:

1. Address the patient's actual concern.
2. Do not invent hospital policies.
3. Do not claim that a specific policy exists unless
   it was actually validated.
4. If web information is general rather than
   hospital-specific, clearly say that the patient
   should confirm the final policy with the hospital.
5. Be professional and empathetic.
6. Do not mention "Agent 1", "Agent 2", "SerpAPI",
   "RAG", "confidence", or internal system details.
7. Keep the response reasonably concise.
8. Sign as:

Best regards,
Hospital Support Team
"""

    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        temperature=0.2,
        messages=[
            {
                "role": "system",
                "content": prompt
            }
        ]
    )

    answer = response.choices[0].message.content.strip()

    print("\n📨 AGENT 3 FINAL EMAIL")
    print("-" * 40)
    print(answer)
    print("-" * 40)

    return answer


# ============================================================
# SAVE TO SHEET
# ============================================================

def save_to_sheet(
    worksheet,
    email,
    rag_result,
    validation_result,
    web_used,
    web_query,
    web_validation_confidence,
    final_response,
    final_status
):
    row = [
        datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        email.get("from", ""),
        email.get("subject", ""),
        email.get("body", ""),
        str(
            rag_result.get(
                "hospital_related",
                False
            )
        ),
        rag_result.get(
            "category",
            ""
        ),
        rag_result.get(
            "answer",
            ""
        ),
        rag_result.get(
            "confidence",
            ""
        ),
        validation_result.get(
            "decision",
            ""
        ),
        validation_result.get(
            "confidence",
            ""
        ),
        validation_result.get(
            "reason",
            ""
        ),
        str(web_used),
        web_query,
        web_validation_confidence,
        final_response,
        final_status,
    ]

    worksheet.append_row(
        row,
        value_input_option="USER_ENTERED"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    gmail, sheets = connect_google()

    worksheet = get_sheet(sheets)

    email = get_new_email(gmail)

    if not email:
        print("\n📭 No unread emails found.")
        return

    print("\n📧 New email found")
    print(
        f"From: {email['from']}"
    )
    print(
        f"Subject: {email['subject']}"
    )
    print(
        f"Message: {email['body']}"
    )

    knowledge_base = load_knowledge_base()

    memory = get_memory(
        worksheet
    )

    # --------------------------------------------------------
    # AGENT 1
    # --------------------------------------------------------

    rag_result = rag_agent(
        email,
        knowledge_base,
        memory
    )

    # --------------------------------------------------------
    # AGENT 2
    # --------------------------------------------------------

    validation_result = validation_agent(
        email,
        rag_result,
        knowledge_base
    )

    web_used = False
    web_query = ""
    web_validation_confidence = ""
    web_results = []
    final_response = ""
    final_status = ""

    # --------------------------------------------------------
    # NON-HOSPITAL
    # --------------------------------------------------------

    if validation_result["decision"] == "IGNORE_NON_HOSPITAL":

        print("\n🚫 NON-HOSPITAL EMAIL")
        print(
            "➡️ No SerpAPI search required."
        )
        print(
            "➡️ No response email will be sent."
        )

        mark_as_read(
            gmail,
            email["id"]
        )

        final_status = "NON_HOSPITAL_IGNORED"

        save_to_sheet(
            worksheet,
            email,
            rag_result,
            validation_result,
            False,
            "",
            "",
            "",
            final_status
        )

        print(
            "✅ Original email marked as read"
        )
        print(
            "✅ Memory + Audit Log updated"
        )
        print(
            "\n✅ NON-HOSPITAL EMAIL LOGGED"
        )

        return

    # --------------------------------------------------------
    # DIRECT RAG PATH
    # --------------------------------------------------------

    if validation_result["decision"] == "SEND_TO_AGENT_3":

        print(
            "\n✅ Confidence >= 70%"
        )
        print(
            "➡️ Sending to Agent 3"
        )

        final_response = email_response_agent(
            email,
            rag_result
        )

        send_email(
            gmail,
            email["from"],
            "Re: " + email["subject"],
            final_response,
            email["id"]
        )

        mark_as_read(
            gmail,
            email["id"]
        )

        final_status = "RAG_RESPONSE_SENT"

        save_to_sheet(
            worksheet,
            email,
            rag_result,
            validation_result,
            False,
            "",
            "",
            final_response,
            final_status
        )

        print(
            "\n✅ Personalized email sent successfully"
        )
        print(
            "✅ Original email marked as read"
        )
        print(
            "✅ Memory + Audit Log updated"
        )
        print(
            "\n🎉 FLOW COMPLETED"
        )

        return

    # --------------------------------------------------------
    # WEB SEARCH PATH
    # --------------------------------------------------------

    print(
        "\n⚠️ Confidence < 70%"
    )
    print(
        "➡️ Starting SerpAPI Web Search"
    )

    web_query = (
        f"hospital patient support "
        f"{email['subject']} "
        f"{email['body']}"
    )

    web_used = True

    web_results = web_search(
        web_query
    )

    web_validation = validate_web_results(
        email,
        web_results
    )

    web_validation_confidence = web_validation.get(
        "confidence",
        0
    )

    # --------------------------------------------------------
    # WEB SEARCH PASSED
    # --------------------------------------------------------

    if (
        web_validation.get("decision")
        == "USE_WEB_RESULTS"
        and web_validation_confidence >= CONFIDENCE_THRESHOLD
    ):

        print(
            "\n✅ Web validation >= 70%"
        )
        print(
            "➡️ Sending to Agent 3"
        )

        final_response = email_response_agent(
            email,
            rag_result,
            web_results
        )

        send_email(
            gmail,
            email["from"],
            "Re: " + email["subject"],
            final_response,
            email["id"]
        )

        mark_as_read(
            gmail,
            email["id"]
        )

        final_status = "WEB_VALIDATED_RESPONSE_SENT"

        save_to_sheet(
            worksheet,
            email,
            rag_result,
            validation_result,
            True,
            web_query,
            web_validation_confidence,
            final_response,
            final_status
        )

        print(
            "\n✅ Personalized email sent successfully"
        )
        print(
            "✅ Original email marked as read"
        )
        print(
            "✅ Memory + Audit Log updated"
        )
        print(
            "\n🎉 FLOW COMPLETED"
        )

        return

    # --------------------------------------------------------
    # REFINED WEB SEARCH
    # --------------------------------------------------------

    print(
        "\n⚠️ Web validation < 70%"
    )
    print(
        "➡️ Refining Web Search Query"
    )

    refined_query = (
        f'"{email["subject"]}" '
        f'hospital patient policy '
        f'{rag_result.get("category", "")}'
    )

    web_query = refined_query

    refined_results = web_search(
        refined_query
    )

    refined_validation = validate_web_results(
        email,
        refined_results
    )

    refined_confidence = refined_validation.get(
        "confidence",
        0
    )

    print(
        "\n🔄 REFINED WEB VALIDATION"
    )
    print(
        f"Confidence: "
        f"{refined_confidence}%"
    )
    print(
        f"Decision: "
        f"{refined_validation.get('decision')}"
    )
    print(
        f"Reason: "
        f"{refined_validation.get('reason')}"
    )

    if (
        refined_validation.get("decision")
        == "USE_WEB_RESULTS"
        and refined_confidence >= CONFIDENCE_THRESHOLD
    ):

        print(
            "\n✅ Refined web validation >= 70%"
        )
        print(
            "➡️ Sending to Agent 3"
        )

        final_response = email_response_agent(
            email,
            rag_result,
            refined_results
        )

        send_email(
            gmail,
            email["from"],
            "Re: " + email["subject"],
            final_response,
            email["id"]
        )

        mark_as_read(
            gmail,
            email["id"]
        )

        final_status = "REFINED_WEB_RESPONSE_SENT"

        save_to_sheet(
            worksheet,
            email,
            rag_result,
            validation_result,
            True,
            refined_query,
            refined_confidence,
            final_response,
            final_status
        )

        print(
            "\n✅ Personalized email sent successfully"
        )
        print(
            "✅ Original email marked as read"
        )
        print(
            "✅ Memory + Audit Log updated"
        )
        print(
            "\n🎉 FLOW COMPLETED"
        )

        return

    # --------------------------------------------------------
    # WEB SEARCH FAILED
    # --------------------------------------------------------

    print(
        "\n❌ Unable to achieve 70% confidence."
    )
    print(
        "⚠️ Email will NOT be sent automatically."
    )

    mark_as_read(
        gmail,
        email["id"]
    )

    final_status = "WEB_VALIDATION_FAILED"

    save_to_sheet(
        worksheet,
        email,
        rag_result,
        validation_result,
        True,
        refined_query,
        refined_confidence,
        "",
        final_status
    )

    print(
        "✅ Memory + Audit Log updated"
    )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    main()