from langgraph.graph import StateGraph, START, END
from langchain_core.messages import BaseMessage, HumanMessage
from typing import List, TypedDict, Annotated, Any
from teams.team_sql import SQLTeam
from teams.team_data import DataRequirementTeam
import operator
import functools

class CombinedTeamState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    chat_history: List[str]
    team_members: List[str]  # Ensuring team members are passed correctly
    data_team_members: List[str]
    sql_team_members: List[str]
    next: str
    data_requirements: List[str]  # Stores parameters collected by DataRequirementTeam
    generated_prompt: str    # Stores the prompt generated by data_prompt_generator
    sql_query: str
    execution_results: Any

class PostgreSQLChain:
    def __init__(self, model):
        # Create instances of both teams
        self.sql_team = SQLTeam(model=model)
        self.data_team = DataRequirementTeam(model=model)
        self.graph = StateGraph(CombinedTeamState)  # Initialize the StateGraph with combined state

        # List of team members for supervisor agents
        self.data_team_members = [
            "data_gather_information",
            "data_prompt_generator"
        ]
        self.sql_team_members = [
            "sql_generation",
            "sql_execution",
            "sql_result_formatting"
        ]
        self.team_members = self.data_team_members + self.sql_team_members
        self.generated_prompt = ""

    def build_graph(self):
        """Build the combined data requirement and SQL execution graph."""

        # Add nodes for DataRequirementTeam agents
        self.graph.add_node("data_gather_information", self.data_team.data_gather_information())
        self.graph.add_node("data_prompt_generator", self.data_team.data_prompt_generator())
        self.graph.add_node("data_gather_supervisor", self.data_team.data_gather_supervisor(self.data_team_members))
        self.graph.add_node("data_prompt_supervisor", self.data_team.data_prompt_supervisor(self.team_members))

        # Add nodes for SQLTeam agents
        self.graph.add_node("sql_generation", self.sql_team.sql_generation_agent())
        self.graph.add_node("sql_execution", self.sql_team.sql_execution_agent())
        self.graph.add_node("sql_result_formatting", self.sql_team.sql_result_formatting_agent())
        self.graph.add_node("sql_supervisor", self.sql_team.sql_supervisor(self.sql_team_members))

        ######### DATA REQUIREMENT TEAM #########
        ######### Data Gathering workflow
        # Add conditional edges for dynamic routing
        self.graph.add_conditional_edges(
            "data_gather_supervisor",
            lambda x: x["next"],
            {
                "FINISH": END,
                "data_gather_information": "data_gather_information",
                "data_prompt_generator": "data_prompt_generator"
            }
        )
        
        self.graph.add_edge(START, "data_gather_information")
        self.graph.add_edge("data_gather_information", "data_gather_supervisor")

        ######### Data Prompt Generation workflow
        # Add conditional edges for dynamic routing
        self.graph.add_conditional_edges(
            "data_prompt_supervisor",
            lambda x: x["next"],
            {
                "data_prompt_generator": "data_prompt_generator",
                "sql_generation": "sql_generation"
            }
        )
        self.graph.add_edge("data_prompt_generator", "data_prompt_supervisor")

        ######### SQL TEAM #########
        # SQLTeam workflow
        self.graph.add_edge("sql_generation", "sql_execution")
        self.graph.add_edge("sql_execution", "sql_result_formatting")
        self.graph.add_edge("sql_result_formatting", "sql_supervisor")
        self.graph.add_edge("sql_supervisor", END)

    def compile_chain(self):
        """Compile the combined chain from the constructed graph."""
        return self.graph.compile()

    def enter_chain(self, message: str, chain, conversation_history: List[str]):
        """Enter the compiled chain with the user's message and the chat history, and return the final summary."""
        # Initialize messages with the user's input
        results = [HumanMessage(content=message)]
        
        input_data = {
            "messages": results,
            "chat_history": conversation_history,
            "team_members": self.team_members,
            "agent_scratchpad": "",
            "intermediate_steps": [],
            "data_requirements": {},
            "generated_prompt": "",
            "sql_query": "",
            "execution_results": None,
            "next": None
        }

        # Execute the chain by invoking it with the input data
        chain_result = chain.invoke(input_data)

        if "messages" in chain_result and chain_result["messages"]:
            # Extract the final output from the messages
            final_output = chain_result["messages"][-1].content
        else:
            final_output = "No valid messages returned from the chain."

        return final_output
