from typing import TypedDict, Literal
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import PGVector
from app.services.duckdb_client import execute_text_to_sql
import os
import glob
import duckdb

# ==========================================
# 1. Define the State and Expected Output
# ==========================================

# 1. Initialize embeddings globally so it only loads into RAM once at startup
print("Loading HuggingFace Embeddings into API memory...")
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
DB_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://myuser:mypassword@db:5432/hybrid_ai")
COLLECTION_NAME = "enterprise_documents"

class AgentState(TypedDict):
    question: str
    route_decision: str
    sql_result: str
    rag_context: str
    final_answer: str

class RouteDecision(BaseModel):
    """Pydantic model to force the LLM to output a strict JSON structure."""
    decision: Literal["sql", "rag", "both", "general"] = Field(
        description="Choose 'sql' for numerical/tabular data analysis, 'rag' for document context, 'both' if the query needs both, or 'general' for conversational greetings."
    )

class SQLQueryOutput(BaseModel):
    """Forces the LLM to output only the SQL query."""
    sql_query: str = Field(
        description="A valid DuckDB SQL query string. Do not include markdown formatting or explanations."
    )

# ==========================================
# 2. Define the Nodes (The Actions)
# ==========================================

def router_node(state: AgentState):
    """Analyzes the question and decides the routing path."""
    
    # Initialize the Groq model
    # Llama 3.1 8B is perfect here because routing is a simple classification task,
    # and using the smaller model saves your tokens and runs instantly.
    llm = ChatGroq(model="openai/gpt-oss-20b", temperature=0)
    
    # Force the LLM to respond using the RouteDecision schema
    structured_llm = llm.with_structured_output(RouteDecision)
    
    system_prompt = """You are an intelligent routing agent for an enterprise platform. 
    You have access to two data sources:
    1. A SQL database (CSVs/Tabular data containing metrics, sales, rows, columns).
    2. A Vector database (PDFs/Documents containing text, reports, unstructured context).
    Analyze the user's query and decide which data source is needed."""
    
    result = structured_llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=state["question"])
    ])
    
    return {"route_decision": result.decision}

# Make sure to import your DuckDB function at the top of the file:
# from app.services.duckdb_client import execute_text_to_sql

def sql_node(state: AgentState):
    """Generates SQL, executes it via DuckDB, and returns the result."""
    print("--- ROUTED TO SQL ENGINE ---")
    
    # 1. Dynamically locate the most recently uploaded CSV
    # (FastAPI saves files to /app/uploads inside the container)
    upload_dir = "/app/uploads"
    list_of_csvs = glob.glob(os.path.join(upload_dir, "*.csv"))
    
    if not list_of_csvs:
        return {"sql_result": "Error: No CSV files found. Please upload a dataset first."}
        
    # Grab the newest file based on creation time
    csv_file_path = max(list_of_csvs, key=os.path.getctime)
    print(f"Using dynamic dataset: {csv_file_path}")
    
    # 2. Dynamically extract the table schema using DuckDB
    try:
        con = duckdb.connect(database=':memory:')
        # read_csv_auto automatically infers column types
        schema_df = con.execute(f"DESCRIBE SELECT * FROM read_csv_auto('{csv_file_path}')").df()
        con.close()
        
        table_schema = "Columns:\n"
        for _, row in schema_df.iterrows():
            table_schema += f"- {row['column_name']} ({row['column_type']})\n"
            
    except Exception as e:
        return {"sql_result": f"Error reading CSV schema: {str(e)}"}

    # 3. Define the strict Text-to-SQL System Prompt
    system_prompt = """You are a DuckDB SQL expert. 
    Your job is to write a SQL query that answers the user's question.
    
    CRITICAL RULES:
    1. You MUST query the table named exactly: user_data
    2. Only use the columns listed in the schema below. Do not hallucinate columns.
    3. Use DuckDB syntax (e.g., ILIKE for case-insensitive matching).
    4. Return ONLY the SQL string.
    
    SCHEMA:
    {schema}
    """
    
    # 4. Create the prompt template
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{question}")
    ])
    
    # 5. Initialize the LLM and bind the structured output
    llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)
    structured_llm = llm.with_structured_output(SQLQueryOutput)
    
    # 6. Chain them together and generate the SQL
    chain = prompt | structured_llm
    llm_response = chain.invoke({
        "schema": table_schema,
        "question": state["question"]
    })
    
    generated_sql = llm_response.sql_query
    print(f"Generated SQL: {generated_sql}")
    
    # 7. Execute the SQL against the dynamic CSV path
    execution_result = execute_text_to_sql(csv_file_path, generated_sql)
    
    return {"sql_result": str(execution_result)}

