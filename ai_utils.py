import os
from langchain_community.vectorstores import FAISS
from langchain_nvidia_ai_endpoints import ChatNVIDIA, NVIDIAEmbeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser, PydanticOutputParser  # ✅ تم التعديل
from langchain_community.document_transformers import LongContextReorder
from langchain_core.runnables import RunnableLambda
from langchain_core.runnables.passthrough import RunnableAssign
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.docstore.in_memory import InMemoryDocstore
from faiss import IndexFlatL2
from pydantic import BaseModel, Field
from langchain_core.messages import AIMessage
from utils import load_local_pdfs, get_conversation_history, get_recipe_context

# Initialize AI components
os.environ["NVIDIA_API_KEY"] = "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"

embedder = NVIDIAEmbeddings(model="nvidia/nv-embed-v1")

instruct_llm = ChatNVIDIA(
    model="deepseek-ai/deepseek-v4-flash",
    temperature=0.7,
    timeout=120  # زيادة المهلة إلى 120 ثانية لمنع انتهاء الوقت
)

long_reorder = LongContextReorder()
def RExtract(pydantic_class, llm, prompt_template):
    parser = PydanticOutputParser(pydantic_object=pydantic_class)
    format_instructions = parser.get_format_instructions()

    def preparse(user_input):
        if isinstance(user_input, AIMessage):
            user_input = user_input.content
        if '{' not in user_input:
            user_input = '{' + user_input
        if '}' not in user_input:
            user_input += '}'
        return user_input.replace("\n", " ")

    parser_prompt = ChatPromptTemplate.from_template(
    """As an advanced cooking assistant, analyze the conversation to extract precise user intent and update the knowledge state.

Format Instructions:
{format_instructions}

Current Cooking Session State:
{know_base}

Last Assistant Response:
{output}

New User Input:
{input}

Analysis Tasks:
1. Identify the user's immediate request (question/instruction)
2. Detect any new preferences or dietary restrictions
3. Note recipe modifications or substitutions mentioned
4. Track progress in multi-step recipes
5. Flag any unresolved questions needing follow-up

Output Requirements:
- Update ONLY the fields that have new information
- Maintain all existing valid context
- Never assume information not explicitly provided
- Mark unclear elements as 'unknown' rather than guessing

Updated State Analysis:"""
)

    instruct_merge = RunnableAssign({'format_instructions': lambda _: format_instructions})
    return instruct_merge | parser_prompt | llm | RunnableLambda(preparse) | parser

def initialize_docstore(pdf_paths):
    FAISS_INDEX_DIR = "docstore_index"
    if os.path.exists(os.path.join(FAISS_INDEX_DIR, "index.faiss")):
        print("Loading existing FAISS document index...")
        return FAISS.load_local(
            FAISS_INDEX_DIR,
            embedder,
            allow_dangerous_deserialization=True
        )

    print("Creating new FAISS document index...")
    docs = load_local_pdfs(pdf_paths)
    if not docs:
        raise ValueError("No valid PDFs could be loaded")

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=["\n\n", "\n", ".", ";", ",", " "]
    )

    texts = []
    metadatas = []
    for doc in docs:
        chunks = text_splitter.split_text(doc['page_content'])
        texts.extend(chunks)
        metadatas.extend([doc['metadata']] * len(chunks))

    print(f"Creating index with {len(texts)} chunks...")
    docstore = FAISS.from_texts(texts, embedder, metadatas=metadatas)

    os.makedirs(FAISS_INDEX_DIR, exist_ok=True)
    docstore.save_local(FAISS_INDEX_DIR)
    print("Document index saved.")
    return docstore

def initialize_convstore():
    CONV_INDEX_DIR = "convstore_index"
    if os.path.exists(os.path.join(CONV_INDEX_DIR, "index.faiss")):
        print("Loading existing FAISS conversation index...")
        return FAISS.load_local(
            CONV_INDEX_DIR,
            embedder,
            allow_dangerous_deserialization=True
        )

    print("Creating new empty FAISS conversation index...")
    embed_dims = len(embedder.embed_query("test"))
    convstore = FAISS(
        embedding_function=embedder,
        index=IndexFlatL2(embed_dims),
        docstore=InMemoryDocstore(),
        index_to_docstore_id={},
        normalize_L2=False
    )
    os.makedirs(CONV_INDEX_DIR, exist_ok=True)
    convstore.save_local(CONV_INDEX_DIR)
    return convstore

