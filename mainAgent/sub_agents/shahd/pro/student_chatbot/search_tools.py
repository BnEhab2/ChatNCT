#search_tools.py
import os
import pickle
import faiss
import numpy as np
from openai import OpenAI
from .utils import load_data

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

folder = os.path.join(os.path.dirname(__file__), "data")
emb_file = os.path.join(folder, "data_embeddings.pkl")
index_file = os.path.join(folder, "data_index.faiss")
data_file = os.path.join(folder, "data.pkl")


data = load_data(folder)

if len(data) == 0:
    raise ValueError("No data found.")


if os.path.exists(emb_file) and os.path.exists(index_file) and os.path.exists(data_file):
    print("Loading saved embeddings and index...")
    with open(emb_file, "rb") as f:
        embeddings_matrix = pickle.load(f)
    index = faiss.read_index(index_file)
    with open(data_file, "rb") as f:
        data = pickle.load(f)
else:

    embeddings = []

    for line in data:

        response = client.embeddings.create(
            input=line,
            model="text-embedding-3-small"
        )

        embeddings.append(response.data[0].embedding)

    embeddings_matrix = np.array(embeddings).astype("float32")

    d = embeddings_matrix.shape[1]
    index = faiss.IndexFlatL2(d)
    index.add(embeddings_matrix)

    with open(emb_file, "wb") as f:
        pickle.dump(embeddings_matrix, f)

    faiss.write_index(index, index_file)

    with open(data_file, "wb") as f:
        pickle.dump(data, f)


stop_words = {"اي","ما","متى","كم","هل","كيف","أين"}

def search_data(query: str):

    query_words = [w.lower() for w in query.split() if w.lower() not in stop_words]

    if len(query_words) == 0:
        return "يرجى توضيح السؤال."

    query_response = client.embeddings.create(
        input=query,
        model="text-embedding-3-small"
    )

    query_emb = np.array([query_response.data[0].embedding]).astype("float32")

    D, I = index.search(query_emb, k=3)

    for idx in I[0]:

        answer = data[idx]

        match_count = sum(1 for w in query_words if w in answer.lower())

        if match_count >= 1:
            return answer

    return "عذراً، يرجى التواصل مع شؤون الطلبة."