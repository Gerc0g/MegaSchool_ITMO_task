from typing_extensions import Literal
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from typing import TypedDict
from langchain_core.messages import HumanMessage, SystemMessage
import re
from langchain_openai import OpenAIEmbeddings
from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS
import os
from uuid import uuid4
from src.ya_search_api import YandexSearchAPI, YandexSearchConfig, YandexSearchParser
from dotenv import load_dotenv
import asyncio

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_PROXY = os.getenv("OPENAI_PROXY")
YANDEX_API = os.getenv("YANDEX_API")

config = YandexSearchConfig(
    api_key=YANDEX_API,
    groups_on_page = 5,
    docs_in_group = 1,
    max_passages = 2,
    l10n = "LOCALIZATION_RU",
    region = "225"
)
search_api = YandexSearchAPI(config)

embeddings = OpenAIEmbeddings(
    model="text-embedding-3-large",
    api_key = OPENAI_API_KEY,
)

async def load_database(_embedding, faiss_idx):
    """Асинхронная загрузка или создание локальной базы данных FAISS."""
    if os.path.exists(faiss_idx) and os.path.isdir(faiss_idx):
        db = await asyncio.to_thread(FAISS.load_local, faiss_idx, _embedding, allow_dangerous_deserialization=True)
    else:
        db = await asyncio.to_thread(FAISS.from_texts, ["Hello pipl"], _embedding)
        await asyncio.to_thread(db.save_local, faiss_idx)
    return db


class AgentState(TypedDict):
    messages: str
    context_messages: list
    is_test: str
    is_rag: str
    is_full_answ: str
    final_answ: dict



async def route_req(state: AgentState) -> Literal["Pass", "Fail"]:
    """
    Функция для определения следующего шага в зависимости от категории.
    """
    print("--- ВЫЗОВ АГЕНТА route_req ---")
    answer = state["messages"]

    multiple_choice_pattern = re.compile(r"^\d+\.\s+", re.MULTILINE)
    if multiple_choice_pattern.search(str(answer)):
        print("--- Текст является тестом ---")
        return {"messages" : state['messages'],
                "context_messages" : state['context_messages'],
                "is_test": "Pass",
                "is_rag": state['is_rag'],
                "is_full_answ": 'test_answer',
                "final_answ": state['final_answ']}
    
    
    model = ChatOpenAI(temperature=0, streaming=False, model="gpt-4-turbo", api_key=OPENAI_API_KEY)
    system_message = SystemMessage(content=(
        """
        Ты интеллектуальный ассистент, задача которого — валидировать контент.
        Твоя цель — определять, является ли текст вопросом на который необходимо ответить.
        Отвечай либо Yes , либо No.
        """
    ))
    human_message = HumanMessage(content=f"Отрывок: {answer}")
    response = await model.ainvoke([system_message, human_message])
    response_text = response.content
    if response_text.lower() == 'yes':
        print("--- Текст является вопросом ---")
        return {"messages" : state['messages'],
            "context_messages" : state['context_messages'],
            "is_test": "Pass",
            "is_rag": state['is_rag'],
            "is_full_answ": 'full_answer',
            "final_answ": state['final_answ']}


    print("--- Текст не является вопросом и не является тестом---")
    final_answer = {
        "answer": "null",
        "reasoning": "Запрос не является вопросом на который можно однозначно ответить или выбрать правильный вариант ответа.",
        "sources": []
    }
    return {"messages" : state['messages'],
            "context_messages" : state['context_messages'],
            "is_test": "Fail",
            "is_rag": state['is_rag'],
            "is_full_answ": state['is_full_answ'],
            "final_answ": final_answer}

