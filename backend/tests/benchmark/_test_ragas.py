"""临时测试：RAGAS Faithfulness 单题评测"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

os.environ["RAG_RATE_LIMIT_MODE"] = "bypass"
if "DEEPSEEK_API_KEY" in os.environ and "OPENAI_API_KEY" not in os.environ:
    os.environ["OPENAI_API_KEY"] = os.environ["DEEPSEEK_API_KEY"]

from langchain_openai import ChatOpenAI
from datasets import Dataset as HFDataset
from ragas.metrics import faithfulness
from ragas import evaluate

llm = ChatOpenAI(
    model="deepseek-chat",
    openai_api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
    openai_api_base=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    temperature=0.0,
)
print("LLM OK")

data = HFDataset.from_dict({
    "question": ["年假有多少天？"],
    "answer": ["员工年满一年后可享受年假10天。"],
    "contexts": [["员工年满一年后可享受年假10天。"]],
})
print("Dataset OK")

result = evaluate(data, metrics=[faithfulness], llm=llm)
print("Faithfulness:", result["faithfulness"][0])
