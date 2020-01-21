from django.core.management.base import BaseCommand
from smart_emails.suggestions import *


class Command(BaseCommand):
    '''send monthly email suggestions to users based on favorites'''
    def handle(self, *args, **kwargs):
        Suggestion(30).send_suggestions()