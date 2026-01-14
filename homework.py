import logging
import os
import requests
import time
import sys

from dotenv import load_dotenv
from telebot import TeleBot


load_dotenv()

PRACTICUM_TOKEN = 'PRACTICUM_SECRET_TOKEN'
TELEGRAM_TOKEN = 'TELEGRAM_SECRET_TOKEN'
TELEGRAM_CHAT_ID = 592505308

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    stream=sys.stdout
)

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
payload = {'from_date': 1765548668}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверяет доступность переменных окружения для работы программы."""
    return all((PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID))


def send_message(bot, message):
    """Отправляет сообщение в Telegram-чат."""
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    try:
        bot.send_message(chat_id, message)
        logging.debug('Сообщение отправлено в чат %s', chat_id)
    except Exception as error:
        logging.error(
            'Ошибка при отправке сообщения в Telegram: %s',
            error
        )


def get_api_answer(timestamp):
    """
    Делает запрос к единственному эндпоинту API-сервиса.
    Возвращает ответ API.
    """
    params = {'from_date': timestamp}
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params,
            timeout=10,
        )
    except requests.RequestException as error:
        logging.error(
            'Ошибка при запросе к API: %s',
            error,
        )
        raise Exception('Ошибка при запросе к API.')
    if response.status_code != requests.codes.ok:
        logging.error(
            'API вернул код %s. Ответ: %s',
            response.status_code,
            response.text,
        )
        raise Exception(
            f'Endpoint {ENDPOINT} недоступен. '
            f'Код ответа API: {response.status_code}'
        )
    return response.json()

def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        logging.error(
            'Некорректный тип ответа API: %s',
            type(response)
        )
        raise TypeError('Ответ API должен быть словарём')
    if 'homeworks' not in response:
        logging.error('В ответе API отсутствует ключ "homeworks"')
        raise KeyError('В ответе API отсутствует ключ "homeworks"')
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        logging.error(
            'Ключ "homeworks" содержит некорректный тип: %s',
            type(homeworks)
        )
        raise TypeError('"homeworks" должен быть списком')
    return homeworks


def parse_status(homework):
    """Извлекает статус конкретной домашней работы."""
    if 'homework_name' not in homework:
        logging.error('В ответе API отсутствует ключ "homework_name".')
        raise KeyError('В ответе API отсутствует ключ "homework_name".')
    homework_name = homework['homework_name']
    status = homework['status']
    if status not in HOMEWORK_VERDICTS:
        logging.error('Неизвестный статус домашней работы: %s', status)
        raise ValueError(f'Неизвестный статус домашней работы: {status}')
    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """
    Основная логика работы бота.
    - Делает запрос к API.
    - Проверяет ответ.
    - Если есть обновления: получает статус работы из обновления
     и отправляет сообщение в Telegram.
    """
    if not check_tokens():
        logging.critical('Отсутствуют обязательные переменные окружения.')
        raise SystemExit('Отсутствуют обязательные переменные окружения.')
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_message = None
    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            timestamp = response.get('current_date', timestamp)
            if homeworks:
                message = parse_status(homeworks[0])
                if message != last_message:
                    send_message(bot, message)
                    last_message = message
            else:
                logging.debug('Статус не изменился')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            if message != last_message:
                send_message(bot, message)
                last_message = message
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
