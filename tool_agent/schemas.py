from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel


class ImageURL(BaseModel):
    url: str


class ContentPartText(BaseModel):
    type: Literal["text"]
    text: str


class ContentPartImageURL(BaseModel):
    type: Literal["image_url"]
    image_url: ImageURL


ContentPart = Union[ContentPartText, ContentPartImageURL, Dict[str, Any]]


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: Union[str, List[ContentPart]]


class ChatCompletionRequest(BaseModel):
    model: Optional[str] = None
    messages: List[ChatMessage]
    stream: Optional[bool] = False
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None


class ChatCompletionResponseMessage(BaseModel):
    role: Literal["assistant"] = "assistant"
    content: str


class ChatCompletionChoice(BaseModel):
    index: int = 0
    message: ChatCompletionResponseMessage
    finish_reason: Optional[str] = "stop"


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str = "tool-agent"
    choices: List[ChatCompletionChoice]
    usage: Optional[Dict[str, int]] = None

