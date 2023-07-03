from typing import Any, List, Optional

from langchain import LLMChain
from langchain.agents import (
    AgentExecutor,
    Tool,
    ZeroShotAgent,
    initialize_agent,
    AgentType,
)
from langchain.experimental import AutoGPT
from langchain.agents.agent_toolkits import (
    SQLDatabaseToolkit,
    VectorStoreInfo,
    VectorStoreRouterToolkit,
    VectorStoreToolkit,
)
from langchain.agents.agent_toolkits.json.prompt import JSON_PREFIX, JSON_SUFFIX
from langchain.agents.agent_toolkits.json.toolkit import JsonToolkit
from langchain.agents.agent_toolkits.pandas.prompt import PREFIX as PANDAS_PREFIX
from langchain.agents.agent_toolkits.pandas.prompt import (
    SUFFIX_WITH_DF as PANDAS_SUFFIX,
)
from langchain.agents.agent_toolkits.sql.prompt import SQL_PREFIX, SQL_SUFFIX
from langchain.agents.agent_toolkits.vectorstore.prompt import (
    PREFIX as VECTORSTORE_PREFIX,
)
from langchain.agents.agent_toolkits.vectorstore.prompt import (
    ROUTER_PREFIX as VECTORSTORE_ROUTER_PREFIX,
)
from langchain.agents.mrkl.prompt import FORMAT_INSTRUCTIONS
from langchain.base_language import BaseLanguageModel
from langchain.memory.chat_memory import BaseChatMemory
from langchain.sql_database import SQLDatabase
from langchain.tools.python.tool import PythonAstREPLTool
from langchain.tools.sql_database.prompt import QUERY_CHECKER
from langflow.interface.base import CustomAgentExecutor

from langchain.callbacks.manager import (
    Callbacks
)
from typing import Any, Dict, List, Optional, Union


class JsonAgent(CustomAgentExecutor):
    """Json agent"""

    @staticmethod
    def function_name():
        return "JsonAgent"

    @classmethod
    def initialize(cls, *args, **kwargs):
        return cls.from_toolkit_and_llm(*args, **kwargs)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @classmethod
    def from_toolkit_and_llm(cls, toolkit: JsonToolkit, llm: BaseLanguageModel):
        tools = toolkit if isinstance(toolkit, list) else toolkit.get_tools()
        tool_names = {tool.name for tool in tools}
        prompt = ZeroShotAgent.create_prompt(
            tools,
            prefix=JSON_PREFIX,
            suffix=JSON_SUFFIX,
            format_instructions=FORMAT_INSTRUCTIONS,
            input_variables=None,
        )
        llm_chain = LLMChain(
            llm=llm,
            prompt=prompt,
        )
        agent = ZeroShotAgent(
            llm_chain=llm_chain, allowed_tools=tool_names  # type: ignore
        )
        return cls.from_agent_and_tools(agent=agent, tools=tools, verbose=True)

    def run(self, *args, **kwargs):
        return super().run(*args, **kwargs)


class CSVAgent(CustomAgentExecutor):
    """CSV agent"""

    @staticmethod
    def function_name():
        return "CSVAgent"

    @classmethod
    def initialize(cls, *args, **kwargs):
        return cls.from_toolkit_and_llm(*args, **kwargs)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @classmethod
    def from_toolkit_and_llm(
        cls,
        path: str,
        llm: BaseLanguageModel,
        pandas_kwargs: Optional[dict] = None,
        **kwargs: Any
    ):
        import pandas as pd  # type: ignore

        _kwargs = pandas_kwargs or {}
        df = pd.read_csv(path, **_kwargs)

        tools = [PythonAstREPLTool(locals={"df": df})]  # type: ignore
        prompt = ZeroShotAgent.create_prompt(
            tools,
            prefix=PANDAS_PREFIX,
            suffix=PANDAS_SUFFIX,
            input_variables=["df", "input", "agent_scratchpad"],
        )
        partial_prompt = prompt.partial(df=str(df.head()))
        llm_chain = LLMChain(
            llm=llm,
            prompt=partial_prompt,
        )
        tool_names = {tool.name for tool in tools}
        agent = ZeroShotAgent(
            llm_chain=llm_chain, allowed_tools=tool_names, **kwargs  # type: ignore
        )

        return cls.from_agent_and_tools(agent=agent, tools=tools, verbose=True)

    def run(self, *args, **kwargs):
        return super().run(*args, **kwargs)


