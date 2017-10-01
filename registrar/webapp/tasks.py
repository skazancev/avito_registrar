from celery import shared_task
from webapp.utils import Avito


@shared_task
def auto_signup_accounts(data):
    for i in range(data['quantity']):
        registerer = Avito()
        registerer.signup(data['email'])
