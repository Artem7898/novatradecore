import uuid
from locust import HttpUser, task, constant
import json

class TradeUser(HttpUser):
    # Реалистичная пауза для 1 юзера: от 100 до 300 мс (примерно 3-10 RPS на юзера)
    wait_time = constant(0)

    @task
    def ingest_trade(self):
        payload = {
            "symbol": "SOL/USDT",
            "side": "BUY",
            "price": "150.250000000",
            "quantity": "10.500000000",
            "exchange_id": "binance",
            "trade_id": f"locust_{uuid.uuid4().hex[:12]}"
        }
        self.client.post("/api/v1/trades/ingest/", json=payload)