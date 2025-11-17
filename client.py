import os
import openai
import yaml
from pathlib import Path
from typing import Dict, List, Any
import logging
import json

openai_client = openai.OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY", "sk-bmsWLavVv66gpmuONjKKLWrNGKSQkzj2u4grluethb07CSt6"), # sk-nHtiNgJH62prZkSfWyGcpHUEYq7lPJJ81Ce3f1zGknfJdA7M
    base_url=os.environ.get("OPENAI_BASE_URL", "https://yeysai.com/v1") # https://api.key77qiqi.cn/v1
)

def generate_skill(sys_prompt: str, usr_prompt: str, knowledge_path: str) -> str:
    response = openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": usr_prompt}
        ],
        temperature=0.7,
        max_tokens=2000
    )
    return response.choices[0].message.content

if __name__ == "__main__":
    print("starting")
    print(generate_skill(
        sys_prompt="You are a helpful assistant that helps people find information.",
        usr_prompt="What is the capital of France?",
        knowledge_path="knowledges/lecture02.pptx"))