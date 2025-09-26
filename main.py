from mssql_agent.sqldb import MSSQLConnector
from fastapi import FastAPI, HTTPException,Request
from fastapi.responses import JSONResponse
from mssql_agent.sqldb import MSSQLConnector
from langchain_openai import ChatOpenAI
from langchain_openai import ChatOpenAI


app = FastAPI(title="SQL LLM API")


llm= ChatOpenAI(
        openai_api_key="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",
        openai_api_base="https://openrouter.ai/api/v1",
        model="meta-llama/llama-3.3-70b-instruct"
        )


conn = MSSQLConnector(
    username="sa",
    password="sa@12309876",
    host="192.168.152.22",
    port=1433,
    database="CT_Demo"
)



@app.post("/query")
async def run_query(req: Request):
    try:
        data = await req.json()  # Parse JSON body
        question = data.get("question")
        if not question:
            raise HTTPException(status_code=400, detail="Missing 'question' in request body")
        
        result = conn.invoke(question, llm)
        # conn.invoke may return a dict or string
        output = result["answer"] if isinstance(result, dict) else str(result)
        return JSONResponse(content={"result": output})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))