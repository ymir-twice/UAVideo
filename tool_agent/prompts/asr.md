# ASR (Speech Recognition) Prompts

## Audio Transcription

**Default Prompt:**
```
请转写这段音频的内容。
```

**Chinese:**
```
请转写这段音频的内容。
```

**English:**
```
Please transcribe the content of this audio.
```

**With Context:**
```
请转写这段音频的内容。如果有背景音乐或噪音，请忽略它们，专注于人声。
```

---

## Usage

These prompts are used by `VLLMASRClient` when calling vLLM-deployed ASR models (e.g., Qwen3-ASR-1.7B) for audio transcription.

```python
# In vllm_client.py
prompt = prompt or "请转写这段音频的内容。"
```

---

## Note

The ASR model is deployed via vLLM at `http://localhost:8008/v1` and uses the Qwen3-ASR-1.7B model. The transcription is performed by sending audio data as base64-encoded WAV to the vLLM endpoint.