class VectorStoreAgent(CustomAgentExecutor):
    """Vector store agent"""

    @staticmethod
    def function_name():
        return "VectorStoreAgent"

    @classmethod
    def initialize(cls, *args, **kwargs):
        return cls.from_toolkit_and_llm(*args, **kwargs)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @classmethod
    def from_toolkit_and_llm(
        cls, llm: BaseLanguageModel, vectorstoreinfo: VectorStoreInfo, **kwargs: Any
    ):
        """Construct a vectorstore agent from an LLM and tools."""

        toolkit = VectorStoreToolkit(vectorstore_info=vectorstoreinfo, llm=llm)

        tools = toolkit.get_tools()
        prompt = ZeroShotAgent.create_prompt(tools, prefix=VECTORSTORE_PREFIX)
        llm_chain = LLMChain(
            llm=llm,
            prompt=prompt,
        )
        tool_names = {tool.name for tool in tools}
        agent = ZeroShotAgent(
            llm_chain=llm_chain, allowed_tools=tool_names, **kwargs  # type: ignore
        )
        return AgentExecutor.from_agent_and_tools(
            agent=agent, tools=tools, verbose=True, handle_parsing_errors=True
        )

    def run(self, *args, **kwargs):
        return super().run(*args, **kwargs)


class SQLAgent(CustomAgentExecutor):
    """SQL agent"""

    @staticmethod
    def function_name():
        return "SQLAgent"

    @classmethod
    def initialize(cls, *args, **kwargs):
        return cls.from_toolkit_and_llm(*args, **kwargs)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @classmethod
    def from_toolkit_and_llm(
        cls, llm: BaseLanguageModel, database_uri: str, **kwargs: Any
    ):
        """Construct an SQL agent from an LLM and tools."""
        db = SQLDatabase.from_uri(database_uri)
        toolkit = SQLDatabaseToolkit(db=db, llm=llm)

        # The right code should be this, but there is a problem with tools = toolkit.get_tools()
        # related to `OPENAI_API_KEY`
        # return create_sql_agent(llm=llm, toolkit=toolkit, verbose=True)
        from langchain.prompts import PromptTemplate
        from langchain.tools.sql_database.tool import (
            InfoSQLDatabaseTool,
            ListSQLDatabaseTool,
            QuerySQLCheckerTool,
            QuerySQLDataBaseTool,
        )

        llmchain = LLMChain(
            llm=llm,
            prompt=PromptTemplate(
                template=QUERY_CHECKER, input_variables=["query", "dialect"]
            ),
        )

        tools = [
            QuerySQLDataBaseTool(db=db),  # type: ignore
            InfoSQLDatabaseTool(db=db),  # type: ignore
            ListSQLDatabaseTool(db=db),  # type: ignore
            QuerySQLCheckerTool(db=db, llm_chain=llmchain, llm=llm),  # type: ignore
        ]

        prefix = SQL_PREFIX.format(dialect=toolkit.dialect, top_k=10)
        prompt = ZeroShotAgent.create_prompt(
            tools=tools,  # type: ignore
            prefix=prefix,
            suffix=SQL_SUFFIX,
            format_instructions=FORMAT_INSTRUCTIONS,
        )
        llm_chain = LLMChain(
            llm=llm,
            prompt=prompt,
        )
        tool_names = {tool.name for tool in tools}  # type: ignore
        agent = ZeroShotAgent(
            llm_chain=llm_chain, allowed_tools=tool_names, **kwargs  # type: ignore
        )
        return AgentExecutor.from_agent_and_tools(
            agent=agent,
            tools=tools,  # type: ignore
            verbose=True,
            max_iterations=15,
            early_stopping_method="force",
            handle_parsing_errors=True,
        )

    def run(self, *args, **kwargs):
        return super().run(*args, **kwargs)


