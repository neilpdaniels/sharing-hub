from celery import shared_task
from django.core.mail import send_mail
import logging

logger = logging.getLogger(__name__)

@shared_task
def send_registration_verification_email(email, code, resume_link):
    """Send registration verification code email asynchronously."""
    send_mail(
        subject='Your rentalution verification code',
        message=(
            'Your rentalution registration code is: ' + code + '\n\n'
            'This code expires in 15 minutes.\n\n'
            'Resume verification: ' + resume_link
        ),
        from_email=None,
        recipient_list=[email],
        fail_silently=False,
    )


@shared_task
def process_profile_image(profile_id):
    """
    Async task to process and resize profile images.
    Handles RGBA conversion, resizing, and JPEG compression.
    """
    from account.models import Profile
    from PIL import Image
    from io import BytesIO
    from django.core.files.uploadedfile import InMemoryUploadedFile
    import sys
    
    try:
        profile = Profile.objects.get(id=profile_id)
        
        if not profile.image:
            logger.warning(f'Profile {profile_id} has no image to process')
            return
        
        # Open the image
        im = Image.open(profile.image)
        output = BytesIO()
        fill_color = 'white'
        
        # Convert RGBA to RGB
        if im.mode in ('RGBA', 'LA'):
            background = Image.new(im.mode[:-1], im.size, fill_color)
            background.paste(im, im.split()[-1])
            im = background
        
        # Resize if too large (profile photos: max 800x600)
        max_h = 800
        if im.size[0] > max_h:
            ratio = im.size[0] / max_h
            v_height = im.size[1] / ratio
            im = im.resize((max_h, int(v_height)))
        
        max_v = 600
        if im.size[1] > max_v:
            ratio = im.size[1] / max_v
            h_height = im.size[0] / ratio
            im = im.resize((int(h_height), max_v))
        
        # Save as JPEG
        im.save(output, format='JPEG', quality=100)
        output.seek(0)
        
        # Update the image field
        filename = f"{profile.image.name.split('.')[0]}.jpg"
        profile.image = InMemoryUploadedFile(
            output, 'ImageField', filename, 'image/jpeg', sys.getsizeof(output), None
        )
        
        # Save without triggering image processing again
        profile._skip_image_processing = True
        profile.save()
        
        logger.info(f'Successfully processed profile image for profile {profile_id}')
    except Profile.DoesNotExist:
        logger.error(f'Profile {profile_id} not found')
    except Exception as e:
        logger.exception(f'Error processing profile image {profile_id}: {str(e)}')

@shared_task
def send_random_mail():
    message = 'blah'
    subject = 'blah'
    mail_sent = send_mail(subject,
                        message,
                        'admin@rentalution.com',
                        ['testuser@rentalution.com'])
    return mail_sent