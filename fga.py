"""Auth0 Fine-Grained Authorization (FGA) client and Privacy-Aware RAG implementation."""

import os
import re
from typing import Any, Optional
from dotenv import load_dotenv
from openfga_sdk.client import ClientConfiguration, OpenFgaClient
from openfga_sdk.client.models import ClientCheckRequest
from openfga_sdk.credentials import CredentialConfiguration, Credentials

# Load environment variables
load_dotenv()

FGA_API_URL = os.getenv("FGA_API_URL")
FGA_STORE_ID = os.getenv("FGA_STORE_ID")
FGA_CLIENT_ID = os.getenv("FGA_CLIENT_ID")
FGA_CLIENT_SECRET = os.getenv("FGA_CLIENT_SECRET")
FGA_API_TOKEN_ISSUER = os.getenv("FGA_API_TOKEN_ISSUER")
FGA_API_AUDIENCE = os.getenv("FGA_API_AUDIENCE")

# In-memory document dataset for RAG demo
DOCUMENTS = [
    {
        "id": "salary_report",
        "title": "Executive Salary and Compensation Report 2026",
        "content": (
            "Confidential executive compensation overview: Base executive pay starts at $220,000 "
            "with a 30% performance bonus target. Engineering leadership compensation ranges from "
            "$180,000 to $250,000. All executive compensation reviews occur annually in December."
        ),
        "keywords": [
            "salary", "compensation", "pay", "bonus", "executive", "payroll", "earnings", "money"
        ],
    },
    {
        "id": "holiday_policy",
        "title": "Company Holiday and Leave Policy",
        "content": (
            "Employees receive 20 days of paid annual leave plus 10 public company holidays. "
            "Additional floating personal days are granted each quarter. Unused vacation days "
            "(up to 5 days) may roll over into the next calendar year."
        ),
        "keywords": [
            "holiday", "vacation", "leave", "time off", "policy", "days", "pto", "annual"
        ],
    },
    {
        "id": "legal_memo",
        "title": "Privileged Legal Memo: Merger and Acquisition Guidelines",
        "content": (
            "Strictly privileged attorney-client communication: All discussions regarding potential vendor "
            "acquisitions and mergers are governed by NDA-741. Disclosing target valuations, pending term sheets, "
            "or due diligence findings is strictly prohibited without General Counsel approval."
        ),
        "keywords": [
            "legal", "merger", "acquisition", "nda", "memo", "attorney", "agreement", "compliance", "lawyer"
        ],
    },
    {
        "id": "remote_work_guide",
        "title": "Remote Work and Home Office Guidelines",
        "content": (
            "Team members are eligible for hybrid or full-time remote work upon manager approval. "
            "The company provides a $500 home office equipment stipend and monthly reimbursement "
            "for high-speed home internet up to $75."
        ),
        "keywords": [
            "remote", "work", "home", "office", "equipment", "stipend", "internet", "hybrid", "wfh"
        ],
    },
    {
        "id": "security_protocol",
        "title": "Internal Security & Access Control Protocols",
        "content": (
            "Mandatory security procedures: Multi-Factor Authentication (MFA) is strictly enforced across "
            "all company accounts and SSO logins. Production database access requires approval via JIT "
            "access requests and automatically expires after 4 hours."
        ),
        "keywords": [
            "security", "mfa", "access", "protocol", "credentials", "password", "database", "control"
        ],
    },
    {
        "id": "financial_audit",
        "title": "Quarterly Financial Audit and Revenue Summary",
        "content": (
            "Confidential Q3 Financial Summary: Net quarterly revenue reached $4.2M representing a 14% "
            "year-over-year increase. Operating margin was 22%. Cash reserves stand at $12.5M. Detailed "
            "audit reports are restricted to Finance and Board members."
        ),
        "keywords": [
            "financial", "audit", "revenue", "finance", "budget", "profit", "quarterly", "margin"
        ],
    },
]


def get_fga_client() -> Optional[OpenFgaClient]:
    """Initialize OpenFGA client with client credentials from .env."""
    if not all([FGA_API_URL, FGA_STORE_ID, FGA_CLIENT_ID, FGA_CLIENT_SECRET]):
        return None

    credentials = Credentials(
        method="client_credentials",
        configuration=CredentialConfiguration(
            client_id=FGA_CLIENT_ID,
            client_secret=FGA_CLIENT_SECRET,
            api_issuer=FGA_API_TOKEN_ISSUER,
            api_audience=FGA_API_AUDIENCE,
        ),
    )

    configuration = ClientConfiguration(
        api_url=FGA_API_URL,
        store_id=FGA_STORE_ID,
        credentials=credentials,
    )

    return OpenFgaClient(configuration)


