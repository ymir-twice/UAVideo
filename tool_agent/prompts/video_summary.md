# Video Summary Prompts

## Semantic Segment Summary (语义片段摘要)

**Purpose:** Generate a concise semantic segment summary from frame descriptions.

**Prompt Template:**
```
请根据以下视频帧描述，生成一个简洁的语义片段摘要：

时间范围: {start_time:.1f}s - {end_time:.1f}s

帧描述:
{content}

请提取:
1. 片段摘要（1-2句话）
2. 关键实体（人物、物体、地点等）
3. 关键事件（动作、发生的事）
4. 最重要的关键帧描述

以JSON格式输出:
{{"summary": "...", "entities": [...], "events": [...], "key_frame": "..."}}
```

**Chinese:**
```
请根据以下视频帧描述，生成一个简洁的语义片段摘要：

时间范围: {start_time:.1f}s - {end_time:.1f}s

帧描述:
{content}

请提取:
1. 片段摘要（1-2句话）
2. 关键实体（人物、物体、地点等）
3. 关键事件（动作、发生的事）
4. 最重要的关键帧描述

以JSON格式输出:
{"summary": "...", "entities": [...], "events": [...], "key_frame": "..."}
```

---

## Overall Video Summary (整体视频摘要)

**Purpose:** Generate an overall video summary from segment summaries.

**Prompt Template:**
```
请根据以下视频片段摘要，生成一段整体概述：

视频时长: {duration:.1f}秒
片段数量: {count}

片段摘要:
{content}

请生成一段2-3句话的视频整体概述，简明扼要地描述视频的主要内容。
```

**System Prompt:**
```
你是视频理解助手，生成简洁准确的摘要。
```

---

## Usage

These prompts are used in `memory.py` and `orchestrator.py`:

```python
# In memory.py - merge_frames_to_segment()
prompt = f"""请根据以下视频帧描述，生成一个简洁的语义片段摘要：
...
"""

# In orchestrator.py - _generate_overall_summary()
prompt = f"""请根据以下视频片段摘要，生成一段整体概述：
...
"""
```
