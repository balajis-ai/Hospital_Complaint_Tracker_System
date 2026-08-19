

# 🏥 Hospital Support & Patient Experience AI enabled System

## Buildathon Project — Multi-Agent Hospital Email Support Automation

A multi-agent AI system that automatically reads incoming hospital-support emails from Gmail, understands the patient's concern using a hospital-specific RAG knowledge base, validates the response, performs web research when the knowledge base is insufficient, generates a professional patient-facing email, sends the response, and records the complete interaction in Google Sheets for memory and audit purposes.

---

## 📌 Project Overview

This project is designed as an AI-powered hospital customer-support assistant.

The system continuously checks an authenticated Gmail inbox for unread emails.

For every new email, it performs the following workflow:

```
                    ┌──────────────────────┐
                    │     Gmail Inbox      │
                    │  Unread Patient Mail │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │      Agent 1         │
                    │     RAG Agent        │
                    │                      │
                    │ • Understand email  │
                    │ • Classify complaint │
                    │ • Search KB         │
                    │ • Score confidence  │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │      Agent 2         │
                    │ Validation Agent     │
                    └──────────┬───────────┘
                               │
                ┌──────────────┴──────────────┐
                │                             │
        Confidence ≥ 70%              Confidence < 70%
                │                             │
                ▼                             ▼
        ┌───────────────┐             ┌────────────────┐
        │    Agent 3    │             │    SerpAPI     │
        │ Email Response│             │  Web Search    │
        └───────┬───────┘             └───────┬────────┘
                │                             │
                │                             ▼
                │                     ┌────────────────┐
                │                     │ Web Validation │
                │                     └───────┬────────┘
                │                             │
                │                  ┌──────────┴──────────┐
                │                  │                     │
                │               ≥ 70%                  < 70%
                │                  │                     │
                │                  ▼                     ▼
                │             Agent 3              Refined Search
                │                                        │
                │                                        ▼
                │                                   Web Validation
                │                                        │
                └────────────────────────────────────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │    Gmail Response    │
                    │ Patient-facing Email │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │    Google Sheets     │
                    │ Memory + Audit Log   │
                    └──────────────────────┘
```


# 🌐 SerpAPI Web Research

Web search is used only when the hospital knowledge base is insufficient.

The initial query is constructed from:

* Hospital patient support
* Email subject
* Email body

Example:

```
hospital patient support
International patient insurance policy question
[patient email content]
```

The system retrieves up to 5 Google results.

Each result contains:

```
Title
Snippet
URL
```



# 📚 Knowledge Base

The primary knowledge source is:

```
knowledge_base.txt
```

The provided knowledge base is:

**HOSPITAL OPERATIONS & PATIENT EXPERIENCE — RAG KNOWLEDGE BASE — Version 1.0**

It covers hospital operational and patient-experience complaints including:

1. Canteen Food Complaints
2. Dietitian Complaints
3. Referral / Specialist Consultation Complaints
4. Facility Complaints
5. Staff Behavior Complaints
6. Treatment / Service Delay Complaints
7. Food Delivery Delay
8. Customer Support / Communication Delay
9. Patient Transportation Delay
10. Housekeeping / Cleaning Complaints
11. Medical Counseling Delay
12. Payment / Financial Counseling
13. Increase in Bill / Amount
14. Admission Kit Complaint
15. Room Amenity Complaints
16. Delay in Communication
17. General Patient Complaint Handling
18. AI Response Rules
19. Confidence Scoring
20. Example Complaints

🏥 Operational Safety

The system should not promise:

"Your issue will be resolved in 10 minutes."

unless the hospital team has confirmed that time.

Instead:

"We will coordinate with the concerned team
and provide an update."

🔄 Complete Processing Logic

The main processing flow is:

1. Connect to Google
   ↓
2. Open Google Sheet
   ↓
3. Search for unread Gmail
   ↓
4. Extract email
   ↓
5. Load knowledge base
   ↓
6. Load memory
   ↓
7. Agent 1 — RAG
   ↓