def search_documents(query: str) -> list[dict[str, Any]]:
    """
    Find matching documents from the dataset via keyword matching.
    Returns ranked list of documents matching the query.
    """
    if not query:
        return []

    query_lower = query.lower()
    # Extract alphanumeric words longer than 2 characters
    words = [w for w in re.findall(r"\w+", query_lower) if len(w) > 2]
    # Common stop words to exclude
    stop_words = {
        "what", "is", "the", "about", "for", "in", "a", "of", "to", "show", "me",
        "tell", "can", "you", "our", "are", "and", "how", "give", "please", "with"
    }
    filtered_words = [w for w in words if w not in stop_words]
    match_words = filtered_words if filtered_words else words

    scored: list[tuple[int, dict[str, Any]]] = []

    for doc in DOCUMENTS:
        score = 0
        doc_id = doc["id"].lower()
        title = doc["title"].lower()
        content = doc["content"].lower()

        # Direct document ID match
        if doc_id in query_lower or any(part in query_lower for part in doc_id.split("_")):
            score += 15

        # Title word matches
        for w in match_words:
            if w in title:
                score += 8

        # Keyword matches
        for kw in doc.get("keywords", []):
            if kw in query_lower or any(kw in w or w in kw for w in match_words):
                score += 6

        # Content word matches
        for w in match_words:
            if w in content:
                score += 2

        if score > 0:
            scored.append((score, doc))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [doc for _, doc in scored]


async def check_fga_access(fga_client: OpenFgaClient, email: str, doc_id: str) -> bool:
    """
    Execute FGA check (user:<email>, viewer, document:<doc_id>) using openfga-sdk.
    """
    clean_email = email.strip().lower()
    fga_user = f"user:{clean_email}"
    fga_object = f"document:{doc_id}"

    check_req = ClientCheckRequest(
        user=fga_user,
        relation="viewer",
        object=fga_object,
    )

    try:
        response = await fga_client.check(check_req)
        return bool(response.allowed)
    except Exception as e:
        # Fail closed on authorization errors
        print(f"FGA Check error for {fga_user} on {fga_object}: {e}")
        return False


async def query_rag_pipeline(email: str, question: str) -> dict[str, Any]:
    """
    Execute the Privacy-Aware RAG pipeline:
    1. Search for candidate documents via keyword search.
    2. Check access permissions via Auth0 FGA before returning any document.
    3. Drop denied documents.
    4. Generate response and return transparent decision audit.
    """
    clean_email = (email or "anonymous").strip().lower()
    fga_user = f"user:{clean_email}"

    matched_docs = search_documents(question)

    if not matched_docs:
        return {
            "user_email": clean_email,
            "fga_user": fga_user,
            "question": question,
            "reply": (
                "No relevant internal documents matched your question. "
                "Try asking about: holiday policy, salary report, legal memo, "
                "remote work, security protocols, or financial audit."
            ),
            "status": "not_found",
            "allowed_docs": [],
            "denied_docs": [],
            "inspections": [],
        }

    fga_client = get_fga_client()
    inspections = []
    allowed_docs = []
    denied_docs = []

    try:
        for doc in matched_docs:
            if fga_client:
                is_allowed = await check_fga_access(fga_client, clean_email, doc["id"])
            else:
                # If FGA is not configured, default deny
                is_allowed = False

            inspection = {
                "doc_id": doc["id"],
                "doc_title": doc["title"],
                "fga_object": f"document:{doc['id']}",
                "relation": "viewer",
                "allowed": is_allowed,
            }
            inspections.append(inspection)

            if is_allowed:
                allowed_docs.append(doc)
            else:
                denied_docs.append(doc)
    finally:
        if fga_client:
            await fga_client.close()

    # Determine final response
    if allowed_docs:
        # Answer from allowed documents
        answers = []
        for d in allowed_docs:
            answers.append(f"**{d['title']}**\n{d['content']}")

        reply_body = "\n\n".join(answers)
        sources_list = [d["title"] for d in allowed_docs]

        reply = f"{reply_body}\n\n*Sources used: {', '.join(sources_list)}*"
        if denied_docs:
            reply += "\n*(Note: Additional matching documents were restricted by FGA policy)*"

        return {
            "user_email": clean_email,
            "fga_user": fga_user,
            "question": question,
            "reply": reply,
            "status": "allowed",
            "sources": sources_list,
            "allowed_docs": [d["id"] for d in allowed_docs],
            "denied_docs": [d["id"] for d in denied_docs],
            "inspections": inspections,
        }

    else:
        # Matching doc(s) were found, but ALL were denied by FGA
        return {
            "user_email": clean_email,
            "fga_user": fga_user,
            "question": question,
            "reply": "You don't have access to that document.",
            "access_denied_note": "Access denied by FGA",
            "status": "denied",
            "sources": [],
            "allowed_docs": [],
            "denied_docs": [d["id"] for d in denied_docs],
            "inspections": inspections,
        }

