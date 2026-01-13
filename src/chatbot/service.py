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
-- ============================================================
-- PostgreSQL Schema: public
-- ============================================================

-- Table: public.branches
-- Purpose: Stores branch master data.
-- Used when questions are about branch performance, customer distribution, or branch KPIs.

CREATE TABLE public.branches (
    branch_id BIGSERIAL NOT NULL,

    -- Unique short branch code.
    branch_code VARCHAR(20) NOT NULL UNIQUE,

    -- Name of the branch.
    branch_name VARCHAR(150) NOT NULL,

    -- Location fields for regional analytics.
    city VARCHAR(100),
    state VARCHAR(100),

    -- Created timestamp.
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_branches PRIMARY KEY (branch_id)
);

-- ============================================================

-- Table: public.customers
-- Purpose: Stores customer identity and onboarding information.
-- Used when questions are about people, customers, tenure, or segmentation.

CREATE TABLE public.customers (
    customer_id BIGSERIAL NOT NULL,

    -- Full name of customer.
    full_name VARCHAR(150) NOT NULL,

    -- Customer unique ID used internally (CIF).
    cif_number VARCHAR(30) NOT NULL UNIQUE,

    -- Contact details.
    mobile VARCHAR(20),
    email VARCHAR(200),

    -- Customer lifecycle status.
    status VARCHAR(30) NOT NULL DEFAULT 'Active',

    -- Onboarding date/time.
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_customers PRIMARY KEY (customer_id)
);

-- ============================================================

-- Table: public.accounts
-- Purpose: Represents bank accounts owned by customers.
-- Used when questions involve balances, account type segmentation, status, ownership.

CREATE TABLE public.accounts (
    account_id BIGSERIAL NOT NULL,

    -- Unique account number.
    account_number VARCHAR(30) NOT NULL UNIQUE,

    -- Owner customer.
    customer_id BIGINT NOT NULL,

    -- Branch in which account is maintained.
    branch_id BIGINT NOT NULL,

    -- Category: Savings, Current.
    account_type VARCHAR(50) NOT NULL,

    -- Current available balance.
    balance NUMERIC(18,2) NOT NULL DEFAULT 0,

    -- Active/Dormant/Closed.
    status VARCHAR(30) NOT NULL DEFAULT 'Active',

    -- Account opening date.
    opened_date DATE NOT NULL,

    CONSTRAINT pk_accounts PRIMARY KEY (account_id),

    CONSTRAINT fk_accounts_customer
        FOREIGN KEY (customer_id)
        REFERENCES public.customers (customer_id)
        ON DELETE NO ACTION,

    CONSTRAINT fk_accounts_branch
        FOREIGN KEY (branch_id)
        REFERENCES public.branches (branch_id)
        ON DELETE NO ACTION
);

CREATE INDEX idx_accounts_customer ON public.accounts(customer_id);
CREATE INDEX idx_accounts_branch ON public.accounts(branch_id);

-- ============================================================

-- Table: public.transactions
-- Purpose: Stores all money movement for accounts.
-- Used when questions are about statements, transfers, transaction KPIs, debit/credit.

CREATE TABLE public.transactions (
    transaction_id BIGSERIAL NOT NULL,

    -- Unique transaction reference number.
    txn_reference VARCHAR(50) NOT NULL UNIQUE,

    -- Account in which transaction happened.
    account_id BIGINT NOT NULL,

    -- Transaction type: Deposit, Withdrawal, Transfer.
    txn_type VARCHAR(30) NOT NULL,

    -- Direction: Credit adds money, Debit removes money.
    direction VARCHAR(10) NOT NULL CHECK (direction IN ('Credit','Debit')),

    -- Transaction amount.
    amount NUMERIC(18,2) NOT NULL CHECK (amount >= 0),

    -- Status: Success/Failed/Pending.
    status VARCHAR(30) NOT NULL DEFAULT 'Success',

    -- Channel: ATM, Branch, UPI, NEFT, RTGS, IMPS.
    channel VARCHAR(50),

    -- Note/remark.
    narration VARCHAR(250),

    -- Timestamp of transaction.
    transaction_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_transactions PRIMARY KEY (transaction_id),

    CONSTRAINT fk_transactions_account
        FOREIGN KEY (account_id)
        REFERENCES public.accounts (account_id)
        ON DELETE CASCADE
);

CREATE INDEX idx_txn_time ON public.transactions(transaction_time);
CREATE INDEX idx_txn_account ON public.transactions(account_id);

-- ============================================================

-- Table: public.loan_accounts
-- Purpose: Stores loans issued to customers.
-- Used when questions are about loan book, loan status, loan outstanding.

CREATE TABLE public.loan_accounts (
    loan_id BIGSERIAL NOT NULL,

    -- Loan belongs to this customer.
    customer_id BIGINT NOT NULL,

    -- Loan maintained in branch.
    branch_id BIGINT NOT NULL,

    -- Loan account number.
    loan_account_number VARCHAR(30) NOT NULL UNIQUE,

    -- Type: Home Loan / Personal Loan / Vehicle Loan.
    loan_type VARCHAR(50) NOT NULL,

    -- Loan sanctioned amount.
    principal_amount NUMERIC(18,2) NOT NULL,

    -- Interest rate (annual %).
    annual_interest_rate NUMERIC(5,2) NOT NULL,

    -- Tenure in months.
    tenure_months INT NOT NULL,

    -- Current outstanding balance.
    outstanding_amount NUMERIC(18,2) NOT NULL,

    -- Active/Closed/Defaulted.
    status VARCHAR(30) NOT NULL DEFAULT 'Active',

    -- Disbursement date.
    disbursed_date DATE NOT NULL,

    CONSTRAINT pk_loan_accounts PRIMARY KEY (loan_id),

    CONSTRAINT fk_loan_customer
        FOREIGN KEY (customer_id)
        REFERENCES public.customers (customer_id)
        ON DELETE NO ACTION,

    CONSTRAINT fk_loan_branch
        FOREIGN KEY (branch_id)
        REFERENCES public.branches (branch_id)
        ON DELETE NO ACTION
);

CREATE INDEX idx_loans_customer ON public.loan_accounts(customer_id);
CREATE INDEX idx_loans_branch ON public.loan_accounts(branch_id);

-- ============================================================

-- Table: public.loan_repayments
-- Purpose: Tracks EMI repayments for each loan.
-- Used when questions are about overdue EMI, monthly EMI collections, repayment trends.

CREATE TABLE public.loan_repayments (
    repayment_id BIGSERIAL NOT NULL,

    -- Loan reference.
    loan_id BIGINT NOT NULL,

    -- EMI due date.
    due_date DATE NOT NULL,

    -- EMI amount expected.
    emi_amount NUMERIC(18,2) NOT NULL,

    -- Amount paid.
    paid_amount NUMERIC(18,2) NOT NULL DEFAULT 0,

    -- Paid / Overdue / Pending.
    status VARCHAR(30) NOT NULL DEFAULT 'Pending',

    -- Payment date (if paid).
    paid_date DATE,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_loan_repayments PRIMARY KEY (repayment_id),

    CONSTRAINT fk_lr_loan
        FOREIGN KEY (loan_id)
        REFERENCES public.loan_accounts (loan_id)
        ON DELETE CASCADE
);

CREATE INDEX idx_lr_due_date ON public.loan_repayments(due_date);
CREATE INDEX idx_lr_status ON public.loan_repayments(status);


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



