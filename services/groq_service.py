"""
Groq Service — LLM calls: summary, MCQs, Q&A, image understanding
"""
import base64
from groq import Groq
from config import GROQ_API_KEY, GROQ_TEXT_MODEL, GROQ_VISION_MODEL


client = Groq(api_key=GROQ_API_KEY)


# ── Summary ───────────────────────────────────────────────────────────────────

def generate_summary(text: str) -> str:
    """PDF text ka structured summary generate karta hai."""
    prompt = f"""You are an expert document analyst.

Analyze the following text and provide a clear, structured summary with:
1. **Main Topic** — what this document is about (2-3 sentences)
2. **Key Points** — 5-8 bullet points of the most important information
3. **Important Concepts** — list any technical terms or key concepts explained
4. **Conclusion** — main takeaway in 2-3 sentences

TEXT:
{text[:6000]}

Provide a well-structured, informative summary."""

    response = client.chat.completions.create(
        model=GROQ_TEXT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=1500
    )
    return response.choices[0].message.content


# ── MCQs ──────────────────────────────────────────────────────────────────────

def generate_mcqs(text: str, num_questions: int = 5) -> list[dict]:
    """
    Text se MCQs generate karta hai.
    Returns list of dicts: {question, options: [A,B,C,D], answer, explanation}
    """
    prompt = f"""You are an expert educator. Create {num_questions} multiple choice questions from the text below.

RULES:
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
{text[:5000]}

Return ONLY the JSON array, no extra text."""

    response = client.chat.completions.create(
        model=GROQ_TEXT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
        max_tokens=2000
    )

    import json
    raw = response.choices[0].message.content.strip()

    # JSON extract karo (kabhi kabhi model extra text add karta hai)
    start = raw.find("[")
    end   = raw.rfind("]") + 1
    if start != -1 and end > start:
        raw = raw[start:end]

    return json.loads(raw)


# ── Q&A (Chat) ────────────────────────────────────────────────────────────────

def answer_question(question: str, context_chunks: list[str]) -> str:
    """
    Retrieved chunks ke basis pe user question ka jawab deta hai.
    """
    context = "\n\n---\n\n".join(context_chunks)

    prompt = f"""You are a helpful assistant answering questions about a document.

Use ONLY the provided context to answer. If the answer is not in the context, say:
"I couldn't find this information in the document."

CONTEXT:
{context}

QUESTION: {question}

Provide a clear, accurate answer based on the context above."""

    response = client.chat.completions.create(
        model=GROQ_TEXT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=1000
    )
    return response.choices[0].message.content


# ── Image Understanding ───────────────────────────────────────────────────────

def understand_image(image_path: str, context: str = "") -> str:
    """
    Image ko base64 mein convert karke Groq Vision ko bhejta hai.
    Returns image description/explanation.
    """
    # Image ko base64 encode karo
    with open(image_path, "rb") as f:
        img_data = base64.b64encode(f.read()).decode("utf-8")

    # Extension se media type
    ext = image_path.split(".")[-1].lower()
    media_type_map = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "gif": "gif", "webp": "webp"}
    media_type = f"image/{media_type_map.get(ext, 'png')}"

    context_part = f"\nDocument context: {context[:500]}" if context else ""

    prompt = f"""Analyze this image from a document carefully.{context_part}

Describe:
1. What type of image is this (chart, graph, diagram, table, photo, etc.)
2. What information does it convey?
3. Key data points, labels, or values visible
4. What conclusion or insight can be drawn from it?

Be specific and detailed."""

    response = client.chat.completions.create(
        model=GROQ_VISION_MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{media_type};base64,{img_data}"
                        }
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }
        ],
        temperature=0.3,
        max_tokens=800
    )
    return response.choices[0].message.content
