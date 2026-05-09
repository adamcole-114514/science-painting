import os
from typing import Optional, List, Dict, Generator, Union
from openai import OpenAI

DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "sk-cfd685e3d69b477cad093150ec0336d1")
MODEL_NAME = "qwen3.5-plus"
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

def call_llm_api(
    system_prompt: str,
    user_input: str,
    api_key: str = DASHSCOPE_API_KEY,
    model: str = MODEL_NAME,
    enable_search: bool = True,
    stream: bool = True,
    temperature: float = 0.7,
    max_tokens: int = 2048,
    conversation_history: Optional[List[Dict[str, str]]] = None
) -> Union[str, Generator[str, None, None]]:
    client = OpenAI(api_key=api_key, base_url=BASE_URL)

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    if conversation_history:
        messages.extend(conversation_history[-8:])
    messages.append({"role": "user", "content": user_input})

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=stream,
        extra_body={"enable_search": enable_search, "enable_thinking": False}
    )

    if stream:
        def generate():
            for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        return generate()
    else:
        return response.choices[0].message.content.strip()
