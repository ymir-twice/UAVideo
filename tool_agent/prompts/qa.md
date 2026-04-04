# Video Question Answering Prompts

## QA Prompt Template

**Purpose:** Answer questions based on video memory/context.

**Prompt Template:**
```
视频问答任务。请根据提供的视频记忆信息回答用户问题。

如果记忆信息不足以回答问题，请说明"根据视频内容无法确定"，不要编造答案。

{video_info}

{context}

用户问题: {question}

请给出准确、简洁的回答：
```

**System Prompt:**
```
你是专业的视频理解助手，根据提供的记忆信息准确回答问题。
```

**Chinese:**
```
视频问答任务。请根据提供的视频记忆信息回答用户问题。

如果记忆信息不足以回答问题，请说明"根据视频内容无法确定"，不要编造答案。

{video_info}

{context}

用户问题: {question}

请给出准确、简洁的回答：
```

**English:**
```
Video QA task. Please answer the user's question based on the provided video memory information.

If the memory information is insufficient to answer the question, say "Cannot be determined from video content" and do not fabricate answers.

Video Information:
{video_info}

Context:
{context}

User Question: {question}

Please provide an accurate, concise answer:
```

---

## Usage

These prompts are used in `orchestrator.py` for the `answer_question()` method:

```python
# In orchestrator.py - answer_question()
prompt = f"""视频问答任务。请根据提供的视频记忆信息回答用户问题。
...
"""
```
