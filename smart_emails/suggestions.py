import sendgrid
from django.db.models import Q
from django.template.loader import get_template
from django.template import Context
from django.conf import settings
from django.forms.models import model_to_dict
from authentication.models import User
from scrpr.models import FavoriteJobQuery, FavoriteGameQuery
from .models import SavedSuggestion
from web_scraper.web_scraping.scrape_games import PSStoreScraper
from web_scraper.web_scraping.scrape_jobs import JobsSitesScraper


# workflow of cron job:
# For every User:
# 1. If User has notifications set up, and frequency is the same:
#     1. Form a query from notification parameters (limited by 10 results)
#     2. Check previous suggestions in SavedSuggestion model
#     3. If there are any of them of the same type:
#         1. Remode the doubling suggestions from the query
#            for every repeating suggestion already saved in database
#        Else:
#         1. Do nothing with query results, continue to the next step
#     4. If by this point any query results remaining:
#         1. Form a message to User email with query results
#            in respective template (template is chosen by suggestion type)
#         2. Send message to User
#         3. If there are already 5 suggestion packs from messages
#            saved in database:
#             1. Remove the oldest pack and save current query in the database
#            Else:
#             1. Just save the query in the database
#        Else:
#         1. Do nothing and switch to the next User


class Suggestion:
    MAX_SUGGESTIONS = 10

    def __init__(self, frequency_in_days):
        self.frequency_in_days = frequency_in_days

    @staticmethod
    def _get_saved_suggestions(user, type):
        suggestions = SavedSuggestion.objects.filter(
            account=user, type=type).order_by('-saved_datetime')
        if len(suggestions) > 50:
            for suggestion in suggestions[51:]:
                suggestion.delete()
        return suggestions[:50]

    @staticmethod
    def _remove_duplicates(new_list, old_list):
        old_list = [item.link for item in old_list]
        result = []
        for entry in new_list:
            if entry['link'] not in old_list:
                result.append(entry)
        return result

    @staticmethod
    def _get_email_context(suggestions, username, frequency):
        return {
            'object_list': suggestions,
            'username': username,
            'frequency': frequency,
        }

    @staticmethod
    def _save_new_suggestions(new_suggestions, type, user):
        new_entries = [
            SavedSuggestion(
                type=type,
                link=suggestion['link'],
                account=user
            ) for suggestion in new_suggestions
        ]
        SavedSuggestion.objects.bulk_create(new_entries)

    @staticmethod
    def _send_message(subject_filename, body_txt_filename,
                     body_html_filename, receiver_email, email_context):
        subject_template = get_template('smart_emails/' + subject_filename)
        text_email_template = get_template('smart_emails/' + body_txt_filename)
        html_email_template = get_template('smart_emails/' + body_html_filename)
        rendered_subject = subject_template.render().strip()
        txt_with_context = text_email_template.render(email_context)
        html_with_context = html_email_template.render(email_context)
        message = sendgrid.helpers.mail.Mail(
            from_email='bolotnikovprojects@gmail.com',
            to_emails=receiver_email,
            subject=rendered_subject,
            html_content=html_with_context,
        )
        sg_client = sendgrid.SendGridAPIClient(settings.EMAIL_HOST_PASSWORD)
        response = sg_client.send(message)

    def _get_job_favorites(self):
        return FavoriteJobQuery.objects.select_related('account'
            ).filter(notification_freq=self.frequency_in_days)

    def _get_game_favorites(self):
        return FavoriteGameQuery.objects.select_related('account'
            ).filter(notification_freq=self.frequency_in_days)

    def _get_filtered_suggestions(self, new_suggestions, user, type):
        prev_suggestions = self._get_saved_suggestions(user, type)
        return self._remove_duplicates(
            new_suggestions,
            prev_suggestions
        )[:self.MAX_SUGGESTIONS]

    def _get_game_suggestions_from_query(self, query_params):
        query_results = PSStoreScraper().scrape_game_website(
            query_params=query_params,
            page_num=1,
        )
        return query_results.get('object_list')

    def _get_job_suggestions_from_query(self, query_params):
        query_results = JobsSitesScraper().scrape_websites(
            location=query_params.get('city') if query_params else None,
            query_params=query_params,
            page_num=1,
        )
        return query_results.get('object_list')

    def _send_game_suggestions(self, game_favorites):
        for game_favorite in game_favorites:
            user = game_favorite.account
            game_favorite = model_to_dict(game_favorite)
            game_suggestions = self._get_game_suggestions_from_query(game_favorite)
            if game_suggestions:
                filtered_suggestions = self._get_filtered_suggestions(
                    game_suggestions, user, 'GAME')
                if filtered_suggestions:
                    email_context = self._get_email_context(
                        filtered_suggestions,
                        user.username,
                        self.frequency
                    )
                    self._send_message(
                        subject_filename='games_email_subject_template.txt',
                        body_txt_filename='games_email_body_template.txt',
                        body_html_filename='games_email_body_template.html',
                        receiver_email=user.email,
                        email_context=email_context
                    )
                    self._save_new_suggestions(filtered_suggestions, 'GAME', user)

    def _send_job_suggestions(self, job_favorites):
        for job_favorite in job_favorites:
            user = job_favorite.account
            job_favorite = model_to_dict(job_favorite)
            job_suggestions = self._get_job_suggestions_from_query(job_favorite)
            if job_suggestions:
                filtered_suggestions = self._get_filtered_suggestions(
                    job_suggestions, user, 'JOB')
                if filtered_suggestions:
                    email_context = self._get_email_context(
                        filtered_suggestions,
                        user.username,
                        self.frequency
                    )
                    self._send_message(
                        subject_filename='jobs_email_subject_template.txt',
                        body_txt_filename='jobs_email_body_template.txt',
                        body_html_filename='jobs_email_body_template.html',
                        receiver_email=user.email,
                        email_context=email_context
                    )
                    self._save_new_suggestions(filtered_suggestions, 'JOB', user)

    def send_suggestions(self):
        game_favorites = self._get_game_favorites()
        print(game_favorites)
        if game_favorites:
            self._send_game_suggestions(game_favorites)
        job_favorites = self._get_job_favorites()
        print(job_favorites)
        if job_favorites:
            self._send_job_suggestions(job_favorites)

    @property
    def frequency(self):
        from scrpr.constants import CHOICES_DICT
        return CHOICES_DICT[self.frequency_in_days]