async def retrive_vectorstore(state: AgentState):
    """
    Вызывает агентную модель для генерации ответа на основе текущего состояния.
    Учитывая вопрос, агент принимает решение: использовать инструмент поиска или завершить выполнение.

    Аргументы:
        state (messages): Текущее состояние

    Возвращает:
        dict: Обновленное состояние с добавленным ответом агента в список сообщений
    """
    print("--- ВЫЗОВ АГЕНТА Retriver_Valid ---")
    message = state["messages"]

    database = await load_database(embeddings, 'db/prod_db')

    retriever_data = await asyncio.to_thread(database.similarity_search, message, k=3, filter={"table": "ITMO"})

    system_message = SystemMessage(content=(
        """
        Ты интеллектуальный ассистент, задача которого — валидировать контент.
        Твоя цель — определять, можно ли из контаекста текста ответить на вопрос.
        Отвечай либо Yes , либо No.
        """
    ))


    model = ChatOpenAI(temperature=0, streaming=False, model="gpt-4-turbo", api_key=OPENAI_API_KEY)
    valid_docs = []

    for idx, chunk in enumerate(retriever_data):
        human_message = HumanMessage(content=f"Тема запроса: {message}; Отрывок: {chunk.page_content}")
        response = await model.ainvoke([system_message, human_message])
        response_text = response.content
        print(f"--- Чанк {idx} валидный? - {response_text} ---")

        if response_text.lower() == 'yes':
            valid_docs.append({"text" : chunk.page_content,
                                "url" : chunk.metadata['url']})

    print(f"--- Всего чанков отобрано {len(valid_docs)} ---")

    if len(valid_docs) != 0:
        print(f"--- Начинаем генерацию ответа ---")
        return {"messages" : state['messages'],
                "context_messages" : valid_docs,
                "is_test":  state['is_test'],
                "is_rag": "Pass",
               "is_full_answ": state['is_full_answ'],
                "final_answ": state['final_answ']}
    else:
        print(f"--- переходим в поиск в интернете ---")
        return {"messages" : state['messages'],
                "context_messages" : state['context_messages'],
                "is_test":  state['is_test'],
                "is_rag": "Fail",
                "is_full_answ": state['is_full_answ'],
                "final_answ": state['final_answ']}


async def retrieve_web(state: AgentState):
    """Функция-заглушка для инструмента поиска в интернете"""
    print("---TOOL: WEB SEARCH TOOL---")

    query = state["messages"]
    response = await search_api.search(query)
    valid_docs = []

    if response:
        print("Ответ от API получен, парсим XML...")
        parsed_results = YandexSearchParser.parse(response)

        model = ChatOpenAI(temperature=0, streaming=False, model="gpt-4-turbo", api_key=OPENAI_API_KEY)
        system_message = SystemMessage(content=(
                """
                Ты интеллектуальный ассистент, задача которого — валидировать контент.
                Твоя цель — определять, есть ли ответ на вопрос.
                Отвечай однозначно либо Yes , либо No.
                """
        ))

        for idx, doc in enumerate(parsed_results, start=1):
            if len(valid_docs) >= 3:
                break

            url = doc['url']
            print(f"\nДокумент {idx}:")
            print(f"URL: {url}")

            passages_text = ', '.join(doc['passages'])
            human_message = HumanMessage(content=f"Вопрос: {query}; Контекст: {passages_text}")
            response = await model.ainvoke([system_message, human_message])
            response_text = response.content
            print(f"--- Чанк {idx} валидный? - {response_text} ---")
            print(f"--- {passages_text} ---")
            if response_text.lower() == 'yes':
                valid_docs.append({"text" : passages_text,
                                   "url" : url})
            else:
                passages_text = doc.get('extended_text', '')
                human_message = HumanMessage(content=f"Тема запроса: {query}; Отрывок: {passages_text}")
                messages = [system_message, human_message]
                response = await model.ainvoke(messages)
                response_text = response.content
                print(f"--- Чанк {idx} валидный? - {response_text} ---")
                print(f"--- {passages_text} ---")
                if response_text.lower() == 'yes':
                    valid_docs.append({"text" : passages_text,
                                        "url" : url})




    print(f"--- Всего чанков отобрано {len(valid_docs)} ---")

    if len(valid_docs) == 0:
        return {"messages" : state['messages'],
            "context_messages" : [],
            "is_test":  state['is_test'],
            "is_rag": state['is_rag'],
            "is_full_answ": state['is_full_answ'],
            "final_answ": state['final_answ']}

    state['context_messages'] = valid_docs

    return {"messages" : state['messages'],
            "context_messages" : valid_docs,
            "is_test":  state['is_test'],
            "is_rag": state['is_rag'],
            "is_full_answ": state['is_full_answ'],
            "final_answ": state['final_answ']}


