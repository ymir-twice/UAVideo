# Benchmark Prompts

## Visual Evidence QA

**Purpose:** Used for benchmark evaluation when processing images/videos.

**System Prompt:**
```
You are a benchmark assistant. Use the provided visual evidence to answer. Output the final answer only, without extra explanation unless explicitly requested.
```

**User Message Template:**
```
{question}

VISUAL EVIDENCE:
{evidence_text}

Final answer:
```

**Chinese System:**
```
你是基准测试助手。使用提供的视觉证据来回答。只需输出最终答案，除非明确要求，否则不要添加额外解释。
```

---

## Evidence Aggregation

When multiple images are processed, captions and ASR results are aggregated into evidence:

```
CAPTIONS:
{caption_1}
{caption_2}
...
```

Or with ASR:
```
CAPTIONS:
{caption_1}
{caption_2}
...

AUDIO_TRANSCRIPTION:
{asr_text}
```

---

## Usage

These prompts are used in `orchestrator.py` for the `generate()` method (benchmark mode):

```python
# In orchestrator.py - generate()
llm_messages = [
    {"role": "system", "content": "You are a benchmark assistant. Use the provided visual evidence to answer. Output the final answer only, without extra explanation unless explicitly requested."},
    {"role": "user", "content": f"{question}\n\nVISUAL EVIDENCE:\n{evidence_text}\n\nFinal answer:"}
]
```

---

## Configuration

The maximum evidence characters can be configured via:
```bash
MAX_EVIDENCE_CHARS=12000
```

If evidence exceeds this limit, it will be truncated.
