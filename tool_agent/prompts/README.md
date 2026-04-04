# Prompts

This folder contains all prompts used by the Video Understanding Agent.

## Index

| File | Purpose |
|------|---------|
| [caption.md](caption.md) | Image captioning prompts |
| [asr.md](asr.md) | Audio transcription prompts |
| [video_summary.md](video_summary.md) | Video summary generation prompts |
| [qa.md](qa.md) | Question answering prompts |
| [benchmark.md](benchmark.md) | Benchmark evaluation prompts |
| [frame_extraction.md](frame_extraction.md) | Frame extraction prompts |

## Quick Reference

### Caption
```
描述这张图片的内容，用简洁的语言说明画面中有什么，以及发生了什么。
```

### ASR
```
请转写这段音频的内容。
```

### Video Summary
```
请根据以下视频片段摘要，生成一段整体概述...
```

### QA
```
视频问答任务。请根据提供的视频记忆信息回答用户问题...
```

### Benchmark
```
You are a benchmark assistant. Use the provided visual evidence to answer.
```

## Usage

All prompts are configurable via environment variables. Check the specific prompt file for configuration options.

Prompts are loaded at runtime from the code and can be modified directly in these files for experimentation.