class VectorStoreRouterAgent(CustomAgentExecutor):
    """Vector Store Router Agent"""

    @staticmethod
    def function_name():
        return "VectorStoreRouterAgent"

    @classmethod
    def initialize(cls, *args, **kwargs):
        return cls.from_toolkit_and_llm(*args, **kwargs)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @classmethod
    def from_toolkit_and_llm(
        cls,
        llm: BaseLanguageModel,
        vectorstoreroutertoolkit: VectorStoreRouterToolkit,
        **kwargs: Any
    ):
        """Construct a vector store router agent from an LLM and tools."""

        tools = (
            vectorstoreroutertoolkit
            if isinstance(vectorstoreroutertoolkit, list)
            else vectorstoreroutertoolkit.get_tools()
        )
        prompt = ZeroShotAgent.create_prompt(tools, prefix=VECTORSTORE_ROUTER_PREFIX)
        llm_chain = LLMChain(
            llm=llm,
            prompt=prompt,
        )
        tool_names = {tool.name for tool in tools}
        agent = ZeroShotAgent(
            llm_chain=llm_chain, allowed_tools=tool_names, **kwargs  # type: ignore
        )
        return AgentExecutor.from_agent_and_tools(
            agent=agent, tools=tools, verbose=True, handle_parsing_errors=True
        )

    def run(self, *args, **kwargs):
        return super().run(*args, **kwargs)


class InitializeAgent(CustomAgentExecutor):
    """Implementation of AgentInitializer function"""

    @staticmethod
    def function_name():
        return "AgentInitializer"

    @classmethod
    def initialize(
        cls,
        llm: BaseLanguageModel,
        tools: List[Tool],
        agent: str,
        memory: Optional[BaseChatMemory] = None,
    ):
        # Find which value in the AgentType enum corresponds to the string
        # passed in as agent
        agent = AgentType(agent)
        return initialize_agent(
            tools=tools,
            llm=llm,
            # LangChain now uses Enum for agent, but we still support string
            agent=agent,  # type: ignore
            memory=memory,
            return_intermediate_steps=True,
            handle_parsing_errors=True,
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def run(self, *args, **kwargs):
        return super().run(*args, **kwargs)


class AutoGPTAgent(CustomAgentExecutor):
    """AutoGPT Agent"""

    @staticmethod
    def function_name():
        return "AutoGPTAgent"

    @classmethod
    def initialize(
        cls,
        ai_name: str,
        ai_role: str,
        llm: BaseLanguageModel,
        tools: List[Tool],
        # max_loop: int = 5,
        memory: Optional[BaseChatMemory] = None,
    ):
        agent = AutoGPT.from_llm_and_tools(
            ai_name=ai_name,
            ai_role=ai_role,
            tools=tools,
            llm=llm,
            memory=memory,
            # max_iterations=max_loop,
            # return_intermediate_steps=True,
        )
        agent.acall = cls._acall
        # @FIX What should keys refer to?
        agent.output_keys = ["fred"]
        # agent.output_keys = [{"log": "fred"}]

        return agent

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def run(self, *args, **kwargs):
        print("AutoGPT.run()")
        # print(args)
        # print(kwargs)
        return super().run(*args, **kwargs)

    async def _acall(self,
        chat_input: str,
        callbacks: Callbacks = None,
    ):
        print('AutoGPT._acall()')
        print(chat_input)  # False
        print(callbacks)            # [langflow.api.v1.callback.AsyncStreamingLLMCallbackHandler]
        # AutoGPT has no attribute output_keys
        # @TODO What should acall() return? A promise of something.
        return {
            "intermediate_steps": [
                {
                    "index": 1,
                    "result": "fake data"
                }
            ]
        }


CUSTOM_AGENTS = {
    "JsonAgent": JsonAgent,
    "CSVAgent": CSVAgent,
    "AgentInitializer": InitializeAgent,
    "VectorStoreAgent": VectorStoreAgent,
    "VectorStoreRouterAgent": VectorStoreRouterAgent,
    "SQLAgent": SQLAgent,
    "AutoGPTAgent": AutoGPTAgent,
}
