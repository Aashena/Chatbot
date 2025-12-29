#Load the Vector Store from Disk
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings

# Recreate the embedding function
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-mpnet-base-v2")#,
                                  # model_kwargs={"device": "mps"})

# Load existing Chroma DB
vectorstore = Chroma(
    persist_directory="./chroma_db",
    embedding_function=embeddings,
)

#Create a Retriever
retriever = vectorstore.as_retriever(
    search_type="similarity",
    search_kwargs={"k": 10},
)

#Initialize Gemini LLM
from langchain_google_genai import ChatGoogleGenerativeAI
models_list = ["gemini-2.5-flash-lite" , "gemini-2.5-flash"]
current_model_idx = 0

llm = ChatGoogleGenerativeAI(
    model= models_list[current_model_idx] ,
    temperature=0,
    max_retries=0,
    additional_kwargs={
        "retry": None,  # Disable retry policy
    }
)

#Create a RAG Prompt
from langchain_core.prompts import ChatPromptTemplate

prompt = ChatPromptTemplate.from_template("""
You are a helpful customer-support chatbot.
Answer the user's question using the information provided in the 'context' and the 'conversation history'.
If the question is not related to the given context or the conversation history, say "I don't know based on the website content."

Context:
---------
{context}

Conversation History:
---------
{conversation_history}

Question:
---------
{question}

Answer:
---------
""")

#Create the RAG Chain
def format_docs(docs):
    docs_page_content = []
    for doc in docs:
        page_content = " ".join(doc.page_content.split() )
        docs_page_content.append(page_content)
    return "\n\n".join(doc for doc in docs_page_content)

#Build the chain (LangChain LCEL)
from langchain_core.runnables import RunnablePassthrough
from logger import log_interaction
# rag_chain = (
#     {
#         "context": retriever | format_docs,
#         "question": RunnablePassthrough(),
#     }
#     | prompt
#     | llm
# )
def ask(query: str , conv_history='' ):
    docs = retriever.invoke(query)
    context = format_docs(docs)

    response = llm.invoke(
        prompt.format(
            context=context,
            question=query,
            conversation_history=conv_history
        )
    )

    log_interaction(
        question=query,
        context=context,
        answer=response.content,
        conv_history=conv_history
    )

    return response.content