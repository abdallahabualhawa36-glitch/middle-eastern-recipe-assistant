import os

from dotenv import load_dotenv
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda

load_dotenv()

NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")

if not NVIDIA_API_KEY:
    raise ValueError(
        "NVIDIA_API_KEY is not set. "
        "Please add it to your .env file."
    )

os.environ["NVIDIA_API_KEY"] = NVIDIA_API_KEY

instruct_llm = ChatNVIDIA(
    model="google/diffusiongemma-26b-a4b-it",
    temperature=0.7,
    timeout=120,
    max_tokens=256
)

chat_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        """
You are a friendly and expert Shopping Assistant
for a technology store.

Your goal is to help users find the best products
based ONLY on the product catalog provided below.

--------------------------------------------------
PRODUCT CATALOG
--------------------------------------------------

{product_context}

--------------------------------------------------
CONVERSATION HISTORY
--------------------------------------------------

{history}

--------------------------------------------------
USER SHOPPING STATE
--------------------------------------------------

{shopping_state}

--------------------------------------------------
RULES
--------------------------------------------------

1. Respond in the SAME LANGUAGE as the user.

2. If the user writes in Arabic, answer in Arabic.

3. If the user writes in English, answer in English.

4. Use ONLY the information available in the
   product catalog.

5. NEVER invent:
   - products
   - prices
   - specifications
   - brands
   - stock information
   - colors
   - storage
   - RAM
   - features

6. If the requested information is not available,
   say that you don't have information about it.

7. When recommending a product, explain WHY
   you recommend it.

8. Include the price when it is available.

9. If the catalog does not contain enough information
   to answer the question, clearly say so.

10. Keep the answer helpful and reasonably concise.

--------------------------------------------------
PRODUCT RECOMMENDATION EXAMPLE
--------------------------------------------------

Arabic:

أنصحك بـ [اسم المنتج] لأن [السبب].

السعر: [السعر].

المواصفات المتوفرة: [المواصفات].

English:

I recommend [Product Name] because [reason].

Price: [price].

Available specifications: [specifications].
"""
    ),
    (
        "human",
        "{input}"
    )
])


chain = (
    chat_prompt

    | RunnableLambda(
        lambda x:
            print(
                "\n🧠 FULL PROMPT INPUT:\n",
                x,
                "\n"
            ) or x
    )

    | RunnableLambda(
        lambda x:
            print(
                "🚀 SENDING REQUEST TO NVIDIA...\n"
            ) or x
    )

    | instruct_llm

    | RunnableLambda(
        lambda x:
            print(
                "✅ NVIDIA RESPONSE RECEIVED!\n"
            ) or x
    )

    | StrOutputParser()
)

print("==============================================")
print("🛒 Shopping AI initialized successfully")
print("🤖 Model: google/diffusiongemma-26b-a4b-it")
print("⏱️ LLM timeout: 120 seconds")
print("📦 Product source: Laravel API")
print("🚫 PDF/FAISS retrieval disabled")
print("==============================================")