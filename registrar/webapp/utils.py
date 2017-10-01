import base64
import json
import logging

import io
import random
import string
import time

import requests
from PIL import Image
from captcha_solver import CaptchaSolver
from django.conf import settings
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException

from webapp.models import AvitoUser, YaMail

logger = logging.getLogger(__name__)


class PhoneAPI(object):
    api_key = settings.PHONE_API_KEY
    url = 'https://smslike.ru/api/stubs/handler_api.php'

    def send_request(self, action, data={}):
        data.update({
            'api_key': self.api_key,
            'service': 'av',
            'action': action
        })

        return requests.get(self.url, params=data).text

    def get_number(self):
        """
        получение временного номера
        :return: номер телефона
        """
        response = self.send_request('getNumber')
        success, data = self.clean(response, 'ACCESS_NUMBER')

        if not success:
            raise Exception(data)

        return data

    def get_status(self, phone_id):
        """
        получение статуса активации телефона
        :param phone_id: id телефона
        :return: код подтверждения
        """
        response = self.send_request('getStatus', {
            'id': phone_id
        })
        success, data = self.clean(response, 'STATUS_OK')

        if success:
            return data

        raise Exception(data)

    def clean(self, response, success):
        response = response.replace('"', '').split(':')

        if response[0] == success and len(response) > 1:
            return True, response[1:]

        return False, response[0]


class YandexMailApi(object):
    api_url = 'https://pddimp.yandex.ru/api2/admin/'

    def __init__(self):
        self.headers = {'PddToken': settings.YANDEX_TOKEN}
        self.domain = settings.YANDEX_DOMAIN

    def send_request(self, method, type='email', values=None):
        if not values:
            values = {}

        values.update({'domain': self.domain})
        request_url = '/'.join([self.api_url, type, method])
        post_methods = ['add', 'del', 'edit']
        get_methods = ['list?', 'ml/list?', 'ml/subscribers?']

        if method in post_methods:
            response = requests.post(request_url, data=values, headers=self.headers)

        elif method in get_methods:
            response = requests.get(request_url, data=values, headers=self.headers)

        else:
            raise Exception("NotMethodName: ".format(method))

        return json.loads(response.text)

    def create_mail(self, password):
        """
        Создание ящика
        :param password: пароль пользователя
        :return:
        """
        # values = {'login': login, 'password': password}
        # response = self.send_request('add', values=values)
        # print(response)
        ya_mail = YaMail.objects.last()
        index = ya_mail.index + 1 if ya_mail else 1
        email = f'opt-{index}@{self.domain}'
        YaMail.objects.create(index=index, email=email)
        return email


def captcha_solver(data):
    solver = CaptchaSolver('antigate', api_key=settings.ANTICAPTCHA_KEY)
    return solver.solve_captcha(data)


class Avito(object):
    phone_id = None
    verify_attempt = 0

    def __init__(self):
        self.driver = webdriver.Chrome()
        self.driver.set_window_size(1050, 1050)
        self.phone = PhoneAPI()

    def generate_password(self):
        """
        генерация пароля включающего цифры и буквы
        :return: пароль
        """
        chars = string.digits + string.ascii_letters
        password = ''.join(random.choice(chars) for _ in range(10))

        if password.isalpha() or password.isnumeric():
            return self.generate_password()

        return password

    def generate_email(self):
        """
        создание доменной почты
        :return: почта
        """
        ya_mail = YandexMailApi()
        return ya_mail.create_mail(self.generate_password())

    def set_value(self, name, value):
        """
        установка значения для поля ввода
        :param name: наименование
        :param value: значение, которое будет установленно
        :return: поле ввода
        """
        field = self.driver.find_element_by_name(name)
        field.clear()
        field.send_keys(value)
        return field

    def signup(self, name, email='', number='', password=''):
        """
        регистрация аккаунта
        :param name: имя
        :param email: почта
        :param number: номер телефона
        :param password: пароль
        :return: AvitoUser
        """
        self.driver.get('https://www.avito.ru/registration')

        if not number or not self.phone_id:
            self.phone_id, number = self.phone.get_number()
            number = number[1:]

        password = password or self.generate_password()
        email = email or self.generate_email()
        captcha = self.captcha_resolve()

        self.set_value('name', name)
        self.set_value('email', email)
        self.set_value('phone', number)
        self.set_value('password', password)
        self.set_value('captcha', captcha)
        button = self.driver.find_element_by_xpath("//button[@type='submit']")
        self.driver.execute_script('arguments[0].click();', button)

        user = None

        # Если форма отправлена успешно, то переход на шаг подтверждения телефона
        # иначе, смотрим ошибки email, phone или captcha, а затем снова заполняем и отправляем
        if self.driver.current_url.startswith('https://www.avito.ru/registration/verify'):
            if self.verify():
                user = AvitoUser.objects.create(login=email, email=name, phone=number, password=password)
            else:
                logger.warning('Phone is not verified')
        else:
            data = {
                'name': name,
                'password': password
            }
            try:
                self.driver.find_element_by_xpath("//div[contains(@class, 'is-error')]/input[@name='email']")
            except NoSuchElementException:
                data['email'] = email

            try:
                self.driver.find_element_by_xpath("//div[contains(@class, 'is-error')]/input[@name='phone']")
            except NoSuchElementException:
                data['number'] = number

            return self.signup(**data)

        self.driver.close()
        return user

    def captcha_resolve(self):
        """
        Вырезается капча из скриншота и отправляется на сервис anti-captcha.com
        :return: код подтверждения
        """
        captcha = self.driver.find_element_by_xpath("//img[@class='form-captcha-image js-form-captcha-image']")
        left, top = captcha.location.values()
        window_size = self.driver.get_window_size()
        captcha_size = captcha.size

        data = self.driver.get_screenshot_as_base64()
        data = base64.b64decode(data)
        im = Image.open(io.BytesIO(data))
        width, height = im.size

        # 114 пикселей погрешность в скриншоте за счет надписи:
        # "Chrome is being controlled by automated test software."
        w, h = window_size['width'], window_size['height'] - 114

        # получение координат капчи в процентном соотношении от размера браузера к размеру картинки
        left = left / w * width
        top = top / h * height
        right = left + captcha_size['width'] / w * width
        bottom = top + captcha_size['height'] / h * height

        im = im.crop((left, top, right, bottom))

        image = io.BytesIO()
        im.save(image, format='PNG')
        image = image.getvalue()
        return captcha_solver(image)

    def resend_confirmation_code(self):
        try:
            self.driver.find_element_by_xpath(
                "//button[@class='button button-azure js-phone-checker-request-code full']").click()
        except NoSuchElementException:
            pass

    def verify(self):
        """
        Подтверждение кода активации телефона
        36 попыток запроса статуса с интервалом 5 секунд, затем переотправка кода
        6 попыток переотправки кода, т.к. время действия телефона 20 минут (рекурсионно)
        36 * 5 * 6 == 18 минут
        :return: код подтверждения
        """
        self.verify_attempt += 1
        self.driver.find_element_by_class_name('button-azure-text').click()
        code = None

        for i in range(36):
            try:
                code = self.phone.get_status(self.phone_id)
                break
            except Exception as e:
                if str(e) == 'STATUS_WAIT_CODE':
                    time.sleep(5)

                else:
                    logger.warning(e)
                    return False

        if code is None:
            if self.verify_attempt > 6:
                self.verify_attempt = 0
                return

            self.resend_confirmation_code()
            self.verify()

        self.driver.find_element_by_name('code').send_keys(code)
        self.driver.find_element_by_class_name('js-registration-form-submit').click()
        return code
