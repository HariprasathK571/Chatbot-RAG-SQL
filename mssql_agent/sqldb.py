from langchain_community.utilities.sql_database import SQLDatabase
from typing_extensions import TypedDict,Annotated
from langchain_community.tools.sql_database.tool import QuerySQLDatabaseTool
from langchain_core.prompts import ChatPromptTemplate
from colorama import Fore, Style, init
init(autoreset=True)  # ensures colors reset after each print
import asyncio
import re


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
    
    # def clean_schema(self,raw_schema):
    # # Remove block comments (/* ... */)
    #     return re.sub(r"/\*.*?\*/", "", raw_schema, flags=re.DOTALL).strip()
    

    def write_query(self,question,llm):
        """Generate SQL query to fetch information."""
        query_prompt_template = self.promptemp()
        # cleanschema=self.clean_schema(self.db.get_table_info())
        prompt = query_prompt_template.invoke(
            {
                "dialect": self.db.dialect,
                "top_k": 10,
                "table_info": self.db.get_table_info(),
                "input": question
            }
        )
        # print(prompt)
        structured_llm = llm.with_structured_output(QueryOutput)
        result = structured_llm.invoke(prompt)
        return result
    
    def execute_query(self,query):
        """Execute SQL query."""
        execute_query_tool = QuerySQLDatabaseTool(db= self.db)
        sqlresult =  execute_query_tool.invoke(query)

        if isinstance(sqlresult, str) and sqlresult.lower().startswith("error:"):
            raise Exception(sqlresult)
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

    # async def invoke_streaming(self, question, llm, token_callback):
    #     attempt = 0
    #     querygenbyllm = None  # initialize
    #     max_retries = 2


    #     while attempt <= max_retries:
    #         try:
    #             if attempt == 0:
    #                 querygenbyllm = self.write_query(question, llm)
    #                 querygenbyllm = {"query":"usuffsdf"}
    #             else:
    #                 feedback_prompt = (
    #                     f"The previously generated SQL query failed:\n{querygenbyllm}\n"
    #                     f"Error message: {last_error}\n"
    #                     f"Tables/columns allowed: {self.db.get_table_info()}\n"
    #                     f"Please generate a corrected SQL query for the same user question:\n{question}"
    #                 )
    #                 structured_llm = llm.with_structured_output(QueryOutput)
    #                 querygenbyllm = structured_llm.invoke(feedback_prompt)

    #             sql_text = querygenbyllm["query"] if isinstance(querygenbyllm, dict) else str(querygenbyllm)
    #             print(Fore.GREEN + f'Generated SQL:\n"{sql_text}"' + Style.RESET_ALL)
    #             query_values = self.execute_query(querygenbyllm)
    #             print(Fore.RED + f'Generated values:\n"{query_values}"' + Style.RESET_ALL)


    #             answer_prompt = (
    #         "Given the following user question, corresponding SQL query, "
    #         "and SQL result, answer the user question.\n\n"
    #         f"Question: {question}\n"
    #         f"SQL Query: {querygenbyllm}\n"
    #         f"SQL Result: {query_values}"
    #     )
    #             for token in llm.stream(answer_prompt):
    #                 token_callback(token)
    #                 await asyncio.sleep(0)

    #             token_callback(None)  # end of stream
    #             return


    #         except Exception as e:
    #             last_error = str(e)  # save error for feedback
    #             print(Fore.RED + f'Attempt {attempt+1} failed with error:\n"{last_error}"' + Style.RESET_ALL)

    #             if attempt == max_retries:
    #             # Instead of exposing DB error, generate a general answer
    #                 fallback_prompt = (
    #                     f"The user asked: {question}\n"
    #                     f"However, the system could not retrieve an answer from the database "
    #                     f"after {max_retries} attempts.\n"
    #                     "Please provide a polite, general response that acknowledges the failure "
    #                     "without exposing technical details, and suggest the user try rephrasing."
    #                 )
    #                 for token in llm.stream(fallback_prompt):
    #                     token_callback(token)
    #                     await asyncio.sleep(0)
    #                 token_callback(None)
    #                 return
    #             attempt += 1


    async def invoke_streaming(self, question, llm, token_callback):

        attempt = 0
        querygenbyllm = None  # initialize
        max_retries = 1

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
                        f"Tables/columns allowed: {self.db.get_table_info()}\n"
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
                        for token in llm.stream(fallback_prompt):
                            token_callback(token)
                            await asyncio.sleep(0)
                        token_callback(None)
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
                for token in llm.stream(answer_prompt):
                    token_callback(token)
                    await asyncio.sleep(0)

                token_callback(None)  # end of stream
                return

            except Exception as e:
                # Catch unexpected errors in query generation
                last_error = str(e)
                print(Fore.RED + f'Attempt {attempt+1} failed with error:\n"{last_error}"' + Style.RESET_ALL)
                attempt += 1
                 


