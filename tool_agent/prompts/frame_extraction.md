# Frame Extraction Prompts

## Keyframe Detection (VLM-assisted)

**Purpose:** Determine if a frame contains significant visual changes.

**Default Prompt:**
```
这个画面是否包含重要的视觉变化，如物体出现/消失、动作变化、场景切换？请回答是或否。
```

**English:**
```
Does this frame contain significant visual changes, such as object appearance/disappearance, action changes, or scene transitions? Please answer yes or no.
```

---

## Response Keywords

When using VLM-assisted keyframe extraction, the following keywords indicate a significant change:

- `是` (yes)
- `yes`
- `变化` (change)
- `重要` (important)
- `关键` (key)

---

## Usage

These prompts are used in `video.py` for VLM-assisted keyframe extraction:

```python
# In video.py - extract_keyframes_vlm()
prompt = "这个画面是否包含重要的视觉变化，如物体出现/消失、动作变化、场景切换？请回答是或否。"

# Keywords to detect
keywords = ['是', 'yes', '变化', '重要', '关键']
```

---

## Adaptive Frame Extraction

The system also uses a color histogram chi-square distance method for adaptive frame extraction without requiring VLM:

- Frames with histogram difference above threshold are selected
- Ensures minimum 8 frames and maximum `max_frames` frames
- Falls back to uniform extraction if adaptive fails

```python
# In video.py - extract_adaptive()
threshold = self.settings.adaptive_threshold  # default: 0.3
```
