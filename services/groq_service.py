"""LLM calls — Hugging Face (primary), Groq (fallback)."""
import base64
import json
from config import (
    HF_TOKEN, HF_TEXT_MODEL, HF_VISION_MODEL,
    GROQ_API_KEY, GROQ_TEXT_MODEL, GROQ_VISION_MODEL,
)

_hf_client = None
_groq_client = None


def _get_hf():
    global _hf_client
    if _hf_client is None and HF_TOKEN:
        from openai import OpenAI
        _hf_client = OpenAI(
            base_url="https://router.huggingface.co/v1",
            api_key=HF_TOKEN,
        )
    return _hf_client


def _get_groq():
    global _groq_client
    if _groq_client is None and GROQ_API_KEY:
        from groq import Groq
        _groq_client = Groq(api_key=GROQ_API_KEY)
    return _groq_client


def _chat(messages, model_hf, model_groq, temperature=0.3, max_tokens=1000, image_data=None):
    if image_data:
        content = [
            {"type": "image_url", "image_url": {"url": f"data:{image_data['media_type']};base64,{image_data['data']}"}},
            {"type": "text", "text": messages[0]["content"]},
        ]
        messages = [{"role": "user", "content": content}]

    hf = _get_hf()
    if hf:
        try:
            return hf.chat.completions.create(model=model_hf, messages=messages, temperature=temperature, max_tokens=max_tokens).choices[0].message.content
        except Exception as e:
            print(f"HF failed, fallback to Groq: {e}")

    groq = _get_groq()
    if groq:
        return groq.chat.completions.create(model=model_groq, messages=messages, temperature=temperature, max_tokens=max_tokens).choices[0].message.content

    raise RuntimeError("No LLM available — set HF_TOKEN or GROQ_API_KEY")


# ── Summary ───────────────────────────────────────────────────────────────────

def generate_summary(text: str) -> str:
    prompt = f"""Analyze the following text and provide a concise, plain-text summary (max 400 words).

Do NOT use markdown formatting (no **, #, or dashes).

Include:
1. Main Topic — what this document is about (1-2 sentences)
2. Key Points — 3-5 essential points, each 1 sentence
3. Conclusion — main takeaway (1 sentence)

TEXT:
{text[:10000]}"""

    return _chat(
        messages=[{"role": "user", "content": prompt}],
        model_hf=HF_TEXT_MODEL,
        model_groq=GROQ_TEXT_MODEL,
        temperature=0.3,
        max_tokens=700,
    )


# ── MCQs ──────────────────────────────────────────────────────────────────────

def generate_mcqs(text: str, num_questions: int = 5) -> list[dict]:
    prompt = f"""You are an expert question writer who adapts to any document type.

First, analyze the document below and determine its primary content type: educational, technical, business, creative/literary, news, or general.

Then generate up to {num_questions} well-crafted multiple choice questions that are appropriate for that content type. Choose a number proportional to the content — fewer for short documents, more for detailed ones.

TAILOR QUESTIONS TO THE CONTENT TYPE:
- **Educational** → comprehension, concept recall, application, and understanding
- **Technical** → procedures, specifications, configurations, and factual details
- **Business** → strategies, data interpretation, market analysis, and decision points
- **Creative/Literary** → themes, characters, plot, narrative techniques, and symbolism
- **News** → key facts, chronology, implications, stakeholders, and context
- **General** → main ideas, important details, and key takeaways

RULES for ALL types:
- Questions must be based ONLY on the provided text
- Each question must have exactly 4 options (A, B, C, D)
- Only one correct answer per question
- Include a brief explanation for the correct answer

IMPORTANT: For each question, include the exact source reference:
- "source": A short verbatim excerpt from the text that supports this question
- "page": The page number where the source appears (from [Page N, Line M] markers)
- "line": The line number where the source appears (from [Page N, Line M] markers)

INCLUDE A "topic" FIELD FOR EACH QUESTION that describes which section or concept this question tests (e.g., "Architectural Concepts", "Data Synchronization", "Microservice Patterns", etc.).

RESPONSE FORMAT (strict JSON array):
[
  {{
    "question": "Question text here?",
    "options": {{
      "A": "Option A",
      "B": "Option B",
      "C": "Option C",
      "D": "Option D"
    }},
    "answer": "A",
    "explanation": "Brief explanation why A is correct",
    "topic": "Topic name here",
    "source": "Verbatim excerpt supporting this question",
    "page": 3,
    "line": 12
  }}
]

TEXT:
{text[:10000]}

Return ONLY the JSON array, no extra text."""

    raw = _chat(
        messages=[{"role": "user", "content": prompt}],
        model_hf=HF_TEXT_MODEL,
        model_groq=GROQ_TEXT_MODEL,
        temperature=0.4,
        max_tokens=2000,
    ).strip()

    start = raw.find("[")
    end = raw.rfind("]") + 1
    if start != -1 and end > start:
        raw = raw[start:end]

    return json.loads(raw)


