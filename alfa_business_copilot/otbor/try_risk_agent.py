from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

from alfa_agent.acquisition import RiskAdvisorAgent, RiskChatState
from alfa_agent.llm import LLMError


def main() -> None:
    agent = RiskAdvisorAgent()
    state = RiskChatState()

    print("Опишите бизнес, который хотите открыть, — например: «хочу открыть кофейню, риски?»")
    print("Для выхода: Ctrl+C\n")

    while True:
        try:
            user_message = input("Вы: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nПока!")
            return

        if not user_message:
            continue

        try:
            reply, state = agent.handle_message(user_message, state)
        except LLMError as exc:
            print(f"[Ошибка LLM] {exc}")
            continue

        print(f"Агент: {reply}\n")


if __name__ == "__main__":
    main()
