# Caption Prompts

## Image Caption (单图描述)

**Default Prompt:**
```
描述这张图片的内容，用简洁的语言说明画面中有什么，以及发生了什么。
```

**Chinese:**
```
描述这张图片的内容，用简洁的语言说明画面中有什么，以及发生了什么。
```

**English:**
```
Describe the content of this image in concise language, explaining what is in the scene and what is happening.
```

---

## Multi-Image Caption (多图描述)

**Default Prompt:**
```
依次描述这些图片的内容，用简洁的语言说明每张画面中有什么。
```

**Chinese:**
```
依次描述这些图片的内容，用简洁的语言说明每张画面中有什么。
```

**English:**
```
Describe the content of these images in order, using concise language to explain what is in each scene.
```

---

## Usage

These prompts are used by `CaptionEngine` when calling vLLM-deployed VLM models (e.g., Qwen3-VL-4B) for image understanding.

```python
# In vllm_client.py
prompt = "描述这张图片的内容，用简洁的语言说明画面中有什么，以及发生了什么。"
```
