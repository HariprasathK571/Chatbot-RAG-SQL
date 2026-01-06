import logging
from typing_extensions import TypedDict, Annotated
from colorama import Fore, Style, init
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from sqlalchemy import text, inspect
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel.ext.asyncio.session import AsyncSession
from src.db.core import async_engine, sync_url# ✅ shared async engine + session
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
    async def export_schema_with_samples(self, sample_limit=2):
        """
        Return formatted schema with table definitions and sample rows (async).
        """
        inspector = inspect(sync_url)
        output = []

        async with async_engine.connect() as conn:
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
                        result = await conn.execute(text(f"SELECT TOP {sample_limit} * FROM {schema}.[{table_name}]"))
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
    async def schema(self):
        """Return cached schema (generate once)."""
        if self._schema is None:
            self._schema = """
-- Table: public.customers
-- Purpose: Stores individuals who are customers of the bank.
-- Used when questions are about people, users, customer identity, or ownership.

CREATE TABLE public.customers (
    customer_id BIGSERIAL NOT NULL,

    -- Human-readable full name of the customer.
    -- Use when output requires identifying the person.
    full_name VARCHAR(150) NOT NULL,

    -- Contact email address.
    -- Informational only; should not be used for analytics.
    email VARCHAR(200),

    -- Timestamp when the customer joined the bank.
    -- Used for tenure or longevity-based questions.
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_customers PRIMARY KEY (customer_id)
);

-- Table: public.accounts
-- Purpose: Represents bank accounts owned by customers.
-- Used when questions involve balances, account status, or account ownership.

CREATE TABLE public.accounts (
    account_id BIGSERIAL NOT NULL,

    -- Identifies the owner of the account.
    -- Used to associate accounts with a customer.
    customer_id BIGINT NOT NULL,

    -- Category of the account (Savings, Current).
    -- Used for segmentation and eligibility logic.
    account_type VARCHAR(50) NOT NULL,

    -- Current available balance in the account.
    -- Represents present state only; do not use for historical analysis.
    balance NUMERIC(18,2) NOT NULL,

    -- Lifecycle state of the account (Active, Dormant, Closed).
    -- Used to filter usable or valid accounts.
    status VARCHAR(30) NOT NULL,

    -- Date when the account was opened.
    -- Used for account age or longevity analysis.
    opened_date DATE NOT NULL,

    CONSTRAINT pk_accounts PRIMARY KEY (account_id),

    CONSTRAINT fk_accounts_customer
        FOREIGN KEY (customer_id)
        REFERENCES public.customers (customer_id)
        ON DELETE NO ACTION
);

-- Table: public.transactions
-- Purpose: Stores all monetary inflow and outflow activity.
-- Used for spending analysis, income tracking, and transaction history.

CREATE TABLE public.transactions (
    transaction_id BIGSERIAL NOT NULL,

    -- Account on which the transaction occurred.
    -- Used to associate financial activity with customers.
    account_id BIGINT NOT NULL,

    -- Date and time when the transaction occurred.
    -- Primary column for time-based queries (recent, monthly, yearly).
    transaction_date TIMESTAMP NOT NULL,

    -- Monetary value of the transaction.
    -- Negative value indicates money leaving the account.
    -- Positive value indicates money entering the account.
    amount NUMERIC(18,2) NOT NULL,

    -- Business classification of the transaction.
    -- Debit = spending, Credit = income.
    transaction_type VARCHAR(20) NOT NULL,

    -- Merchant or source associated with the transaction.
    -- Used for merchant-wise spending analysis.
    merchant_name VARCHAR(150),

    -- Execution result of the transaction (Success, Failed, Pending).
    -- Used for reliability, error detection, and risk monitoring.
    transaction_status VARCHAR(30) NOT NULL,

    CONSTRAINT pk_transactions PRIMARY KEY (transaction_id),

    CONSTRAINT fk_transactions_account
        FOREIGN KEY (account_id)
        REFERENCES public.accounts (account_id)
        ON DELETE NO ACTION
);

-- Table: public.transfers
-- Purpose: Records internal fund movements between accounts.
-- Used when money moves inside the bank rather than via merchants.

CREATE TABLE public.transfers (
    transfer_id BIGSERIAL NOT NULL,

    -- Source account from which money was sent.
    -- Represents outflow of funds.
    from_account_id BIGINT NOT NULL,

    -- Destination account that received money.
    -- Represents inflow of funds.
    to_account_id BIGINT NOT NULL,

    -- Amount of money transferred between accounts.
    -- Always a positive value.
    transfer_amount NUMERIC(18,2) NOT NULL,

    -- Date and time when the transfer occurred.
    -- Used for time-based transfer analysis.
    transfer_date TIMESTAMP NOT NULL,

    -- Current state of the transfer (Completed, Pending, Failed).
    -- Used for operational monitoring.
    transfer_status VARCHAR(30) NOT NULL,

    CONSTRAINT pk_transfers PRIMARY KEY (transfer_id),

    CONSTRAINT fk_transfers_from_account
        FOREIGN KEY (from_account_id)
        REFERENCES public.accounts (account_id)
        ON DELETE NO ACTION,

    CONSTRAINT fk_transfers_to_account
        FOREIGN KEY (to_account_id)
        REFERENCES public.accounts (account_id)
        ON DELETE NO ACTION
);

"""
        return self._schema

    # ----------------------------------------------------------------
    # 🧩 PROMPT TEMPLATE
    # ----------------------------------------------------------------
    def promptemp(self):
        system_message = """You are an expert SQL (PostgreSQL) query generator.

        Given an input question, create a syntactically correct {dialect} query to
        run to help find the answer. Unless the user specifies in his question a
        specific number of examples they wish to obtain, always limit your query to
        at most {top_k} results. You can order the results by a relevant column to
        return the most interesting examples in the database.

        Never query for all the columns from a specific table, only ask for a few
        relevant columns given the question.

        Pay attention to use only the column names that you can see in the schema
        description. Be careful to not query for columns that do not exist. Also,
        pay attention to which column is in which table.

        Rules:
        - Always generate PostgreSQL queries.
        - Use `LIMIT {top_k}` to restrict the number of rows.
        - Do not use `TOP`, `RETURNING` (unless needed for INSERT), or any T-SQL-specific clauses.
        - Only use the columns and tables listed in the schema.
        - Never select all columns (*), only the required ones.
        - Ensure syntax is valid for PostgreSQL.

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
        DB_schema = await self.schema
        query_prompt_template = self.promptemp()

        prompt = query_prompt_template.invoke(
            {
                "dialect": "postgres",
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
    async def execute_query(self, session: AsyncSession, query):
        """Execute a raw SQL query asynchronously using SQLModel AsyncSession."""
        try:
            result = await session.exec(text(query))
            rows = result.all()
            return [dict(row._mapping) for row in rows]
        except SQLAlchemyError as e:
            raise Exception(f"Database error: {e}")
        
    # 🧩 MAIN STREAMING LOGIC
    # ----------------------------------------------------------------
    async def invoke_streaming(self, question, llm: ChatOpenAI,session: AsyncSession):
        """Generate query, execute asynchronously, and stream LLM answer."""
        attempt = 0
        max_retries = 1
        last_error = None
        querygenbyllm = None

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
                    query_values = await self.execute_query(session, sql_text)
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



