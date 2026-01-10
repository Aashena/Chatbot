#Initialize Gemini LLM
from langchain_google_genai import ChatGoogleGenerativeAI
#Create a RAG Prompt
from langchain_core.prompts import ChatPromptTemplate
#Build the chain (LangChain LCEL)
from langchain_core.runnables import RunnablePassthrough
from logger import log_interaction
from langchain_community.vectorstores import UpstashVectorStore
#To structure the LLM output
from pydantic import BaseModel, Field
from typing import Optional, Literal
#Telegram bot communication
from telegram_handler import create_alert

models_list = ['gemini-2.0-flash-lite', 'gemini-2.5-flash-lite-preview-09-2025', 'gemini-2.0-flash', 'gemini-2.5-flash-preview-09-2025', 'gemini-3-flash-preview', "gemini-2.5-flash-lite" , "gemini-2.5-flash", 'gemini-2.5-pro']
current_model_idx = 0

PROMPT = ChatPromptTemplate.from_template("""
You are a helpful customer support chatbot. Your goal is to provide accurate and helpful answers to the user.

**Guidelines for Answering:**
1. Primary Source: Always look for the answer in the provided Website Content first.
2. Helpful Expansion: If the specific answer is not found in the Website Content, but the question is somehow related to the website content, use your general knowledge outside the website content to provide a helpful response.

Website Content:
---------
{context}

Conversation History:
---------
{conversation_history}

Question:
---------
{question}
""")

#Create the RAG Chain
def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

class LLM_Response(BaseModel):
    answer: str = Field(
        description="The final answer to the user's question."
    )
    source_type: Literal["website_content", "general_knowledge", "none"] = Field(
        description="Where the information came from. 'none' if the question couldn't be answered."
    )
    is_valid: bool = Field(
        description="True if a helpful answer was provided (even from general knowledge). False if the bot refused to answer or gave a non-answer."
    )
    reason: Optional[str] = Field(
        default=None,
        description="The reason why the model could not answer, if applicable."
    )

def create_llm():
    llm = ChatGoogleGenerativeAI(
        model= models_list[current_model_idx] ,
        temperature=0,
        max_retries=0,
    )
    #Bind the structure to the model
    structured_llm = llm.with_structured_output(LLM_Response)
    return structured_llm

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
            response=response,
            conv_history=conv_history
        )
        
        if not response.is_valid:
            create_alert(self.namespace, query, response, conv_history )

        return response
        # rag_chain = (
    #     {
    #         "context": retriever | format_docs,
    #         "question": RunnablePassthrough(),
    #     }
    #     | prompt
    #     | llm
    # )