import logging
from typing_extensions import TypedDict, Annotated
from colorama import Fore, Style, init
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from sqlalchemy import text, inspect
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
# from sqlmodel.ext.asyncio.session import AsyncSession
from src.db.core import engine # ✅ shared async engine + session
# import asyncio
#get_session 
init(autoreset=True)


class QueryOutput(TypedDict):
    """Generated SQL query."""
    query: Annotated[str, ..., "Syntactically valid SQL query."]


class MSSQLConnector:
    """Async MSSQL connector integrated with project-wide async engine (no SQLDatabase)."""

    def __init__(self):
        self._schema = None

    # ----------------------------------------------------------------
    # 🧩 SCHEMA EXPORT
    # ----------------------------------------------------------------
    def export_schema_with_samples(self, sample_limit=2):
        """
        Return formatted schema with table definitions and sample rows (async).
        """
        inspector = inspect(engine)
        output = []

        with engine.connect() as conn:
            for schema in inspector.get_schema_names():
                output.append(f"-- Schema: {schema}")

                for table_name in inspector.get_table_names(schema=schema):
                    output.append(f"\n-- Table: {schema}.{table_name}")

                    # 1️⃣ Columns
                    columns = inspector.get_columns(table_name, schema=schema)
                    ddl = f"CREATE TABLE {schema}.[{table_name}] (\n"
                    column_defs = []

                    for col in columns:
                        col_def = f"    [{col['name']}] {col['type']}"
                        if not col.get("nullable", True):
                            col_def += " NOT NULL"
                        column_defs.append(col_def)

                    # 2️⃣ Primary Key
                    pk_constraint = inspector.get_pk_constraint(table_name, schema=schema)
                    if pk_constraint and pk_constraint.get("constrained_columns"):
                        pk_cols = ", ".join(f"[{col}]" for col in pk_constraint["constrained_columns"])
                        pk_name = pk_constraint.get("name", f"PK_{table_name}")
                        column_defs.append(f"    CONSTRAINT [{pk_name}] PRIMARY KEY CLUSTERED ({pk_cols})")

                    # 3️⃣ Foreign Keys
                    fks = inspector.get_foreign_keys(table_name, schema=schema)
                    for fk in fks:
                        fk_cols = ", ".join(f"[{col}]" for col in fk["constrained_columns"])
                        ref_schema = fk.get("referred_schema", schema)
                        ref_table = fk["referred_table"]
                        ref_cols = ", ".join(f"[{col}]" for col in fk["referred_columns"])
                        fk_name = fk.get("name", f"FK_{table_name}_{ref_table}_{'_'.join(fk['constrained_columns'])}")
                        ondelete = f" ON DELETE {fk.get('options', {}).get('ondelete', 'NO ACTION')}"
                        column_defs.append(
                            f"    CONSTRAINT [{fk_name}] FOREIGN KEY({fk_cols}) REFERENCES {ref_schema}.[{ref_table}] ({ref_cols}){ondelete}"
                        )

                    ddl += ",\n".join(column_defs) + "\n);"
                    output.append(ddl)

                    # 4️⃣ Sample Rows
                    try:
                        result = conn.execute(text(f"SELECT TOP {sample_limit} * FROM {schema}.[{table_name}]"))
                        rows = result.fetchall()
                        if rows:
                            cols = result.keys()
                            output.append(f"\n/*\n{len(rows)} rows from {table_name} table:")
                            output.append("\t".join(cols))
                            for row in rows:
                                output.append("\t".join(str(x) if x is not None else "NULL" for x in row))
                            output.append("*/\n")
                    except Exception as e:
                        output.append(f"/* Could not fetch rows: {e} */\n")

        return "\n".join(output)

    @property
    def schema(self):
        """Return cached schema (generate once)."""
        if self._schema is None:
            self._schema = self.export_schema_with_samples()
        return self._schema

    # ----------------------------------------------------------------
    # 🧩 PROMPT TEMPLATE
    # ----------------------------------------------------------------
    def promptemp(self):
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

        return ChatPromptTemplate(
            [("system", system_message), ("user", user_prompt)]
        )

    # ----------------------------------------------------------------
    # 🧩 QUERY GENERATION
    # ----------------------------------------------------------------
    async def write_query(self, question, llm: ChatOpenAI):
        """Generate SQL query using LLM and live schema."""
        DB_schema = self.schema
        query_prompt_template = self.promptemp()

        prompt = query_prompt_template.invoke(
            {
                "dialect": "MSSQL",
                "top_k": 10,
                "table_info": DB_schema,
                "input": question,
            }
        )
        structured_llm = llm.with_structured_output(QueryOutput)
        result = structured_llm.invoke(prompt)
        print(prompt)
        return result

    # ----------------------------------------------------------------
    # 🧩 QUERY EXECUTION (Async)
    # ----------------------------------------------------------------
    # async def execute_query(self, db :Session, query):
    #     """Execute a raw SQL query asynchronously using SQLModel AsyncSession."""
    #     try:
    #         result = await db.exec(text(query))
    #         rows = result.all()
    #         return [dict(row._mapping) for row in rows]
    #     except SQLAlchemyError as e:
    #         raise Exception(f"Database error: {e}")
        
    async def execute_query(self, db: Session, query: str):
        """Execute a raw SQL query synchronously using SQLAlchemy Session."""
        try:
            result = db.execute(text(query))
            rows = result.fetchall()
            return [dict(row._mapping) for row in rows]
        except SQLAlchemyError as e:
            raise Exception(f"Database error: {e}")

        
    # 🧩 MAIN STREAMING LOGIC
    # ----------------------------------------------------------------
    async def invoke_streaming(self, question, llm: ChatOpenAI,db: Session):
        """Generate query, execute asynchronously, and stream LLM answer."""
        attempt = 0
        max_retries = 1
        last_error = None

        while attempt <= max_retries:
            try:
                if attempt == 0:
                    querygenbyllm = await self.write_query(question, llm)
                    # querygenbyllm = {"query":"usuffsdf"}
                else:
                    # regenerate query based on last error
                    feedback_prompt = (
                        f"The previously generated SQL query failed:\n{querygenbyllm}\n"
                        f"Error message: {last_error}\n"
                        f"Tables/columns allowed: {self.schema}\n"
                        f"Please generate a corrected MS-SQL query for the same user question:\n{question}"
                    )
                    structured_llm = llm.with_structured_output(QueryOutput)
                    querygenbyllm = structured_llm.invoke(feedback_prompt)
                    # querygenbyllm = {"query":"usuffsdf"}

                sql_text = querygenbyllm["query"] if isinstance(querygenbyllm, dict) else str(querygenbyllm)
                print(Fore.GREEN + f'Generated SQL:\n"{sql_text}"' + Style.RESET_ALL)


                # Execute SQL
                try:
                    query_values = await self.execute_query(db, sql_text)
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



