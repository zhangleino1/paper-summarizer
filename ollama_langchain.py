from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama.llms import OllamaLLM

template = """Question: {question}

Answer: 给出答案."""

prompt = ChatPromptTemplate.from_template(template)
Model = "qwen2.5:14b"
model = OllamaLLM(model=Model)

chain = prompt | model

result = chain.invoke({"question": "程序员怎么创业？"})

print(result)