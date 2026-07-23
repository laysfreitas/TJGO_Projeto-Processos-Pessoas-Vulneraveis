from google.adk.agents.llm_agent import Agent

# root_agent = Agent(
#     model='gemini-3.5-flash',                                               # Model: The reasoning engine (Course 1!)
#     name='root_agent',                                                      # Identity: Required identifier
#     description='A helpful assistant for user questions.',                  # Purpose: What this agent does
#     instruction='Answer user questions to the best of your knowledge',      # Behavior: How this agent should behave
#     # Tools: 
#     # Orchestration: 
# )

root_agent = Agent(
    model='gemini-2.5-flash',
    name='math_tutor_agent',
    description='Helps students learn algebra by guiding them through problem solving steps.',
    instruction='You are a patient math tutor. Help students with algebra problems.'
)