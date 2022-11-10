import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

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

# Не сделал правку с "центром обработки". Сейчас я почти в каждой функции
# в случае ошибки делаю запись в логи и параллельно вызываю исключения.
# Как я понимаю, вы хотите, чтобы в функциях я только вызывал исключения,
# а запись в логи делал уже в main()?
# Если это так, можно подсказку в какую сторону думать, чтобы это реальзовать?


def send_message(bot, message):
    """Отправка сообщения в Telegram чат."""
    try:
        logger.info(f"Отправляем сообщение {message}")
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except Exception as error:
        logger.error(f"Сообщение не {message} отправлено. Ошибка {error}")
    else:
        logger.info(f"Сообщение {message} отправлено")


def get_api_answer(current_timestamp):
    """Отправка запроса к API."""
    params = {'from_date': current_timestamp}
    try:
        response = requests.get(
            ENDPOINT, headers=HEADERS, params=params,
        )
    except requests.RequestException:
        logger.error('Ошибка при обращении к API')
    if response.status_code != HTTPStatus.OK:
        logger.error(f'Сбой при запросе к API.'
                     f'Status Code: {response.status_code}, ожидаемый 200')
        raise requests.HTTPError('Сбой при запросе к API')
    try:
        return response.json()
    except ValueError:
        logger.error('Ответ приходит не в формате json')
        raise ValueError('Ответ приходит не в формате json')


def check_response(response):
    """Проверка ответа API на корректность."""
    try:
        homework_response = response['homeworks']
    except KeyError:
        logger.error('В словаре отсутствует ключ "homeworks"')
        raise KeyError('Ошибка словаря по ключу homeworks')
    if not isinstance(homework_response, list):
        raise TypeError(f'Неверный тип данных. Type "homework_response":'
                        f'{type(homework_response)}. Ожидаемый тип list')
    if "homeworks" not in response.keys():
        raise KeyError('"homeworks" отсутствует в словаре')
    if 'current_date' not in response.keys():
        logger.error('"current_date" отсутствует в словаре')
    return homework_response


def parse_status(homework):
    """Извлечение статуса из домашней работы."""
    try:
        homework_status = homework.get("status")
    except KeyError:
        logger.error('В homeworks отсутствует ключ "status"')
        raise KeyError('В словаре homeworks отсутствует ключ "status"')
    try:
        homework_name = homework.get('homework_name')
    except KeyError:
        logger.error(f'Нет домашней работы с именем {homework_name}')
        raise KeyError(f'Нет домашней работы с именем {homework_name}')
    verdict = HOMEWORK_VERDICT[homework_status]
    if not verdict:
        raise KeyError(f'{verdict}  нет в HOMEWORK_VERDICT')
    if homework_status not in HOMEWORK_VERDICT:
        message_homework_status = f'Статус {homework_status} не существует'
        raise KeyError(message_homework_status)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка доступность переменных окружения."""
    return(all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]))


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    logger.setLevel(logging.INFO)
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

    if not check_tokens():
        logger.critical('Ошибка в получении токенов')
        raise Exception('Ошибка в получении токенов')

    while True:
        try:
            response = get_api_answer(current_timestamp)
            current_timestamp = response.get('current_date')
            homeworks = check_response(response)
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
