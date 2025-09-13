

# 🍔 Foodie — Conversational Food Recommendation Bot

Foodie is a modern, AI-powered food discovery and recommendation platform. Built with modular backend and interactive UI, Foodie empowers users to explore, filter, and select dishes that fit their mood, budget, and dietary preferences—whether through friendly chat or advanced search.

***

## 🚩 Table of Contents

- [Features](#features)
- [Demo Screenshots](#demo-screenshots)
- [Architecture Overview](#architecture-overview)
- [Project Structure](#project-structure)
- [Setup & Installation](#setup--installation)
- [API Reference](#api-reference)
- [Data & Analytics](#data--analytics)
- [Customization](#customization)
- [Contributing](#contributing)
- [License](#license)
- [Credits](#credits)

***

## ✨ Features

- **Conversational Chatbot**  
  Engage in natural language chat to get meal recommendations.
- **Personalized Filters**  
  Suggestions by *mood*, *budget*, *dietary tags* (vegan, gluten-free, etc.), and nutrients.
- **Context & Session Memory**  
  Maintains conversation history and context for each user.
- **Flexible Recommendation Logic**  
  Supports preference-based, collaborative filtering, and admin-curated specials.
- **Admin CRUD Dashboard**  
  Manage menu/products from Streamlit UI — add, update, delete in seconds.
- **Advanced Analytics**  
  Conversation, product, and query logging for insights and improvement.
- **LLM Ready, But Optional**  
  Seamless integration with Groq or HuggingFace LLMs (API key/module required).
- **Modern API**  
  REST endpoints for chat, search, analytics, and admin operations.

***

## 🖥️ Demo Screenshots

<img width="1914" height="859" alt="image" src="https://github.com/user-attachments/assets/866e716c-07b0-4650-9f8e-2570790130d8" />
<img width="1919" height="859" alt="image" src="https://github.com/user-attachments/assets/19c5ae59-12ea-4d3d-ac8d-2ae49bf12ee2" />
<img width="1907" height="847" alt="image" src="https://github.com/user-attachments/assets/a4be695e-f533-4283-b77f-b933592e1f6b" />

***

## 🏗 Architecture Overview

| Layer           | Component                  | Description                                                      |
| --------------- | ------------------------- | ---------------------------------------------------------------- |
| Database        | SQLite (`foodie_products.db`, `analytics.db`) | Product/analytics storage                         |
| Backend         | Python, FastAPI (`app.py`) | RESTful API, session/context logic, recommendation endpoints      |
| Chat & LLM      | convo.py, convo_llm.py     | NLU, context/scoring, Groq/HF-powered LLM responses (optional)   |
| Recommendation  | recommender.py             | Filtering, scoring, and collaborative recommend logic             |
| Analytics       | analytics.py               | Conversation/query/event logging to analytics DB                  |
| Frontend        | Streamlit (`streamlit_app.py`) | Interactive web UI with multi-page navigation, product browsing |

***

## 🗂 Project Structure

```
├── app.py              # FastAPI backend (API, session mgmt, endpoints)
├── streamlit_app.py    # Streamlit UI app (chat, search, analytics, admin)
├── recommender.py      # Recommendation (mood, budget, dietary, collaborative)
├── convo.py            # Session context, NLU, engagement/score logic
├── convo_llm.py        # LLM (Groq/HF) parsing & response (optional)
├── analytics.py        # Logging queries, conversations, analytics endpoints
├── foodie_products.db  # SQLite: product/menu items
├── analytics.db        # SQLite: events, conversations, queries
├── test.py             # CLI tests for LLM parsing/reply
└── README.md           # Project information (you're here!)
```

***

## ⚡ Setup & Installation

1. **Clone Repo**
    ```bash
    git clone https://github.com/dhruv25072003/Foodie.git
    cd Foodie
    ```

2. **Create a Python Environment & Install**
    ```bash
    pip install -r requirements.txt
    ```

3. **(Optional) Configure LLM**
    - Set up environment variables:
      - `GROQ_API_KEY` and `GROQ_ENDPOINT` *(for Groq LLM)*
      - or `HF_API_TOKEN` *(for HuggingFace)*
    - LLM is optional; system falls back to rule-based NLU if unset.

4. **Run Backend**
    ```bash
    uvicorn app:app --reload
    ```

5. **Start the Frontend**
    ```bash
    streamlit run streamlit_app.py
    ```

6. **Browse**:  
   - API Docs: `http://localhost:8000/docs`
   - UI Demo: `http://localhost:8501`

***

## 📚 API Reference

**Core Endpoints (FastAPI)**

| Route                       | Method | Description                       |
|-----------------------------|--------|-----------------------------------|
| `/chat`                     | POST   | Chat with FoodieBot (NLU, LLM)    |
| `/recommend`                | GET    | Filtered product recommendations  |
| `/recommend_from_context`   | GET    | Recommend by user session/history |
| `/search`                   | GET    | Search by name/description        |
| `/product/{product_id}`     | GET    | View product details              |
| `/analytics/conversations`  | GET    | List dialog history/logs          |
| `/analytics/recent_queries` | GET    | Query log stats                   |
| `/admin/products`           | POST   | Add new product (admin)           |
| `/admin/products/{id}`      | PUT    | Update product (admin)            |
| `/admin/products/{id}`      | DELETE | Delete product (admin)            |
| `/collab`                   | GET    | Collaborative filtering recs      |

**Sample Request**
```bash
curl -X POST "http://localhost:8000/chat" -H "Content-Type: application/json" \
     -d '{"message":"Suggest something spicy under $10"}'
```

***

## 📊 Data & Analytics

- *Event Logging*: All recommendations, queries, and chats logged (user message, intent, engagement score, products shown/chosen).
- *Database*:  
    - `foodie_products.db`: Menu/product info  
    - `analytics.db`: Conversation, intent, and event logs
- *Streamlit Analytics Page*: View and graph historical user engagement and query performance.

***

## 🔧 Customization

- **LLM Integration**  
  Set the relevant API keys; Groq and HuggingFace are auto-detected if available.
- **Extend Menu or Schema**  
  Edit the SQLite DB or use the Product CRUD UI in Streamlit Admin.
- **UI Theming**  
  Update Streamlit theme or fork UI section for custom branding.
- **Analytics Expansion**  
  Add or modify analytic event points and queries in `analytics.py`.

***

## 🤝 Contributing

- Star, fork, and submit PRs for new features, bug fixes, or docs improvements.
- Suggest enhancements via GitHub Issues.
- All feedback and feature requests are welcome!

***

## 📄 License

Open source under the MIT License.

***

## 🙏 Credits

Developed by [@dhruv25072003](https://github.com/dhruv25072003)  
AI, Analytics, and Real-World AI Product Engineering

***

*Ready to deploy — just clone, install, and chat!*

Let me know if you want further details (requirements.txt, example DB entries, or extra code comments included)!