async def store_in_vector_db(state: AgentState):
    print("---STORE IN VECTOR DB---")
    doc_list = []
    context = state['context_messages']

    if len(context) == 0:
        return {"messages" : state['messages'],
            "context_messages" : [],
            "is_test":  state['is_test'],
            "is_rag": state['is_rag'],
            "is_full_answ": state['is_full_answ'],
            "final_answ": state['final_answ']}
    
    database = await load_database(embeddings, 'db/prod_db')


    for chunk in context:
        cur_doc = Document(page_content = chunk['text'], metadata={'url' : chunk['url'], "table": "ITMO"})
        doc_list.append(cur_doc)

    uuids = [str(uuid4()) for _ in range(len(doc_list))]

    await asyncio.to_thread(database.add_documents, doc_list, ids=uuids)
    await asyncio.to_thread(database.save_local, 'db/prod_db')
    
    return {"messages" : state['messages'],
            "context_messages" : state['context_messages'],
            "is_test":  state['is_test'],
            "is_rag": state['is_rag'],
            "is_full_answ": state['is_full_answ'],
            "final_answ": state['final_answ']}

async def generate(state: AgentState):
    print("---GENERATE RESPONSE---")

    message = state["messages"]
    context = state['context_messages']
    is_full_answ = state['is_full_answ']

    if not context:
        final_answer = {
            "answer": "null",
            "reasoning": "Не удалось найти контекст по данному вопросу в RAG и в Интернете, переформулируйте пожалуйста вопрос или проверьте его правильность.",
            "sources": []
        }
        return {
            "messages": state['messages'],
            "context_messages": state['context_messages'],
            "is_test": state['is_test'],
            "is_rag": state['is_rag'],
            "is_full_answ": state['is_full_answ'],
            "final_answ": final_answer
        }

    result_context = "\n".join(chunk.get('text', '') for chunk in context)
    urls_list = [chunk['url'] for chunk in context if 'url' in chunk]

    model = ChatOpenAI(temperature=0.5, streaming=False, model="gpt-4-turbo", api_key=OPENAI_API_KEY)

    system_message = SystemMessage(content=(
        """
        Ты — интеллектуальный помощник, задача которого — анализировать вопрос и развернуто ответить на него на основе предоставленного контекста.
        **Инструкция:**
        1. Внимательно прочитай контекст, содержащий информацию, необходимую для ответа на вопрос.
        2. Ознакомься с самим вопросом.
        3. Сформируй ответ на вопрос.

        В ответе напиши кратко вариант ответа, основываясь на предоставленный контекст.
        """
    ))

    human_message = HumanMessage(content=f"Вопрос: {message}, Контекст: {result_context}")

    print(f'--- ВОПРОС ----\n{message}')
    print(f'--- КОНТЕКСТ ----\n{result_context}')

    messages = [system_message, human_message]

    response = await model.ainvoke(messages)
    response_ans = response.content

    print(f'--- ОТВЕТ ----\n{response_ans}')

    answer = "null"
    reasoning = response_ans
    sources = [url for url in urls_list if url]

    if is_full_answ == 'test_answer':
        test_model = ChatOpenAI(temperature=0, streaming=False, model="gpt-4-turbo", api_key=OPENAI_API_KEY)

        system_message = SystemMessage(content=(
            """
            Ты — интеллектуальный помощник, задача которого — анализировать вопрос и выбирать правильный вариант ответа на основе предоставленного контекста.
            **Инструкция:**
            1. Внимательно прочитай контекст, содержащий информацию, необходимую для ответа на вопрос.
            2. Ознакомься с самим вопросом и предложенными вариантами ответов.
            3. Определи правильный вариант ответа на основе контекста.
            4. Вопрос содержит варианты ответов (пронумерованные от 1 до 10), выбери один правильный вариант и укажи его номер.

            В ответе верни лишь число правильного ответа.
            """
        ))

        test_human_message = HumanMessage(content=f"Вопрос: {message}, Контекст: {response_ans}")

        print(f'--- ВОПРОС ----\n{message}')
        print(f'--- КОНТЕКСТ ----\n{response_ans}')

        test_messages = [system_message, test_human_message]
        test_response = await test_model.ainvoke(test_messages)
        test_response_text = test_response.content.strip()

        match = re.findall(r'\b(10|[1-9])\b', test_response_text)
        answer = match[0] if match else "null"

        print(f'--- ОТВЕТ ----\n{answer}')

    elif is_full_answ == 'full_answer':
        answer = "null"
        reasoning = response_ans

    final_answer = {
        "answer": answer,
        "reasoning": reasoning,
        "sources": sources
    }

    return {
        "messages": state['messages'],
        "context_messages": state['context_messages'],
        "is_test": state['is_test'],
        "is_rag": state['is_rag'],
        "is_full_answ": state['is_full_answ'],
        "final_answ": final_answer
    }
