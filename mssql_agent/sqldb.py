import logging
# logging.basicConfig()
# logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)
# logging.getLogger("sqlalchemy.pool").setLevel(logging.INFO)
from langchain_community.utilities.sql_database import SQLDatabase
from typing_extensions import TypedDict,Annotated
from langchain_community.tools.sql_database.tool import QuerySQLDatabaseTool
from langchain_core.prompts import ChatPromptTemplate
from colorama import Fore, Style, init
from langchain_openai import ChatOpenAI
init(autoreset=True)  # ensures colors reset after each print
import asyncio
import re
from sqlalchemy import create_engine,inspect,text
from sqlalchemy.exc import OperationalError, SQLAlchemyError



class QueryOutput(TypedDict):
    """Generated SQL query."""

    query: Annotated[str, ..., "Syntactically valid SQL query."]

class MSSQLConnector:
    """Optimized SQL Server (PostgreSQL dialect) connection manager with connection pooling and retry."""

    def __init__(self, username: str, password: str, host: str, port: int, database: str, driver: str = "ODBC Driver 17 for SQL Server"):
        self.username = username
        self.password = password.replace("@", "%40")  # escape special chars
        self.host = host
        self.port = port
        self.database = database
        self._engine = None
        self._db = None
        self.driver = driver
        self._schema = None
    # ----------------------------------------------------------------
    # 🧩 DATABASE CONNECTION MANAGEMENT
    # ----------------------------------------------------------------
    def _create_engine(self):
        """Create a SQLAlchemy engine with connection pooling."""
        # uri = f"postgresql+psycopg2://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"

        uri = (
            f"mssql+pyodbc://{self.username}:{self.password}"
            f"@{self.host}:{self.port}/{self.database}?driver={self.driver.replace(' ', '+')}"
        )
        engine = create_engine(
            uri,
            pool_pre_ping=True,      # checks if connection is alive
            pool_size=5,             # maintain 5 connections
            max_overflow=10,         # allow up to 10 more temporary ones
            pool_recycle=1800,       # recycle every 30 minutes
            pool_timeout=30,         # 30s timeout for waiting connections
        )
        return engine

    def connect(self):
        """Establish a pooled SQL connection if not already active."""
        if self._db is None:
            if self._engine is None:
                self._engine = self._create_engine()
            self._db = SQLDatabase.from_uri(self._engine.url)
        return self._db
    
    def export_schema_with_samples(self,engine = None, sample_limit=2):
        """
        Return a formatted string containing all schemas, tables, 
        CREATE TABLE definitions, and sample rows.
        """
        # ensure we have an engine
        if engine is None:
            if self._engine is None:
                self._engine = self._create_engine()
            engine = self._engine

        inspector = inspect(engine)
        output = []  # Collect all text lines here

        with engine.connect() as conn:
            for schema in inspector.get_schema_names():
                output.append(f"-- Schema: {schema}")
                for table_name in inspector.get_table_names(schema=schema):
                    output.append(f"\n-- Table: {schema}.{table_name}")
                    
                    # 1️⃣ Get columns and their definitions
                    columns = inspector.get_columns(table_name, schema=schema)
                    
                    ddl = f"CREATE TABLE {schema}.[{table_name}] (\n"
                    column_defs = []
                    for col in columns:
                        col_def = f"    [{col['name']}] {col['type']}"
                        if not col.get("nullable", True):
                            col_def += " NOT NULL"
                        column_defs.append(col_def)
                    
                    ddl += ",\n".join(column_defs) + "\n);"
                    output.append(ddl)
                    
                    # 2️⃣ Fetch sample rows
                    try:
                        result = conn.execute(text(f"SELECT TOP {sample_limit} * FROM {schema}.[{table_name}]"))
                        rows = result.fetchall()
                        if rows:
                            cols = result.keys()
                            output.append(f"\n/*\n{len(rows)} rows from {table_name} table:")
                            output.append("\t".join(cols))
                            for row in rows:
                                output.append("\t".join(str(x) for x in row))
                            output.append("*/\n")
                    except Exception as e:
                        output.append(f"/* Could not fetch rows: {e} */\n")
        
        # Return everything as one string
        return "\n".join(output)
    
    @property
    def schema(self):
        if self._schema is None:
            self._schema = self.export_schema_with_samples(self._engine)
        return self._schema
