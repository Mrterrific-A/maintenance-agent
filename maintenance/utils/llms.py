from langchain_openai import ChatOpenAI
import os
from dotenv import load_dotenv
from utils.tools import tools
from utils.parser import system_report_parser, intent_parser
from utils.templates import intent_recognition_prompt, system_health_prompt, chat_prompt, result_prompt

load_dotenv()


llm = ChatOpenAI(
    api_key=os.getenv("API_KEY"),
    base_url=os.getenv("BASE_URL"),
    model=os.getenv("MODEL"),
)


model_with_tools = llm.bind_tools(tools)

model_analysis = system_health_prompt| llm | system_report_parser

model_intent_recognition = intent_recognition_prompt | llm | intent_parser

model_chat = chat_prompt | llm

result_chat = result_prompt | llm