def diversify_documents(docs, max_per_doc=5):
    seen = {}
    result = []
    for doc in docs:
        title = doc.metadata.get("Title", "Untitled")
        if seen.get(title, 0) < max_per_doc:
            seen[title] = seen.get(title, 0) + 1
            result.append(doc)
    return result

def ensure_string_input(input_data):
    if isinstance(input_data, str):
        return input_data
    elif isinstance(input_data, dict) and 'input' in input_data:
        return input_data['input']
    elif isinstance(input_data, list) and len(input_data) > 0 and 'input' in input_data[0]:
        return input_data[0]['input']
    return str(input_data)

# Initialize document stores
PDF_DIR = "documents"
os.makedirs(PDF_DIR, exist_ok=True)
pdf_paths = [
    os.path.join(PDF_DIR, "RC_RecipeBook_Orient_EN.pdf"),
    os.path.join(PDF_DIR, "dokumen.pub_the-complete-middle-eastern-cookbook.pdf"),
    os.path.join(PDF_DIR, "الطبخ العربي-1-499 en-US (1).pdf"),
    os.path.join(PDF_DIR, "الطبخ العربي-500-714 en-US.pdf"),
]

docstore = initialize_docstore(pdf_paths)
convstore = initialize_convstore()

# Chat chain setup
# استبدال chat_prompt الحالي بهذا
chat_prompt = ChatPromptTemplate.from_messages([
    ("system", """
        You are a helpful Middle Eastern chef assistant guiding users through recipes step-by-step.
        Respond in the same language as the user's input (Arabic or English).

        Strict Rules:
        1. Only use information from the provided PDF - never bring information from external sources
        2. For greetings, respond in the same language as the user
        3. When discussing recipes, strictly follow the step-by-step process below

        When a user asks for a recipe in English:
        - If they request the **full recipe at once**, provide:
          1. Recipe name: "Recipe: [Name]"
          2. All ingredients
          3. Complete step-by-step instructions
        - If they ask normally (without requesting full steps):
          1. First provide the recipe name clearly: "Recipe: [Name]"
          2. List all ingredients needed (only from the PDF)
          3. Then provide ONLY Step 1 of the instructions
          4. End with: "Let me know when you're ready for the next step."

        When a user asks for a recipe in Arabic:
        - If they request the full recipe: 
          1. اسم الوصفة: "[الاسم]"
          2. جميع المكونات
          3. الخطوات كاملة
        - If they ask normally:
          1. اذكر اسم الوصفة: "الوصفة: [الاسم]"
          2. اذكر جميع المكونات
          3. قدم الخطوة الأولى فقط
          4. أنهي بـ: "أخبرني عندما تكون جاهزًا للخطوة التالية"

        When user asks to continue (step-by-step mode):
        - In English: Provide only the next step with "Step [N]: ..."
        - In Arabic: Provide only the next step with "الخطوة [N]: ..."

        Important:
        - Always respond in the same language as the user's input
        - For Arabic responses, use proper Arabic script (not transliteration)
        - Never mix languages in the same response

        "Knowledge State: {cooking_knowledge}"
        Chat History: {history}
        Relevant Docs: {context}
        User Language: {user_lang}
    """),
    ("user", "{input}")
])

retrieval_chain = (
    {"input": RunnableLambda(ensure_string_input)}
    | RunnableAssign({
        "history": lambda x: get_conversation_history(x.get("conversation_id", 0), 5),
        "context": lambda x: long_reorder.transform_documents(
            diversify_documents(
                docstore.as_retriever(search_kwargs={"k": 20}).invoke(x["input"])
            )
        ),
        "recipe_context": lambda x: get_recipe_context(x.get("conversation_id", 0)),
        "user_lang": lambda x: x.get("user_lang", "en")  # ✅ أضف هذا السطر
    })
)

chain = (
    chat_prompt 
    | RunnableLambda(lambda x: print("\n🧠 FULL PROMPT INPUT:\n", x, "\n") or x)
    | instruct_llm
    | StrOutputParser())