# class MSSQLConnector:
#     """SQL Server (MSSQL) database connection manager."""
#     def __init__(self, username: str, password: str, host: str, port: int, database: str):
#         self.username = username
#         self.password = password
#         self.host = host
#         self.port = port
#         self.database = database

#         # Escape special chars in password for URI (e.g., @, #, etc.)
#         safe_password = password.replace("@", "%40")

#         # Build PostgreSQL URI
#         self.uri = f"postgresql+psycopg2://{username}:{safe_password}@{host}:{port}/{database}"
#         self.db = SQLDatabase.from_uri(self.uri,schema="dbo")


#     def get_db(self) -> SQLDatabase:
#         """Return the SQLDatabase object."""
#         return self.db
    
    def promptemp(self):   
        # system_message = """
        # You are an expert SQL (PostgreSQL) query generator.

        # Given an input question, create a syntactically correct {dialect} query to
        # run to help find the answer. Unless the user specifies in his question a
        # specific number of examples they wish to obtain, always limit your query to
        # at most {top_k} results. You can order the results by a relevant column to
        # return the most interesting examples in the database.

        # Never query for all the columns from a specific table, only ask for a few
        # relevant columns given the question.

        # Pay attention to use only the column names that you can see in the schema
        # description. Be careful to not query for columns that do not exist. Also,
        # pay attention to which column is in which table.

        # Rules:
        # - Always generate PostgreSQL queries.
        # - Use `LIMIT {top_k}` to restrict the number of rows.
        # - Do not use `TOP`, `RETURNING` (unless needed for INSERT), or any T-SQL-specific clauses.
        # - Only use the columns and tables listed in the schema.
        # - Never select all columns (*), only the required ones.
        # - Ensure syntax is valid for PostgreSQL.

        # Only use the following tables:
        # Table Names: {table_info}


        # """
        system_message = """You are an expert SQL Server (MSSQL) query generator.

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
        Table Names: {table_info}"""

        user_prompt = "Question: {input}"

        query_prompt_template = ChatPromptTemplate(
            [("system", system_message), ("user", user_prompt)]
        )
    

        return query_prompt_template
    
    

    def write_query(self,question,llm):
        """Generate SQL query to fetch information."""
        db = self.connect()
        DB_schema = self.schema
        query_prompt_template = self.promptemp()
        # cleanschema=self.clean_schema(self.db.get_table_info())
        prompt = query_prompt_template.invoke(
            {
                "dialect": db.dialect,
                "top_k": 10,
                "table_info": DB_schema,
                "input": question
            }
        )
        print(prompt)
        structured_llm = llm.with_structured_output(QueryOutput)
        result = structured_llm.invoke(prompt)
        return result
    
    def execute_query(self,query):
        """Execute SQL query."""
        db = self.connect()
        execute_query_tool = QuerySQLDatabaseTool(db=db)
        sqlresult =  execute_query_tool.invoke(query)

        if isinstance(sqlresult, str) and sqlresult.lower().startswith("error:"):
            raise Exception(sqlresult)
        return sqlresult


    async def invoke_streaming(self, question, llm:ChatOpenAI):

        attempt = 0
        querygenbyllm = None  # initialize
        max_retries = 1
        db = self.connect()

        while attempt <= max_retries:
            try:
                # Generate query (first attempt or feedback)
                if attempt == 0:
                    querygenbyllm = self.write_query(question, llm)
                    # querygenbyllm = {"query":"usuffsdf"}
                else:
                    # regenerate query based on last error
                    feedback_prompt = (
                        f"The previously generated SQL query failed:\n{querygenbyllm}\n"
                        f"Error message: {last_error}\n"
                        f"Tables/columns allowed: {db.get_table_info()}\n"
                        f"Please generate a corrected SQL query for the same user question:\n{question}"
                    )
                    structured_llm = llm.with_structured_output(QueryOutput)
                    querygenbyllm = structured_llm.invoke(feedback_prompt)
                    # querygenbyllm = {"query":"usuffsdf"}


                sql_text = querygenbyllm["query"] if isinstance(querygenbyllm, dict) else str(querygenbyllm)
                print(Fore.GREEN + f'Generated SQL:\n"{sql_text}"' + Style.RESET_ALL)

                # Execute SQL
                try:
                    query_values = self.execute_query(sql_text)
                    print(Fore.RED + f'Query Result:\n"{query_values}"' + Style.RESET_ALL)
                except Exception as sql_error:
                    last_error = str(sql_error)
                    print(Fore.RED + f'SQL Execution failed:\n"{last_error}"' + Style.RESET_ALL)
                    attempt += 1
                    if attempt > max_retries:
                        # ✅ fallback if retries exhausted
                        fallback_prompt = (
                            f"The user asked: {question}\n"
                            f"However, the system could not retrieve an answer from the database "
                            f"after {max_retries} attempts.\n"
                            "Please provide a polite, general response that acknowledges the failure "
                            "without exposing technical details, and suggest the user try rephrasing."
                        )
                        async for token in llm.astream(fallback_prompt):
                            yield token.content

                        return
                    continue  # retry loop

                # Only if SQL succeeded, generate streaming answer
                answer_prompt = (
                    "Given the following user question, corresponding SQL query, "
                    "and SQL result, answer the user question.\n\n"
                    f"Question: {question}\n"
                    f"SQL Query: {sql_text}\n"
                    f"SQL Result: {query_values}"
                )
                async for token in llm.astream(answer_prompt):
                    yield token.content

                return
            
            except Exception as e:
                # Catch unexpected errors in query generation
                last_error = str(e)
                print(Fore.RED + f'Attempt {attempt+1} failed with error:\n"{last_error}"' + Style.RESET_ALL)
                attempt += 1
            # 🚨 If loop is exhausted without success (e.g. DB down, LLM issue, etc.)
            
        fallback_prompt = (
            f"The user asked: {question}\n\n"
            f"The system failed after {max_retries+1} attempts.\n"
            f"Last recorded error was:\n{last_error}\n\n"
            "Please summarize this error into a polite and general response for the user, "
            "without exposing technical details, but still acknowledging that something went wrong. "
            "Suggest they try again later or rephrase their request."
        )

        try:
            async for token in llm.astream(fallback_prompt):
                yield token.content
        except Exception:
            yield "Sorry, something went wrong while processing your request. Please try again later."
        


