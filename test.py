from dotenv import load_dotenv
load_dotenv()
from convo_llm import parse_nlu_with_llm, generate_reply_with_llm

# NLU test
print(parse_nlu_with_llm("I want something spicy under $10"))

# Reply test
products = [
    {"product_id":"R001","name":"Chicken Fried Rice","price":8.99,"description":"Classic fried rice","spice_level":3,"popularity_score":85}
]
print(generate_reply_with_llm({}, "Tell me about chicken fried rice", products, 70))
