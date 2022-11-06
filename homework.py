import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    level=logging.DEBUG,
    filename='homework_bot.log',
    format='%(asctime)s, %(levelname)s, %(message)s, %(name)s'
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def send_message(bot, message):
    """Отправка сообщения в Telegram чат."""
    logger.info("Отправляем сообщение в чате")
    bot_message = bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    if not bot_message:
        raise telegram.TelegramError("Сообщение не отправлено")
    else:
        logger.info("Сообщение отправлено")


def get_api_answer(current_timestamp):
    """Отправка запроса к API."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(
            ENDPOINT, headers=HEADERS, params=params,
        )
    except Exception:
        logger.error("Ошибка при обращении к API")
    if response.status_code != HTTPStatus.OK:
        message = "Сбой при запросе к API"
        raise requests.HTTPError(message)
    return response.json()


def check_response(response):
    """Проверка ответа API на корректность."""
    homework_response = response['homeworks']
    if not homework_response:
        message = ("Отсутствует статус homeworks")
        raise LookupError(message)
    if not isinstance(homework_response, list):
        message = ("Неверный тип данных")
        raise TypeError(message)
    if "homeworks" not in response.keys():
        message = '"homeworks" отсутствует в словаре'
        raise KeyError(message)
    if 'current_date' not in response.keys():
        message = '"current_date" отсутствует в словаре'
        raise KeyError(message)
    return homework_response


def parse_status(homework):
    """Извлечение из домашней работы её статус."""
    homework_name = homework.get("homework_name")
    homework_status = homework.get("status")
    verdict = HOMEWORK_STATUSES[homework_status]
    if not verdict:
        message_verdict = "Такого статуса нет в словаре"
        raise KeyError(message_verdict)
    if homework_status not in HOMEWORK_STATUSES:
        message_homework_status = "Такого статуса не существует"
        raise KeyError(message_homework_status)
    if "homework_name" not in homework:
        message_homework_name = "Такого имени не существует"
        raise KeyError(message_homework_name)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка доступность переменных окружения."""
    return(all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]))


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    if not check_tokens():
        logger.critical("Ошибка в получении токенов")
        sys.exit()
    actual_status = {}
    previous_status = {}
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homework = check_response(response)[0]
            if homework:
                message = parse_status(homework)
                actual_status[response.get(
                    "homework_name")] = response.get("status")
                if actual_status != previous_status:
                    send_message(bot, message)
                    previous_status = actual_status.copy()
                    actual_status[response.get(
                        "homework_name")] = response.get("status")
            current_timestamp = response.get("current_date")

        except Exception as error:
            message = f"Сбой в работе программы: {error}"
            logger.error(message)
        else:
            logger.error("Сбой")
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
