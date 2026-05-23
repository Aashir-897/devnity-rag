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
    prompt = f"""You are an expert document analyst.

Analyze the following text and provide a clear, structured summary.
Adjust the depth and length of your summary to match the document — concise for short or simple documents, detailed for long or complex ones.

Include:
1. **Main Topic** — what this document is about
2. **Key Points** — the most important information, proportional to content
3. **Important Concepts** — any technical terms or key concepts explained
4. **Conclusion** — main takeaway

TEXT:
{text[:10000]}

Provide a well-structured, informative summary."""

    return _chat(
        messages=[{"role": "user", "content": prompt}],
        model_hf=HF_TEXT_MODEL,
        model_groq=GROQ_TEXT_MODEL,
        temperature=0.3,
        max_tokens=1500,
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
    "explanation": "Brief explanation why A is correct"
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

RESPONSE FORMAT (strict JSON array):
[
  {{
    "question": "Question text here?",
    "answer": "Concise but complete answer based on the text."
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

Use ONLY the provided context to answer. If the answer is not in the context, say:
"I couldn't find this information in the document."

CONTEXT:
{context}

QUESTION: {question}

Provide a clear, accurate answer based on the context above."""

    return _chat(
        messages=[{"role": "user", "content": prompt}],
        model_hf=HF_TEXT_MODEL,
        model_groq=GROQ_TEXT_MODEL,
        temperature=0.2,
        max_tokens=1000,
    )


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
