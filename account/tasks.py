from celery import shared_task
import logging

from common.emails import send_branded_email
from common.failures import record_site_failure

logger = logging.getLogger(__name__)

@shared_task
def send_registration_verification_email(email, code, resume_link):
    """Send registration verification code email asynchronously."""
    try:
        send_branded_email(
            subject='Your rentalution verification code',
            recipient=email,
            heading='Finish setting up your account',
            intro=f'Use this verification code to continue: {code}. It expires in 15 minutes.',
            cta_label='Continue registration',
            cta_url=resume_link,
            steps=['Enter the six-digit code.', 'Add the details needed to use Rentalution.', 'You’ll be ready to borrow and list items.'],
        )
    except Exception as exc:
        record_site_failure(
            'Registration verification email failed',
            details=f'Failed to send registration verification email to {email}.',
            exception=exc,
            context={'email': email, 'resume_link': resume_link},
        )
        raise


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
    return send_branded_email(
        subject='Rentalution test email', recipient='testuser@rentalution.co.uk',
        heading='Your email design is working', intro='This is a test email from Rentalution.',
    )
