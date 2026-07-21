import streamlit as st

# ⬇️ ПЕРВЫЙ ВЫЗОВ STREAMLIT
st.set_page_config(page_title="Правовой Ассистент", page_icon="⚖️")

# Остальные импорты
import os
import re
import requests
import json
import hashlib
import chromadb
from chromadb.utils import embedding_functions
from sentence_transformers import SentenceTransformer

# ---- Настройки YandexGPT (читаем из секретов) ----
# Для локальной разработки можно временно раскомментировать и вписать ключи,
# но в облаке они должны быть в st.secrets
try:
    API_KEY = st.secrets["API_KEY"]
    FOLDER_ID = st.secrets["FOLDER_ID"]
except (KeyError, FileNotFoundError):
    API_KEY = ""
    FOLDER_ID = ""
    st.warning("Ключи API не найдены. Добавьте их в Secrets.")

YANDEXGPT_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"

# ---- Инициализация эмбеддингов и Chroma ----
# В будущем, при обновлении Streamlit до версии >=1.18, замени @st.cache на @st.cache_resource
@st.cache(allow_output_mutation=True)
def init_embedding_model():
    return SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')

@st.cache(allow_output_mutation=True)
def init_chroma():
    client = chromadb.PersistentClient(path="./chroma_db")
    collection = client.get_or_create_collection(
        name="laws",
        embedding_function=embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name='paraphrase-multilingual-MiniLM-L12-v2'
        )
    )
    return client, collection

# ---- Загрузка статей из папки laws ----
def load_articles():
    articles = []
    if not os.path.isdir("./laws"):
        return articles
    for fname in os.listdir("./laws"):
        if not fname.endswith('.txt'):
            continue
        filepath = os.path.join("./laws", fname)
        text = None
        for encoding in ['utf-8', 'cp1251', 'latin-1']:
            try:
                with open(filepath, "r", encoding=encoding) as f:
                    text = f.read().strip()
                break
            except UnicodeDecodeError:
                continue
        if text:
            title = fname.replace('.txt', '')
            articles.append((title, text))
    return articles

ARTICLES = load_articles()
_, collection = init_chroma()

# Если Chroma пуста — наполняем
if collection.count() == 0 and ARTICLES:
    for title, text in ARTICLES:
        doc_id = hashlib.md5(text.encode('utf-8')).hexdigest()
        collection.add(
            documents=[text],
            metadatas=[{"title": title}],
            ids=[doc_id]
        )

# ---- Семантический поиск через Chroma ----
def semantic_search(query, top_n=3):
    if not ARTICLES:
        return []
    results = collection.query(query_texts=[query], n_results=top_n)
    if results['documents'] and results['documents'][0]:
        found = []
        for i, doc in enumerate(results['documents'][0]):
            title = results['metadatas'][0][i]['title']
            found.append((title, doc))
        return found
    return []

# ---- Запрос к YandexGPT (исправленный промпт) ----
def ask_yandex_gpt(question, context_text):
    headers = {
        "Authorization": f"Api-Key {API_KEY}",
        "Content-Type": "application/json"
    }
    prompt = (
        "Ты — заботливый и понятливый юридический ассистент. "
        "Отвечай на вопрос пользователя, используя ИСКЛЮЧИТЕЛЬНО текст статей, приведённых ниже. "
        "Объясняй сложные термины простыми словами. "
        "Если в статьях нет точного ответа, честно скажи об этом и посоветуй обратиться к профессиональному юристу. "
        "Обязательно ссылайся на номера статей.\n\n"
        f"ВОПРОС: {question}\n\n"
        f"СТАТЬИ (используй их текст):\n{context_text}"
    )
    data = {
        "modelUri": f"gpt://{FOLDER_ID}/yandexgpt/latest",
        "completionOptions": {
            "stream": False,
            "temperature": 0.1,
            "maxTokens": 1000
        },
        "messages": [
            {"role": "system", "text": "Ты — строгий юридический ассистент, отвечающий только по предоставленным статьям."},
            {"role": "user", "text": prompt}
        ]
    }
    try:
        response = requests.post(YANDEXGPT_URL, headers=headers, json=data, timeout=30)
        if response.status_code == 200:
            result = response.json()
            return result["result"]["alternatives"][0]["message"]["text"]
        else:
            return f"Ошибка API: {response.status_code} - {response.text}"
    except Exception as e:
        return f"Ошибка соединения: {str(e)}"

# ---- Интерфейс ----
st.title("⚖️ Правовой Ассистент")
st.caption("Задайте вопрос — я найду ответ в законах РФ и объясню.")

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    if msg["role"] == "user":
        st.markdown(f"**Вы:** {msg['content']}")
    else:
        st.markdown(f"**Ассистент:** {msg['content']}")

user_input = st.text_input("Опишите вашу ситуацию:", key="user_input")
if st.button("Спросить"):
    if not user_input.strip():
        st.warning("Введите вопрос.")
    else:
        st.session_state.messages.append({"role": "user", "content": user_input})
        st.markdown(f"**Вы:** {user_input}")

        if not ARTICLES:
            answer = "❌ База законов пуста. Добавьте .txt файлы в папку 'laws'."
        else:
            with st.spinner("Ищу статьи и готовлю ответ..."):
                found = semantic_search(user_input)
                if not found:
                    answer = "❌ В базе законов не найдено подходящих статей."
                else:
                    context_parts = []
                    sources = []
                    for title, text in found:
                        sources.append(title)
                        context_parts.append(f"--- {title} ---\n{text}")
                    context = "\n\n".join(context_parts)
                    ai_answer = ask_yandex_gpt(user_input, context)
                    answer = ai_answer + "\n\n📚 **Использованные статьи:**\n" + "\n".join(f"- {s}" for s in sources)

        st.markdown(f"**Ассистент:** {answer}")
        st.session_state.messages.append({"role": "assistant", "content": answer})