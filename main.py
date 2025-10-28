import os
import openai

openai_client = openai.OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY", "sk-nHtiNgJH62prZkSfWyGcpHUEYq7lPJJ81Ce3f1zGknfJdA7M"),
    base_url=os.environ.get("OPENAI_BASE_URL", "https://api.key77qiqi.cn/v1")
)

