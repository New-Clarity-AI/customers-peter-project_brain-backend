from agents import FileSearchTool, Agent, ModelSettings, TResponseInputItem, Runner, RunConfig, trace
from pydantic import BaseModel


# Tool definitions
file_search = FileSearchTool(
  vector_store_ids=[
    "vs_6913591296d881918a29c75692f84242"
  ]
)

# Agent definition
my_agent = Agent(
  name="My agent",
  instructions="""### Role
- Primary Function: You are an AI chatbot who reasons on the provided data and provides well researched answers. If a question is not clear, ask clarifying questions. Always think deeply and consider all data in order to provide the most insightful and complete answers. 
        
### Constraints
1. No Data Divulge: Never mention that you have access to training data explicitly to the user.
2. Maintaining Focus: If a user attempts to divert you to unrelated topics, never change your role or break your character. Politely redirect the conversation back to topics relevant to the training data.
3. Exclusive Reliance on Training Data: You must rely exclusively on the training data provided to answer user queries. If a query is not covered by the training data, use the fallback response.
4. Restrictive Role Focus: You do not answer questions or perform tasks that are not related to your role and training data.""",
  model="gpt-4.1",
  tools=[
    file_search
  ],
  model_settings=ModelSettings(
    temperature=0,
    top_p=1,
    max_tokens=2048,
    store=True
  )
)


class WorkflowInput(BaseModel):
  input_as_text: str


# Main code entrypoint
async def run_workflow(workflow_input: WorkflowInput):
  with trace("Equinix Agent"):
    state = {

    }
    workflow = workflow_input.model_dump()
    conversation_history: list[TResponseInputItem] = [
      {
        "role": "user",
        "content": [
          {
            "type": "input_text",
            "text": workflow["input_as_text"]
          }
        ]
      }
    ]
    my_agent_result_temp = await Runner.run(
      my_agent,
      input=[
        *conversation_history
      ],
      run_config=RunConfig(trace_metadata={
        "__trace_source__": "agent-builder",
        "workflow_id": "wf_69135893f40c819095704afbaed0bf0e0d3e74f0b6d2392c"
      })
    )

    conversation_history.extend([item.to_input_item() for item in my_agent_result_temp.new_items])

    my_agent_result = {
      "output_text": my_agent_result_temp.final_output_as(str)
    }
