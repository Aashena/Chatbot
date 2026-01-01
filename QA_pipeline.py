#Initialize Gemini LLM
from langchain_google_genai import ChatGoogleGenerativeAI
#Create a RAG Prompt
from langchain_core.prompts import ChatPromptTemplate
#Build the chain (LangChain LCEL)
from langchain_core.runnables import RunnablePassthrough
from logger import log_interaction
from langchain_community.vectorstores import UpstashVectorStore

models_list = ['gemini-2.5-flash-lite-preview-09-2025', 'gemini-2.5-flash-preview-09-2025', 'gemini-3-flash-preview', "gemini-2.5-flash-lite" , "gemini-2.5-flash", 'gemini-2.5-pro', 'gemini-2.0-flash-lite', 'gemini-2.0-flash',]
current_model_idx = 0

PROMPT = ChatPromptTemplate.from_template("""
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
    return "\n\n".join(doc.page_content for doc in docs)

def create_llm():
    llm = ChatGoogleGenerativeAI(
        model= models_list[current_model_idx] ,
        temperature=0,
        max_retries=0,
    )
    return llm

def increase_current_model_idx():
    global current_model_idx
    current_model_idx +=1
    if current_model_idx>=len(models_list):
        current_model_idx=0

class QA_module:

    def __init__(self, name_space):
        self.namespace = name_space
        vectorstore = UpstashVectorStore(embedding=True, namespace = name_space)
        #Create a Retriever
        self.retriever = vectorstore.as_retriever(
            search_kwargs={"k": 5},
        )
        self.llm = create_llm()

    def ask(self, query: str , conv_history='' ):

        docs = self.retriever.invoke(query)
        context = format_docs(docs)

        response = None
        while response is None:
            try:
                response = self.llm.invoke(
                    PROMPT.format(
                        context=context,
                        question=query,
                        conversation_history=conv_history
                    )
                )
            except Exception as e:
                print(f"Rate limit hit for {models_list[current_model_idx]}! Switching model to {models_list[current_model_idx+1]}...")
                increase_current_model_idx()
                self.llm = create_llm()

        log_interaction(
            namespace=self.namespace,
            question=query,
            context=context,
            answer=response.content,
            conv_history=conv_history
        )

        return response.content
        # rag_chain = (
    #     {
    #         "context": retriever | format_docs,
    #         "question": RunnablePassthrough(),
    #     }
    #     | prompt
    #     | llm
    # )