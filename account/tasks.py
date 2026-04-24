from celery import shared_task
from django.core.mail import send_mail

@shared_task
def send_random_mail():
    message = 'blah'
    subject = 'blah'
    mail_sent = send_mail(subject,
                        message,
                        'admin@sharing-hub.com',
                        ['testuser@sharing-hub.com'])
    return mail_sent