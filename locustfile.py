from locust import HttpUser, TaskSet, task, between
import random

REQUESTS = [
    {"messages": "Когда был основан университет ИТМО?"},
    {"messages": "Какие кафедры есть в ИТМО?"},
    {"messages": "Как поступить в ИТМО?"},
    {"messages": "Сколько студентов обучается в ИТМО?"},
    {"messages": "Какие направления подготовки есть в ИТМО?"}
] * 20

class UserBehavior(TaskSet):

    @task
    def send_request(self):
        """Отправляет случайный запрос из списка"""
        request_data = random.choice(REQUESTS)
        self.client.post("/api/request", json=request_data)

class WebsiteUser(HttpUser):
    tasks = [UserBehavior]
    wait_time = between(0.5, 1.5)
