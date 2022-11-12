import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

import custom_exeptions

load_dotenv()
logger = logging.getLogger(__name__)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICT = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message):
    """Отправка сообщения в Telegram чат."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except custom_exeptions.SendMessageError:
        logger.error(f'Сообщение {message} не отправлено')
    else:
        logger.info(f"Сообщение {message} отправлено")


def get_api_answer(current_timestamp):
    """Отправка запроса к API."""
    params = {'from_date': current_timestamp}
    try:
        response = requests.get(
            ENDPOINT, headers=HEADERS, params=params,
        )
        response.json()
    except custom_exeptions.GetApiAnswerError:
        logger.error('Ошибка при обращении к API')
    if response.status_code != HTTPStatus.OK:
        raise custom_exeptions.GetApiAnswerError('Сбой при запросе к API')
    return response.json()


def check_response(response):
    """Проверка ответа API на корректность."""
    homework_response = response['homeworks']
    if not isinstance(response, dict):
        raise KeyError(
            f'Неверный тип данных. Type "homework_response":'
            f'{type(response)}. Ожидаемый тип dict'
        )
    if 'homeworks' not in response.keys():
        raise custom_exeptions.CheckResponseError(
            'Ошибка словаря по ключу homeworks'
        )
    if not isinstance(homework_response, list):
        raise custom_exeptions.CheckResponseError(
            f'Неверный тип данных. Type "homework_response":'
            f'{type(homework_response)}. Ожидаемый тип list'
        )
    if 'current_date' not in response.keys():
        logger.error('"current_date" отсутствует в словаре')
    return homework_response


def parse_status(homework):
    """Извлечение статуса из домашней работы."""
    if 'status' not in homework.keys():
        raise KeyError('В словаре homeworks отсутствует ключ "status"')
    if 'homework_name' not in homework.keys():
        raise KeyError('В словаре homeworks отсутствует ключ "homework_name"')
    homework_status = homework.get('status')
    homework_name = homework.get('homework_name')
    verdict = HOMEWORK_VERDICT[homework_status]
    if not verdict:
        raise KeyError(f'{verdict}  нет в HOMEWORK_VERDICT')
    if homework_status not in HOMEWORK_VERDICT:
        raise KeyError(f'Статус {homework_status} не существует')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка доступность переменных окружения."""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())

    if not check_tokens():
        sys.exit('Ошибка в получении токенов')

    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            current_timestamp = response.get('current_date')
            for homework in homeworks:
                message = parse_status(homework)
                send_message(bot, message)
        except Exception as error:
            logger.error(f'Сбой в работе программы: {error}')
            send_message(bot, str(error))
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
    logging.basicConfig(
        level=logging.INFO,
        filename='homework_bot.log',
        filemode='w'
    )
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        '%(asctime)s, %(levelname)s, %(message)s, %(name)s'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
