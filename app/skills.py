from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from typing import Any

from app.models import JsonDict

SkillHandler = Callable[[JsonDict], Awaitable[JsonDict]]


def word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


async def summarize_document(payload: JsonDict) -> JsonDict:
    text = payload.get("text") or f"Resource content from {payload.get('resource_uri', 'unknown')}"
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    key_points = [sentence.strip() for sentence in sentences if sentence.strip()][:3]
    summary = " ".join(key_points)[:280] or "No summary available."
    return {
        "summary": summary,
        "key_points": key_points or [summary],
        "word_count": word_count(text),
        "mode": "mock",
    }


async def extract_entities(payload: JsonDict) -> JsonDict:
    text = payload["text"]
    people = sorted(set(re.findall(r"\b[A-Z][a-z]+ [A-Z][a-z]+\b", text)))
    organizations = sorted(set(re.findall(r"\b[A-Z][A-Za-z]+(?: Inc| LLC| Corp| Labs| Bank)\b", text)))
    products = sorted(set(re.findall(r"\b(?:Skill Hub|MCP|Atlas|Nova|Helix)\b", text)))
    dates = sorted(set(re.findall(r"\b(?:Q[1-4]\s+\d{4}|\d{4}-\d{2}-\d{2}|Monday|Tuesday|Friday)\b", text)))
    risks = [line.strip() for line in text.splitlines() if "risk" in line.lower()][:5]
    action_items = [line.strip("- ") for line in text.splitlines() if re.search("action|follow", line, re.I)]
    return {
        "people": people,
        "organizations": organizations,
        "products": products,
        "dates": dates,
        "risks": risks,
        "action_items": action_items,
    }


async def translate_text(payload: JsonDict) -> JsonDict:
    text = payload["text"]
    target_language = payload["target_language"]
    return {
        "translated_text": f"[mock translation to {target_language}] {text}",
        "source_language": payload.get("source_language", "auto"),
        "target_language": target_language,
        "quality": "deterministic-placeholder",
    }


async def classify_request(payload: JsonDict) -> JsonDict:
    request = payload["request"].lower()
    if any(term in request for term in ["outage", "down", "blocked", "security"]):
        category, priority, confidence = "incident", "high", 0.91
    elif any(term in request for term in ["rfp", "proposal", "procurement"]):
        category, priority, confidence = "sales", "medium", 0.86
    elif any(term in request for term in ["refund", "support", "ticket"]):
        category, priority, confidence = "support", "medium", 0.82
    else:
        category, priority, confidence = "general", "low", 0.7
    return {
        "category": category,
        "priority": priority,
        "confidence": confidence,
        "rationale": f"Matched deterministic mock routing signals for {category}.",
    }


async def generate_action_items(payload: JsonDict) -> JsonDict:
    text = payload["text"]
    lines = [line.strip("- ").strip() for line in text.splitlines() if line.strip()]
    tasks = []
    for index, line in enumerate(lines[:8], start=1):
        if re.search("follow|owner|todo|action|next|by ", line, re.I):
            owner_match = re.search(r"\b([A-Z][a-z]+)\b", line)
            due_match = re.search(r"\b(?:by|due)\s+([A-Za-z]+\s+\d{1,2}|\d{4}-\d{2}-\d{2})", line, re.I)
            tasks.append(
                {
                    "owner": owner_match.group(1) if owner_match else "Unassigned",
                    "task": line,
                    "due_date": due_match.group(1) if due_match else None,
                    "priority": "high" if "urgent" in line.lower() else "medium",
                }
            )
    if not tasks:
        tasks.append(
            {
                "owner": "Unassigned",
                "task": "Review notes and confirm next step.",
                "due_date": None,
                "priority": "low",
            }
        )
    return {"action_items": tasks, "count": len(tasks)}


async def search_knowledge_base(payload: JsonDict) -> JsonDict:
    query = payload["query"]
    corpus = [
        ("resource://policy/ai-governance", "AI Governance Policy", "Approved use, audit, privacy, and review controls."),
        ("resource://product/skill-hub", "Skill Hub Product Brief", "Reusable MCP skills for enterprise agents."),
        ("resource://policy/vendor-risk", "Vendor Risk Policy", "Security reviews for third-party providers."),
    ]
    terms = set(re.findall(r"\w+", query.lower()))
    results = []
    for uri, title, snippet in corpus:
        score = sum(1 for term in terms if term in f"{title} {snippet}".lower())
        results.append({"uri": uri, "title": title, "snippet": snippet, "score": score or 1})
    results.sort(key=lambda item: item["score"], reverse=True)
    return {"query": query, "results": results[: payload.get("limit", 3)]}


BUILTIN_HANDLERS: dict[str, SkillHandler] = {
    "summarize_document": summarize_document,
    "extract_entities": extract_entities,
    "translate_text": translate_text,
    "classify_request": classify_request,
    "generate_action_items": generate_action_items,
    "search_knowledge_base": search_knowledge_base,
}