# ── Q&A Pairs ──────────────────────────────────────────────────────────────────

def generate_qa_pairs(text: str, num_pairs: int = 5) -> list[dict]:
    prompt = f"""You are an expert question writer who adapts to any document type.

First, analyze the document below and determine its primary content type: educational, technical, business, creative/literary, news, or general.

Then generate up to {num_pairs} question-answer pairs that are appropriate for that content type. Choose a number proportional to the content — fewer for short documents, more for detailed ones.

TAILOR Q&A TO THE CONTENT TYPE:
- **Educational** → concept comprehension, definitions, explanations, "why/how" questions
- **Technical** → procedures, specifications, troubleshooting, factual recall
- **Business** → strategy rationale, data insights, decision analysis
- **Creative/Literary** → theme analysis, character motivation, plot significance
- **News** → key facts, implications, stakeholder impact
- **General** → main ideas and important takeaways

RULES:
- Questions and answers must be based ONLY on the provided text
- Answers should be concise but complete (2-4 sentences)
- Each question must be answerable from the text

IMPORTANT: For each pair, include the exact source reference:
- "source": A short verbatim excerpt from the text that supports this Q&A
- "page": The page number where the source appears (from [Page N, Line M] markers)
- "line": The line number where the source appears (from [Page N, Line M] markers)

RESPONSE FORMAT (strict JSON array):
[
  {{
    "question": "Question text here?",
    "answer": "Concise but complete answer based on the text.",
    "source": "Verbatim excerpt supporting this Q&A",
    "page": 3,
    "line": 12
  }}
]

TEXT:
{text[:10000]}

Return ONLY the JSON array, no extra text."""

    raw = _chat(
        messages=[{"role": "user", "content": prompt}],
        model_hf=HF_TEXT_MODEL,
        model_groq=GROQ_TEXT_MODEL,
        temperature=0.4,
        max_tokens=3000,
    ).strip()

    start = raw.find("[")
    end = raw.rfind("]") + 1
    if start != -1 and end > start:
        raw = raw[start:end]

    return json.loads(raw)


# ── Q&A (Chat) ────────────────────────────────────────────────────────────────

def answer_question(question: str, context_chunks: list[str]) -> str:
    context = "\n\n---\n\n".join(context_chunks)

    prompt = f"""You are a helpful assistant answering questions about a document.

Based on the context below, identify the document type (educational, technical, business, creative/literary, news, or general) and tailor your answer accordingly:

- **Educational** → explain concepts clearly with examples, focus on understanding
- **Technical** → be precise, reference specific procedures, specifications, or configurations
- **Business** → focus on strategy, data, market implications, and decision points
- **Creative/Literary** → discuss themes, characters, plot, and narrative techniques
- **News** → provide context, chronology, key facts, and stakeholder implications
- **General** → clear, direct answers focused on the main information

IMPORTANT: The context contains [Page N, Line M] markers. When you use information from the context, cite the source by including the page and line reference in your answer like this: [Page 3, Line 12]. Always attach a citation to each piece of information you use.

Use ONLY the provided context to answer. If the answer is not in the context, say:
"I couldn't find this information in the document."

CONTEXT:
{context}

QUESTION: {question}

Provide a clear, accurate answer based on the context above, with citations."""

    return _chat(
        messages=[{"role": "user", "content": prompt}],
        model_hf=HF_TEXT_MODEL,
        model_groq=GROQ_TEXT_MODEL,
        temperature=0.2,
        max_tokens=1000,
    )


