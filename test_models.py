# check_models.py
import os
from langchain_nvidia_ai_endpoints import ChatNVIDIA

os.environ["NVIDIA_API_KEY"] = "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"

# جرب هذه النماذج (الأكثر استقراراً حالياً)
models_to_try = [
    "meta/llama-3.1-8b-instruct",
    "meta/llama-3.1-70b-instruct",
    "mistralai/mistral-7b-instruct-v0.3",
    "nvidia/nemotron-4-340b-instruct",
    "google/gemma-2-27b-it"
]

print("🔍 جاري اختبار النماذج...")
for model in models_to_try:
    try:
        llm = ChatNVIDIA(model=model)
        response = llm.invoke("Say hello")
        print(f"✅ {model} يعمل!")
        print(f"الرد: {response.content[:50]}...")
        break
    except Exception as e:
        print(f"❌ {model} فشل: {str(e)[:100]}")