#-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------


# import asyncio
# import re
# from typing_extensions import TypedDict, Annotated
# from colorama import Fore, Style, init
# from langchain_core.prompts import ChatPromptTemplate
# from langchain_openai import ChatOpenAI
# from langchain_community.utilities.sql_database import SQLDatabase
# from langchain_community.tools.sql_database.tool import QuerySQLDatabaseTool
# from sqlalchemy import create_engine
# from sqlalchemy.exc import OperationalError, SQLAlchemyError

# init(autoreset=True)


# class QueryOutput(TypedDict):
#     """Generated SQL query."""
#     query: Annotated[str, ..., "Syntactically valid SQL query."]


# class MSSQLConnector:
#     """Optimized SQL Server (PostgreSQL dialect) connection manager with connection pooling and retry."""

#     def __init__(self, username: str, password: str, host: str, port: int, database: str):
#         self.username = username
#         self.password = password.replace("@", "%40")  # escape special chars
#         self.host = host
#         self.port = port
#         self.database = database
#         self._engine = None
#         self._db = None

#     # ----------------------------------------------------------------
#     # 🧩 DATABASE CONNECTION MANAGEMENT
#     # ----------------------------------------------------------------
#     def _create_engine(self):
#         """Create a SQLAlchemy engine with connection pooling."""
#         uri = f"postgresql+psycopg2://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"
#         engine = create_engine(
#             uri,
#             pool_pre_ping=True,      # checks if connection is alive
#             pool_size=5,             # maintain 5 connections
#             max_overflow=10,         # allow up to 10 more temporary ones
#             pool_recycle=1800,       # recycle every 30 minutes
#             pool_timeout=30,         # 30s timeout for waiting connections
#         )
#         return engine

#     def connect(self):
#         """Establish a pooled SQL connection if not already active."""
#         if self._db is None:
#             if self._engine is None:
#                 self._engine = self._create_engine()
#             self._db = SQLDatabase.from_uri(self._engine.url, schema="dbo")
#         return self._db

