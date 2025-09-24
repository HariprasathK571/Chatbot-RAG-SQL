from langchain_community.utilities.sql_database import SQLDatabase
from typing_extensions import TypedDict,Annotated
from langchain_community.tools.sql_database.tool import QuerySQLDatabaseTool
from langchain_core.prompts import ChatPromptTemplate

class QueryOutput(TypedDict):
    """Generated SQL query."""

    query: Annotated[str, ..., "Syntactically valid SQL query."]

class MSSQLConnector:
    """SQL Server (MSSQL) database connection manager."""

    def __init__(self, username: str, password: str, host: str, port: int, 
                 database: str, driver: str = "ODBC Driver 17 for SQL Server"):
        self.username = username
        self.password = password
        self.host = host
        self.port = port
        self.database = database
        self.driver = driver

        # Escape special chars in password for URI (e.g., @, #, etc.)
        safe_password = password.replace("@", "%40")

        # Build URI
        self.uri = (
            f"mssql+pyodbc://{username}:{safe_password}"
            f"@{host}:{port}/{database}?driver={driver.replace(' ', '+')}"
        )

        # Initialize db connection
        self.db = SQLDatabase.from_uri(self.uri)

    def get_db(self) -> SQLDatabase:
        """Return the SQLDatabase object."""
        return self.db
    
    def promptemp(self):   
        system_message = """
        You are an expert SQL Server (MSSQL) query generator.

        Given an input question, create a syntactically correct {dialect} query to
        run to help find the answer. Unless the user specifies in his question a
        specific number of examples they wish to obtain, always limit your query to
        at most {top_k} results. You can order the results by a relevant column to
        return the most interesting examples in the database.

        Never query for all the columns from a specific table, only ask for a the
        few relevant columns given the question.

        Pay attention to use only the column names that you can see in the schema
        description. Be careful to not query for columns that do not exist. Also,
        pay attention to which column is in which table.

        Rules:
        - Always generate T-SQL queries.
        - Use TOP {top_k} instead of LIMIT.
        - Do not use LIMIT, OFFSET, or RETURNING clauses (not supported in SQL Server).
        - Only use the columns and tables listed in the schema.
        - Never select all columns (*), only the required ones.
        - Ensure syntax is valid for Microsoft SQL Server.

        Only use the following tables:
        Table Names: {table_info}

        """

        user_prompt = "Question: {input}"

        query_prompt_template = ChatPromptTemplate(
            [("system", system_message), ("user", user_prompt)]
        )
    

        return query_prompt_template
    
    def write_query(self,question,llm):
        """Generate SQL query to fetch information."""
        query_prompt_template = self.promptemp()
        prompt = query_prompt_template.invoke(
            {
                "dialect": self.db.dialect,
                "top_k": 10,
                "table_info": self.db.get_table_info(),
                "input": question
            }
        )
        print(prompt)
        structured_llm = llm.with_structured_output(QueryOutput)
        result = structured_llm.invoke(prompt)
        return result
    
    def execute_query(self,query):
        """Execute SQL query."""
        execute_query_tool = QuerySQLDatabaseTool(db= self.db)
        sqlresult =  execute_query_tool.invoke(query)
        return sqlresult
    
    def generate_answer(self,question,querygenbyllm,query_values,llm):
        """Answer question using retrieved information as context."""
        prompt = (
            "Given the following user question, corresponding SQL query, "
            "and SQL result, answer the user question.\n\n"
            f"Question: {question}\n"
            f"SQL Query: {querygenbyllm}\n"
            f"SQL Result: {query_values}"
        )
        response = llm.invoke(prompt)
        return {"answer": response.content}
    
    def invoke(self,question,llm):
        querygenbyllm = self.write_query(question,llm)
        print(querygenbyllm)
        query_values = self.execute_query(querygenbyllm)
        print(query_values)
        final_summarization = self.generate_answer(question,querygenbyllm,query_values,llm)
        print(final_summarization)

        return final_summarization