# ── Takeaways ─────────────────────────────────────────────────

def generate_takeaways(text: str) -> list[dict]:
    prompt = f"""You are an expert document analyst extracting key insights.

Analyze the following text and extract the 4-5 most important takeaways (insights, conclusions, or critical facts). Each takeaway should be a concise, standalone statement that captures a significant point.

RESPONSE FORMAT (strict JSON array):
[
  {{
    "text": "A concise takeaway statement based on the document.",
    "icon": "bi-bullseye"
  }}
]

Choose the icon for each takeaway from: bi-bullseye, bi-lightning-charge-fill, bi-plug-fill, bi-bar-chart-fill, bi-stars, bi-graph-up-arrow, bi-gear-fill, bi-rocket-takeoff-fill

TEXT:
{text[:10000]}

Return ONLY the JSON array, no extra text."""

    raw = _chat(
        messages=[{"role": "user", "content": prompt}],
        model_hf=HF_TEXT_MODEL,
        model_groq=GROQ_TEXT_MODEL,
        temperature=0.3,
        max_tokens=1500,
    ).strip()

    start = raw.find("[")
    end = raw.rfind("]") + 1
    if start != -1 and end > start:
        raw = raw[start:end]

    return json.loads(raw)


# ── Terminology ─────────────────────────────────────────
def generate_terminology(text: str) -> list[dict]:
    prompt = f"""Extract 5-10 key technical terms, jargon, or specialized vocabulary from the document.

For each term, provide a clear definition in the context of how it is used in this document.
These should be DIFFERENT from general takeaways — they are definitions of specific terminology, not insights or conclusions.

RESPONSE FORMAT (strict JSON array):
[
  {{
    "term": "The word or phrase",
    "definition": "Clear definition in context of the document."
  }}
]

TEXT:
{text[:10000]}

Return ONLY the JSON array, no extra text."""

    raw = _chat(
        messages=[{"role": "user", "content": prompt}],
        model_hf=HF_TEXT_MODEL,
        model_groq=GROQ_TEXT_MODEL,
        temperature=0.3,
        max_tokens=1000,
    ).strip()

    start = raw.find("[")
    end = raw.rfind("]") + 1
    if start != -1 and end > start:
        raw = raw[start:end]

    return json.loads(raw)


# ── Document Classification ──────────────────────────────

def classify_document(text: str) -> str:
    prompt = f"""Classify this document into exactly one word: educational, transactional, legal, technical, creative, or other.

Return ONLY the word, nothing else.

TEXT:
{text[:2000]}"""

    raw = _chat(
        messages=[{"role": "user", "content": prompt}],
        model_hf=HF_TEXT_MODEL,
        model_groq=GROQ_TEXT_MODEL,
        temperature=0,
        max_tokens=10,
    ).strip().lower()

    valid = {"educational", "transactional", "legal", "technical", "creative"}
    return raw if raw in valid else "other"


# ── Image Understanding ───────────────────────────────────────────────────────

def understand_image(image_path: str, context: str = "") -> str:
    with open(image_path, "rb") as f:
        img_data = base64.b64encode(f.read()).decode("utf-8")

    ext = image_path.split(".")[-1].lower()
    media_map = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "gif": "gif", "webp": "webp"}
    media_type = f"image/{media_map.get(ext, 'png')}"

    context_part = f"\nDocument context: {context[:500]}" if context else ""

    prompt = f"""Analyze this image from a document carefully.{context_part}

Describe:
1. What type of image is this (chart, graph, diagram, table, photo, etc.)
2. What information does it convey?
3. Key data points, labels, or values visible
4. What conclusion or insight can be drawn from it?

Be specific and detailed."""

    return _chat(
        messages=[{"role": "user", "content": prompt}],
        model_hf=HF_VISION_MODEL,
        model_groq=GROQ_VISION_MODEL,
        temperature=0.3,
        max_tokens=800,
        image_data={"data": img_data, "media_type": media_type},
    )
