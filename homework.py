import os
import sys
import time
import logging

from dotenv import load_dotenv
import requests
from telegram import Bot, TelegramError
from http import HTTPStatus

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


def send_message(bot: Bot, message: str) -> None:
    """
    Отправляет сообщение в Telegram чат, определяемый.

    переменной окружения TELEGRAM_CHAT_ID.
    """
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except Exception as tgerror:
        raise TelegramError(f'Ошибка при отправке данных:'
                            f' {tgerror}') from tgerror


def get_api_answer(current_timestamp: time) -> dict:
    """Делает запрос к единственному эндпоинту API-сервиса."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except Exception as error:
        raise requests.ConnectionError(
            f'Ошибка при получении данных: {error}'
        ) from error
    status = response.status_code
    if not status == HTTPStatus.OK:
        raise requests.HTTPError(f'возврат статуса ответа {status}')
    return response.json()


def check_response(response: dict) -> list:
    """Проверяет ответ API на корректность."""
    if not (isinstance(response, dict) and len(response) > 0):
        raise TypeError('response - не словарь.. ну или пустой словарь :)')
    homeworks = response.get('homeworks')
    if not homeworks:
        raise KeyError('отсутствие ключа homeworks в response')
    if isinstance(homeworks, list):
        return homeworks
    else:
        raise TypeError('под ключом homeworks в response - не список')


def parse_status(homework: dict) -> str:
    """
    Извлекает из информации о конкретной домашней работе.

    статус этой работы.
    """
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')

    if homework_status in HOMEWORK_STATUSES:
        verdict = HOMEWORK_STATUSES[homework_status]
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'
    else:
        raise KeyError("Invalid or Empty Key")


def check_tokens() -> bool:
    """
    Проверяет доступность переменных окружения.

    которые необходимы для работы программы.
    """
    return all((PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID))


def main():
    """Основная логика работы бота."""
    logger = logging.getLogger(__name__)
    logging.basicConfig(
        level=logging.INFO,
        handlers=logger.addHandler(logging.StreamHandler()),
        filemode='w',
        format='%(asctime)s, %(levelname)s, %(message)s, %(name)s'
    )

    if not check_tokens():
        logger.critical('отсутствие обязательных переменных окружения')
        sys.exit()

    bot = Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())

    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if homeworks:
                status = parse_status(homeworks[0])
                send_message(bot, status)

        except TelegramError as error:
            logger.error(f'Где-то в API telegram беда.. {error}')

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.exception(message)
            send_message(bot, message)
            time.sleep(RETRY_TIME)
        else:
            logger.info('всё идёт по плану')
        finally:
            time.sleep(RETRY_TIME)
            current_timestamp = int(time.time())


if __name__ == '__main__':
    main()