def rag_node(state: AgentState):
    """Searches PostgreSQL for relevant document chunks."""
    print("--- RETRIEVING DOCUMENT CONTEXT ---")
    question = state["question"]
    
    # 2. Connect to pgvector using the pre-loaded global embeddings
    vectorstore = PGVector(
        collection_name=COLLECTION_NAME,
        connection_string=DB_URL,
        embedding_function=embeddings,
    )
    
    # 3. Perform the Similarity Search (Retrieve top 4 chunks)
    retriever = vectorstore.as_retriever(search_kwargs={"k": 4})
    docs = retriever.invoke(question)
    
    rag_context = "\n\n---\n\n".join([doc.page_content for doc in docs])
    if not rag_context:
        rag_context = "No relevant documents found in the database."
        
    return {"rag_context": rag_context}


def both_node(state: AgentState):
    """Runs SQL + RAG collection in one node so synthesis executes exactly once."""
    sql_output = sql_node(state)
    rag_output = rag_node(state)
    return {**sql_output, **rag_output}

def synthesizer_node(state: AgentState):
    """Combines all gathered data into a final natural language answer using Groq."""
    print("--- SYNTHESIZING FINAL ANSWER ---")
    
    # 1. Safely extract data from the state using .get() 
    # If the router bypassed a node, that key might be empty.
    sql_data = state.get("sql_result", "No tabular data required for this query.")
    rag_data = state.get("rag_context", "No document context required for this query.")
    question = state["question"]

    # 2. Define the System Prompt
    system_prompt = """You are an expert enterprise AI assistant. Your goal is to provide a clear, 
    accurate, and professional answer to the user's question based strictly on the provided context.
    
    You have been provided with two potential data sources:
    1. TABULAR DATA (from SQL queries executed against company datasets).
    OR
    2. DOCUMENT CONTEXT (from company PDFs and reports).
    
    RULES:
    - Base your answer ONLY on either of the provided data. Do not hallucinate external facts.
    - If a data source says "No data required", ignore it.
    - If the provided data does not contain the answer, politely state that you do not have the information.
    - Format your response nicely using Markdown (bullet points, bold text, or small tables if appropriate).
    """

    # 3. Format the Human Prompt with the injected data
    human_prompt = f"""
    USER QUESTION: {question}
    
    --- TABULAR DATA ---
    {sql_data}
    
    --- DOCUMENT CONTEXT ---
    {rag_data}
    """
    
    # 4. Initialize Groq
    # Llama-3.3-70b-versatile is ideal here because synthesis requires high reasoning 
    # and a large context window to process all the retrieved data.
    # Temperature is slightly above 0 (e.g., 0.2) so the language feels natural but factual.
    llm = ChatGroq(model="openai/gpt-oss-120b", temperature=0.2)
    
    # 5. Invoke the LLM with an explicit tag attached
    response = llm.invoke(
        [SystemMessage(content=system_prompt), HumanMessage(content=human_prompt)],
        config={"tags": ["final_node"]}  # <-- ADD THIS LINE
    )
    
    # 6. Update the LangGraph state with the final answer
    return {"final_answer": response.content}

# ==========================================
# 3. Define the Routing Logic
# ==========================================

def route_traffic(state: AgentState):
    """Reads the state and returns the name of the next node to execute."""
    decision = state["route_decision"]
    
    if decision == "sql":
        return "sql_node"
    elif decision == "rag":
        return "rag_node"
    elif decision == "both":
        return "both_node"
    else:
        return "synthesizer_node"

# ==========================================
# 4. Build and Compile the Graph
# ==========================================

workflow = StateGraph(AgentState)

# Add nodes
workflow.add_node("router", router_node)
workflow.add_node("sql_node", sql_node)
workflow.add_node("rag_node", rag_node)
workflow.add_node("both_node", both_node)
workflow.add_node("synthesizer_node", synthesizer_node)

# Add edges
workflow.add_edge(START, "router")

# The conditional edge reads the output of 'router' and passes it to 'route_traffic'
workflow.add_conditional_edges("router", route_traffic)

# All execution paths eventually lead to the synthesizer to formulate the response
workflow.add_edge("sql_node", "synthesizer_node")
workflow.add_edge("rag_node", "synthesizer_node")
workflow.add_edge("both_node", "synthesizer_node")
workflow.add_edge("synthesizer_node", END)

# Compile
app = workflow.compile()

if __name__ == "__main__":
    # Test Question that requires both data sources
    test_state = {"question": "What were our Q3 sales figures, and what does the annual report PDF say about our Q3 marketing strategy?"}
    
    # Run the compiled workflow
    print(f"User: {test_state['question']}")
    final_state = app.invoke(test_state)
    
    print("\n=== FINAL OUTPUT ===")
    print(final_state["final_answer"])