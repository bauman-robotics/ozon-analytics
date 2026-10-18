"""HTTP-клиент Ozon Seller API: ретраи, лимиты, понятные ошибки."""

from __future__ import annotations

import http.client
import json
import random
import time
import urllib.error
import urllib.request
from typing import Any

# Подсказки по частым ошибкам Ozon API
_HINTS: list[tuple[str, str]] = [
    ("invalid api-key", "Неверный Api-Key. Проверьте ключ в Настройки → API ключи."),
    ("deactivated", "Api-Key отозван или деактивирован. Создайте новый ключ."),
    ("missing a required role", "У ключа нет нужной роли. Добавьте роль в настройках ключа."),
    ("restricted to specific ip", "Ключ ограничен по IP. Запрос должен идти с разрешённого адреса."),
    ("offer not signed", "Не принята оферта Seller API. Примите её в личном кабинете."),
    ("rate limit", "Превышен лимит запросов. Увеличьте паузы (OZON_RPS) и повторите."),
    ("too many requests", "Слишком частые запросы. Увеличьте паузы между вызовами."),
    ("method is not allowed", "Метод недоступен для вашего тарифа/ключа."),
    ("not available with existing subscription", "Метод требует подписки Premium/Premium Plus."),
    ("token must be issued for seller", "Для этого метода нужен OAuth-токен, а не Api-Key."),
    ("not signed", "Проверьте, что оферта Seller API принята в личном кабинете."),
]

# Минимальный интервал между вызовами для методов с жёстким лимитом.
# Ozon: /v1/analytics/data — не больше 1 запроса в минуту (и 50 в сутки
# без Premium Plus), /v1/analytics/turnover/stocks — 1 запрос в минуту.
METHOD_INTERVALS: dict[str, float] = {
    "/v1/analytics/data": 60.0,
    "/v1/analytics/turnover/stocks": 60.0,
}


class OzonAPIError(RuntimeError):
    def __init__(self, message: str, status: int | None = None, code: Any = None, body: str = ""):
        super().__init__(message)
        self.status = status
        self.code = code
        self.body = body


class RateLimiter:
    """Простой ограничитель: не чаще N запросов в секунду."""

    def __init__(self, rps: float = 10.0) -> None:
        self.min_interval = 1.0 / max(rps, 0.1)
        self._last = 0.0

    def wait(self) -> None:
        now = time.monotonic()
        delta = now - self._last
        if delta < self.min_interval:
            time.sleep(self.min_interval - delta)
        self._last = time.monotonic()


class OzonClient:
    def __init__(
        self,
        client_id: str,
        api_key: str,
        *,
        base_url: str = "https://api-seller.ozon.ru",
        timeout: int = 30,
        rps: float = 10.0,
        sleep=time.sleep,
    ) -> None:
        self.client_id = client_id
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.sleep = sleep
        self.limiter = RateLimiter(rps)
        self._last_by_path: dict[str, float] = {}
        self.calls = 0
        self.warnings: list[str] = []

    # --- публичный API -------------------------------------------------
    def post(self, path: str, payload: dict | None = None, *, attempts: int = 4) -> dict:
        data = json.dumps(payload or {}, ensure_ascii=False).encode("utf-8")
        last_error: Exception | None = None

        for attempt in range(1, attempts + 1):
            # Проверяем лимит перед каждой попыткой, в том числе перед ретраем.
            self._respect_method_limit(path)
            request = urllib.request.Request(
                self.base_url + path,
                data=data,
                method="POST",
                headers={
                    "Client-Id": self.client_id,
                    "Api-Key": self.api_key,
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "User-Agent": "ozon-analytics/1.0",
                },
            )
            try:
                self.limiter.wait()
                self.calls += 1
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    raw = response.read()
                self._last_by_path[path] = time.monotonic()
                if not raw:
                    return {}
                try:
                    return json.loads(raw.decode("utf-8"))
                except (ValueError, UnicodeDecodeError) as exc:
                    raise OzonAPIError(
                        f"Ozon API вернул не-JSON ответ: {raw[:200]!r}"
                    ) from exc
            except urllib.error.HTTPError as exc:
                self._last_by_path[path] = time.monotonic()
                raw = exc.read().decode("utf-8", "replace")
                code, message = self._parse_error(raw)
                if exc.code in (429, 500, 502, 503, 504) and attempt < attempts:
                    self.sleep(self._retry_delay(exc.headers, attempt, exc.code))
                    continue
                raise OzonAPIError(self._friendly(message, exc.code), exc.code, code, raw) from exc
            except (urllib.error.URLError, http.client.HTTPException, TimeoutError, OSError) as exc:
                self._last_by_path[path] = time.monotonic()
                last_error = exc
                if attempt < attempts:
                    self.sleep(self._backoff(attempt))
                    continue
                raise OzonAPIError(f"Нет связи с API Ozon: {exc}") from exc

        raise OzonAPIError(f"Запрос не удался: {last_error}")

    # --- служебное ------------------------------------------------------
    def _respect_method_limit(self, path: str) -> None:
        interval = METHOD_INTERVALS.get(path)
        if not interval:
            return
        last = self._last_by_path.get(path)
        if last is None:
            return
        remaining = interval - (time.monotonic() - last)
        if remaining > 0:
            self.sleep(remaining)

    @staticmethod
    def _backoff(attempt: int) -> float:
        return min(2 ** (attempt - 1), 8) + random.uniform(0, 0.4)

    @staticmethod
    def _retry_delay(headers, attempt: int, status: int) -> float:
        """Пауза перед ретраем: Retry-After важнее экспоненциальной задержки."""
        value = headers.get("Retry-After") if headers else None
        if value:
            try:
                return max(0.0, min(float(value), 120.0))
            except (TypeError, ValueError):
                pass
        if status == 429:
            # Лимит Ozon часто минутный — короткой паузы в 1–8 секунд мало.
            return min(max(5.0, 2 ** attempt), 60.0) + random.uniform(0, 0.4)
        return OzonClient._backoff(attempt)

    @staticmethod
    def _parse_error(raw: str) -> tuple[Any, str]:
        try:
            obj = json.loads(raw)
        except (ValueError, TypeError):
            return None, raw[:400]
        if isinstance(obj, dict):
            code = obj.get("code")
            message = obj.get("message") or obj.get("error") or raw[:400]
            return code, str(message)
        return None, str(obj)[:400]

    @staticmethod
    def _friendly(message: str, status: int) -> str:
        low = message.lower()
        for needle, hint in _HINTS:
            if needle in low:
                return f"{hint} (HTTP {status}: {message})"
        return f"Ошибка Ozon API (HTTP {status}): {message}"
