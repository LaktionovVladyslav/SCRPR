import datetime
from django.core.management.base import BaseCommand
from smart_emails.suggestions import *


class Command(BaseCommand):
    '''send weekly email suggestions to users based on favorites'''
    def handle(self, *args, **kwargs):
        if datetime.date.today().weekday() == 0:
            Suggestion(7).send_suggestions()
