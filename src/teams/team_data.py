import functools
from typing import List, TypedDict, Annotated
from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI
from utilities.helper import HelperUtilities
from tools.tool_empty import placeholder_tool
from tools.tool_metadata import fetch_metadata_as_json
import operator

class TeamDataRequirement:
    def __init__(self, model):
        self.llm = ChatOpenAI(model=model)
        self.utilities = HelperUtilities()
        self.tools = {
            'placeholder': placeholder_tool,
            'metadata': fetch_metadata_as_json
        }

    def data_gather_information(self):
        """Creates an agent that captures the user's expectations for the data and stores it."""
        system_prompt_template = (
            """
            Your job is to collect the user's data requirements and expectations to create a prompt template.
            Use the function 'fetch_metadata_as_json' to gather metadata about the database.
            Store the metadata in the 'metadata' list of dictionary, List[dict] for future reference.
            Below is an example of a metadata structure:
            {{
            [
                {
                    "schema_name": "public",
                    "table_name": "employees",
                    "column_name": "employee_id",
                    "data_type": "integer",
                    "column_description": "Unique identifier for employees",
                    "constraint_name": "employees_pkey",
                    "constraint_type": "PRIMARY KEY"
                },
                {
                    "schema_name": "public",
                    "table_name": "employees",
                    "column_name": "first_name",
                    "data_type": "text",
                    "column_description": "First name of the employee",
                    "constraint_name": None,
                    "constraint_type": None
                }
            ]
            }}

            Here is the chat history, use it to gather the data requirements:
            {chat_history}

            You should gather the following information:

            1. **Purpose of the Data**: Understand why the user needs the data. What decision or analysis will it support?
            2. **Specific Data Needs**: Identify which specific data points the user is interested in (e.g., sales figures, customer demographics).
            3. **Time Frame**: Determine if there is a specific time frame the user is interested in (e.g., last month, Q1 2024).
            4. **Filters/Criteria**: Ask for any specific conditions that should be applied to the data (e.g., region, product category).

            Engage with the user to collect all necessary information. If any information is missing or unclear, ask the user for clarification.

            **Once all information is collected**, output the collected information as a dictionary in 'data_requirements' with the following structure:

            {{
                "purpose_of_data": "user's response",
                "specific_data_needs": "user's response",
                "time_frame": "user's response",
                "filters_criteria": "user's response"
            }}

            **Do not include any code fences or extra text; output only the JSON object.**
            """
        )

        data_gather_information_agent = self.utilities.create_agent(
            self.llm,
            [self.tools['metadata']],
            system_prompt_template
        )
        return functools.partial(
            self.utilities.agent_node,
            agent=data_gather_information_agent,
            name="data_gather_information"
        )

    def data_gather_supervisor(self, members: List[str]):
        """Creates a supervisor agent that oversees the data gathering process."""
        system_prompt_template = (
            """
            You are the supervisor for managing the data requirement gathering workflow.
            Your role is to route the conversation to the user, data_gather_information agent or data_prompt_generator agent
            Here is the chat history:
            {chat_history}
            
            Here are your available options to route the conversation:
            - **data_gather_information**: Collects data requirements from the user.
            - **data_prompt_generator**: Generates a prompt template based on collected requirements.
            - **FINISH**: Forwards the data_gather_information question to the user for additional input.

            Use the messages to route the conversation accordingly.

            Here are the recorded data requirements collected:
            {data_requirements}
            If the data requirements are clear, you can route the conversation to the data_prompt_generator agent to generate a prompt template.

            Here are some examples of messages:
            Example 1: 
            Human: "I need data on customer demographics for the last quarter."
            data_gather_information: "Could you please provide more details about the specific data points you are interested in?"
            Output: **FINISH**

            Example 2:
            Human: "Hello, how are you!"
            data_gather_information: "Hello! How can I assist you with your data needs today?"
            Output: **FINISH**

            Now, based on the current conversation, route the conversation accordingly.
            """
        )

        data_gather_supervisor = self.utilities.create_team_supervisor(
            self.llm,
            system_prompt_template,
            members
        )
        return data_gather_supervisor