8. Agent 2 — Validation
   ↓
   ┌────┴─────┐
   │          │
   Non-hospital  Hospital
   │          │
   Ignore       Continue
   ↓
   Confidence Check
   ↓
   ┌──────┴──────┐
   │             │
   > =70           <70
   > │             │
   > ▼             ▼
   > Agent 3       SerpAPI
   > ↓
   > Web Validation
   > ↓
   > ┌──────┴──────┐
   > │             │
   >>=70           <70
   > │             │
   > ▼             ▼
   > Agent 3     Refined Search
   > ↓
   > Validation
   > ↓
   >>=70 / <70
   > │
   > ▼
   > Agent 3 or Fail
   > ↓
   > Send Email if valid
   > ↓
   > Mark Email Read
   > ↓
   > Save Audit Log
   >

📈 Why This Is a Multi-Agent System

The system separates responsibilities across multiple AI decision stages.

### Agent 1

```
UNDERSTAND + RETRIEVE + CLASSIFY
```

### Agent 2

```
VALIDATE + DECIDE
```

### Web Validation

```
VERIFY EXTERNAL INFORMATION
```

### Agent 3

```
GENERATE PATIENT RESPONSE
```

This separation reduces the chance that one model call will independently:

* Misclassify an email.
* Hallucinate an answer.
* Trust irrelevant web information.
* Send an unsupported response.

🏆 Buildathon Value Proposition

This project demonstrates:

1. RAG

Hospital-specific knowledge is used before external search.

2. Multi-Agent AI

Different agents have different responsibilities.

3. Confidence-Based Routing

The system changes its behavior based on confidence.

4. External Validation

SerpAPI provides an additional research layer when required.

5. Memory

Google Sheets stores previous interactions.

6. Automation

The system reads, processes, responds and logs emails automatically.

7. Human-Safe Design

Clinical, financial and policy hallucinations are intentionally restricted.

8. Auditability

Every processed email can be tracked through Google Sheets.

```text
# Hospital AI Support Crew
```



# 🔒 Security Recommendations

Before production deployment:

* Store API keys in secure secrets management.
* Never commit `<span>.env</span>`.
* Never commit `<span>credentials.json</span>`.
* Never commit `<span>token.json</span>`.
* Use minimum required Google OAuth scopes.
* Encrypt patient information where required.
* Implement role-based access.
* Add audit controls.
* Follow applicable healthcare privacy requirements.
* Restrict access to patient information.
* Add human approval for high-risk responses.

# 📌 Example Successful Execution

# 📈 Why This Is a Multi-Agent System

The system separates responsibilities across multiple AI decision stages.

### Agent 1

```
UNDERSTAND + RETRIEVE + CLASSIFY
```

### Agent 2

```
VALIDATE + DECIDE
```

### Web Validation

```
VERIFY EXTERNAL INFORMATION
```

### Agent 3

```
GENERATE PATIENT RESPONSE
```

This separation reduces the chance that one model call will independently:

* Misclassify an email.
* Hallucinate an answer.
* Trust irrelevant web information.
* Send an unsupported response.

A successful execution looks like:

```
🔄 Connecting to Google...
📧 Connected Gmail: balajisridharan.mca@gmail.com
✅ Gmail connected
✅ Google Sheets connected

📧 New email found

🤖 Agent 1 - RAG Agent

Hospital Related: True
Category: PATIENT TRANSPORT / INTERNAL MOVEMENT
Supported by KB: True
Confidence: 95%

🔍 Agent 2 - Validation Agent

Validation Confidence: 95%
Decision: SEND_TO_AGENT_3

📨 Agent 3 - Email Response Agent

✅ Personalized email sent successfully
✅ Original email marked as read
✅ Memory + Audit Log updated

🎉 FLOW COMPLETED
```


🏆 Project Summary

Hospital Operations & Patient Experience AI Support System

A practical multi-agent AI automation that combines:

RAG
+
LLM Reasoning
+
Validation
+
Web Research
+
Email Automation
+
Memory
+
Audit Logging
+
Safety Controls

The result is an automated hospital-support workflow designed to provide faster, more consistent and safer responses while keeping unsupported information away from patients.

# 🎤 Buildathon Highlight

> "This is a multi-agent AI powered hospital support system that automatically handles patient emails. Agent 1 uses a hospital-specific RAG knowledge base to understand and classify the complaint and generates a confidence score. Agent 2 validates whether the response is sufficiently supported. If confidence is low, the system uses SerpAPI for external research and validates those results before continuing. Agent 3 generates a professional patient-facing email. The response is automatically sent through Gmail, the original email is marked as read, and the entire interaction is stored in Google Sheets as memory and an audit log. The system also includes safeguards to prevent unsupported hospital policies, billing information, clinical advice and unconfirmed commitments."
>