#     def close(self):
#         """Dispose of connection pool cleanly."""
#         if self._engine:
#             self._engine.dispose()
#             print(Fore.YELLOW + "Database connection pool closed." + Style.RESET_ALL)
#         self._engine = None
#         self._db = None

#     async def __aenter__(self):
#         """Async context entry."""
#         self.connect()
#         return self

#     async def __aexit__(self, exc_type, exc_val, exc_tb):
#         """Async context exit for auto-close."""
#         self.close()

#     # ----------------------------------------------------------------
#     # 🧩 PROMPT MANAGEMENT
#     # ----------------------------------------------------------------
#     def get_prompt_template(self) -> ChatPromptTemplate:
#         """Return a reusable ChatPromptTemplate for SQL generation."""
#         system_message = """
#         You are an expert SQL (PostgreSQL) query generator.

#         Given a question, create a syntactically correct {dialect} query.
#         - Use LIMIT {top_k} (never SELECT *).
#         - Use only the listed columns and tables.
#         - Never use T-SQL syntax (e.g., TOP, RETURNING unless needed).
#         - Only use valid PostgreSQL syntax.

#         Tables available:
#         {table_info}
#         """

#         user_prompt = "Question: {input}"
#         return ChatPromptTemplate([("system", system_message), ("user", user_prompt)])

#     # ----------------------------------------------------------------
#     # 🧩 QUERY GENERATION
#     # ----------------------------------------------------------------
#     def generate_query(self, question: str, llm: ChatOpenAI) -> str:
#         """Generate SQL query text using the LLM."""
#         db = self.connect()
#         prompt_template = self.get_prompt_template()
#         prompt = prompt_template.invoke(
#             {
#                 "dialect": db.dialect,
#                 "top_k": 10,
#                 "table_info": db.get_table_info(),
#                 "input": question
#             }
#         )
#         structured_llm = llm.with_structured_output(QueryOutput)
#         result = structured_llm.invoke(prompt)
#         return result.get("query")

#     # ----------------------------------------------------------------
#     # 🧩 QUERY EXECUTION
#     # ----------------------------------------------------------------
#     def execute_query(self, query: str):
#         """Execute a SQL query safely and return results."""
#         db = self.connect()
#         tool = QuerySQLDatabaseTool(db=db)

#         try:
#             result = tool.invoke(query)
#             if isinstance(result, str) and result.lower().startswith("error:"):
#                 raise Exception(result)
#             return result
#         except (OperationalError, SQLAlchemyError) as e:
#             print(Fore.RED + f"Database execution error: {e}" + Style.RESET_ALL)
#             self.close()
#             # Reconnect and retry once
#             self.connect()
#             result = tool.invoke(query)
#             return result

#     # ----------------------------------------------------------------
#     # 🧩 STREAMING INVOCATION
#     # ----------------------------------------------------------------
#     async def invoke_streaming(self, question: str, llm: ChatOpenAI):
#         """Generate SQL, execute it, and stream LLM-generated answers."""
#         attempt = 0
#         max_retries = 1
#         last_error = None

#         while attempt <= max_retries:
#             try:
#                 query = self.generate_query(question, llm)
#                 print(Fore.GREEN + f"Generated SQL:\n{query}" + Style.RESET_ALL)

#                 query_result = self.execute_query(query)
#                 print(Fore.CYAN + f"Query Result:\n{query_result}" + Style.RESET_ALL)

#                 # ✅ Generate final streamed answer
#                 answer_prompt = (
#                     "Given the question, SQL query, and its result, "
#                     "provide a natural language answer:\n\n"
#                     f"Question: {question}\nSQL: {query}\nResult: {query_result}"
#                 )

#                 async for token in llm.astream(answer_prompt):
#                     yield token.content
#                 return

#             except Exception as e:
#                 last_error = str(e)
#                 print(Fore.RED + f"Attempt {attempt + 1} failed: {last_error}" + Style.RESET_ALL)
#                 attempt += 1
#                 await asyncio.sleep(1)  # avoid hammering DB

#         # Fallback polite response
#         fallback = (
#             f"Sorry, I couldn't process your request after several attempts.\n"
#             f"Please rephrase your question or try again later."
#         )
#         async for token in llm.astream(fallback):
#             yield token.content
