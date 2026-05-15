"""Registration service layer for user account creation workflow."""

import logging
from datetime import timedelta
from random import randint

from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone

from account.avatar_presets import build_random_avatar_content, normalize_avatar_options
from account.models import RegistrationVerification
from common.phone_utils import normalize_to_domestic

logger = logging.getLogger(__name__)


class RegistrationService:
    """Service for handling user registration workflow."""

    @staticmethod
    def generate_unique_verification_code(max_attempts=20):
        """
        Generate a unique 6-digit verification code.

        Args:
            max_attempts (int): Maximum attempts to generate unique code

        Returns:
            str: A 6-digit verification code

        Raises:
            ValueError: If cannot generate unique code after max attempts
        """
        for _ in range(max_attempts):
            code = f"{randint(0, 999999):06d}"
            if not RegistrationVerification.objects.filter(verification_code=code).exists():
                return code
        raise ValueError('Could not generate a unique verification code.')

    @staticmethod
    def get_pending_verification(email):
        """
        Get the most recent pending verification record for an email.

        Args:
            email (str): Email address to look up

        Returns:
            RegistrationVerification or None: The verification record or None if not found
        """
        return RegistrationVerification.objects.filter(
            email__iexact=email,
            is_used=False,
        ).order_by('-created_at').first()

    @staticmethod
    def build_avatar_from_form(form_data):
        """
        Extract and normalize avatar data from registration form.

        Args:
            form_data (dict): Cleaned form data containing avatar fields

        Returns:
            dict: Normalized avatar parameters and content file
        """
        avatar_seed = (form_data.get('avatar_preset') or '').strip() or form_data['username']
        avatar_style = 'avataaars'
        avatar_hair_color = (form_data.get('avatar_hair_color') or '').strip()
        avatar_gender_vibe = 'neutral'
        avatar_hair_length = (form_data.get('avatar_hair_length') or 'short').strip()
        avatar_glasses = bool(form_data.get('avatar_glasses'))
        avatar_facial_hair = int(form_data.get('avatar_facial_hair') or 25)
        avatar_facial_hair_color = (form_data.get('avatar_facial_hair_color') or '').strip()
        avatar_clothes_color = (form_data.get('avatar_clothes_color') or '').strip()
        avatar_accessories_color = (form_data.get('avatar_accessories_color') or '').strip()
        avatar_skin_tone = str(form_data.get('avatar_skin_tone') or '4').strip()
        avatar_eyes = (form_data.get('avatar_eyes') or 'default').strip()
        avatar_mouth = (form_data.get('avatar_mouth') or 'smile').strip()
        avatar_clothing = (form_data.get('avatar_clothing') or 'hoodie').strip()
        avatar_accessories = (form_data.get('avatar_accessories') or 'round').strip()

        # Normalize avatar options
        (
            avatar_style,
            avatar_hair_color,
            avatar_gender_vibe,
            avatar_skin_tone,
            avatar_hair_length,
            avatar_glasses,
            avatar_facial_hair,
            avatar_facial_hair_color,
            avatar_eyes,
            avatar_mouth,
            avatar_clothing,
            avatar_accessories,
            avatar_clothes_color,
            avatar_accessories_color,
        ) = normalize_avatar_options(
            avatar_style,
            avatar_hair_color,
            avatar_gender_vibe,
            avatar_skin_tone,
            avatar_hair_length,
            avatar_glasses,
            avatar_facial_hair,
            avatar_facial_hair_color,
            avatar_eyes,
            avatar_mouth,
            avatar_clothing,
            avatar_accessories,
            avatar_clothes_color,
            avatar_accessories_color,
        )

        # Generate avatar content
        avatar_content = build_random_avatar_content(
            seed=avatar_seed,
            style=avatar_style,
            hair_color=avatar_hair_color,
            gender_vibe=avatar_gender_vibe,
            skin_tone_level=avatar_skin_tone,
            hair_length=avatar_hair_length,
            glasses=avatar_glasses,
            facial_hair_level=avatar_facial_hair,
            facial_hair_color=avatar_facial_hair_color,
            eyes=avatar_eyes,
            mouth=avatar_mouth,
            clothing=avatar_clothing,
            accessories=avatar_accessories,
            clothes_color=avatar_clothes_color,
            accessories_color=avatar_accessories_color,
        )

        avatar_bytes = avatar_content.read()
        avatar_name = avatar_content.name

        return {
            'seed': avatar_seed,
            'style': avatar_style,
            'hair_color': avatar_hair_color,
            'gender_vibe': avatar_gender_vibe,
            'hair_length': avatar_hair_length,
            'glasses': avatar_glasses,
            'facial_hair': avatar_facial_hair,
            'facial_hair_color': avatar_facial_hair_color,
            'skin_tone': avatar_skin_tone,
            'eyes': avatar_eyes,
            'mouth': avatar_mouth,
            'clothing': avatar_clothing,
            'accessories': avatar_accessories,
            'clothes_color': avatar_clothes_color,
            'accessories_color': avatar_accessories_color,
            'content_file': ContentFile(avatar_bytes, name=avatar_name),
            'name': avatar_name,
        }

    @staticmethod
    def create_verification_record(email, form_data, avatar_data):
        """
        Create a new RegistrationVerification record.

        Args:
            email (str): Email address for verification
            form_data (dict): Cleaned form data
            avatar_data (dict): Avatar parameters and content file

        Returns:
            RegistrationVerification: The created verification record
        """
        # Delete any existing pending verification for this email
        RegistrationVerification.objects.filter(email__iexact=email, is_used=False).delete()

        code = RegistrationService.generate_unique_verification_code()

        return RegistrationVerification.objects.create(
            email=email,
            username=form_data['username'],
            first_name=form_data['first_name'],
            last_name=form_data['last_name'],
            date_of_birth=form_data['date_of_birth'],
            mobile_number=form_data['mobile_number'],
            house_name_number=form_data.get('house_name_number', ''),
            address_line_1=form_data['address_line_1'],
            address_line_2=form_data.get('address_line_2', ''),
            town=form_data['town'],
            county=form_data.get('county', ''),
            postcode=form_data['postcode'],
            image=avatar_data['content_file'],
            avatar_preset=avatar_data['seed'],
            avatar_style=avatar_data['style'],
            avatar_hair_color=avatar_data['hair_color'],
            avatar_gender_vibe=avatar_data['gender_vibe'],
            avatar_hair_length=avatar_data['hair_length'],
            avatar_glasses=avatar_data['glasses'],
            avatar_facial_hair=avatar_data['facial_hair'],
            avatar_facial_hair_color=avatar_data['facial_hair_color'],
            avatar_skin_tone=avatar_data['skin_tone'],
            avatar_eyes=avatar_data['eyes'],
            avatar_mouth=avatar_data['mouth'],
            avatar_clothing=avatar_data['clothing'],
            avatar_accessories=avatar_data['accessories'],
            avatar_clothes_color=avatar_data['clothes_color'],
            avatar_accessories_color=avatar_data['accessories_color'],
            generated_image=avatar_data['content_file'],
            verification_code=code,
            expires_at=timezone.now() + timedelta(minutes=15),
        )

    @staticmethod
    def resend_verification_code(verification_record):
        """
        Resend verification code for an existing verification record.

        Args:
            verification_record (RegistrationVerification): The verification record

        Returns:
            RegistrationVerification: Updated verification record with new code
        """
        code = RegistrationService.generate_unique_verification_code()

        # Delete old record and create new one with new code
        RegistrationVerification.objects.filter(
            email__iexact=verification_record.email,
            is_used=False
        ).delete()

        return RegistrationVerification.objects.create(
            email=verification_record.email,
            username=verification_record.username,
            first_name=verification_record.first_name,
            last_name=verification_record.last_name,
            date_of_birth=verification_record.date_of_birth,
            mobile_number=verification_record.mobile_number,
            house_name_number=verification_record.house_name_number,
            address_line_1=verification_record.address_line_1,
            address_line_2=verification_record.address_line_2,
            town=verification_record.town,
            county=verification_record.county,
            postcode=verification_record.postcode,
            image=verification_record.image,
            avatar_preset=verification_record.avatar_preset,
            avatar_style=verification_record.avatar_style,
            avatar_hair_color=verification_record.avatar_hair_color,
            avatar_gender_vibe=verification_record.avatar_gender_vibe,
            avatar_hair_length=verification_record.avatar_hair_length,
            avatar_glasses=verification_record.avatar_glasses,
            avatar_facial_hair=verification_record.avatar_facial_hair,
            avatar_facial_hair_color=verification_record.avatar_facial_hair_color,
            avatar_skin_tone=verification_record.avatar_skin_tone,
            avatar_eyes=verification_record.avatar_eyes,
            avatar_mouth=verification_record.avatar_mouth,
            avatar_clothing=verification_record.avatar_clothing,
            avatar_accessories=verification_record.avatar_accessories,
            avatar_clothes_color=verification_record.avatar_clothes_color,
            avatar_accessories_color=verification_record.avatar_accessories_color,
            generated_image=verification_record.generated_image,
            verification_code=code,
            expires_at=timezone.now() + timedelta(minutes=15),
        )

    @staticmethod
    def complete_registration(verification_record, password):
        """
        Complete user registration by creating User and Profile from verification record.

        Args:
            verification_record (RegistrationVerification): The completed verification record
            password (str): The new user's password

        Returns:
            tuple: (User, Profile) - The newly created user and profile

        Raises:
            ValueError: If email already exists or verification is invalid
        """
        email = verification_record.email

        # Check if user already exists
        if User.objects.filter(email__iexact=email).exists():
            raise ValueError(f'User with email {email} already exists.')

        # Create user
        new_user = User.objects.create(
            username=verification_record.username,
            email=email,
            first_name=verification_record.first_name,
            last_name=verification_record.last_name,
            is_active=True,
        )
        new_user.set_password(password)
        new_user.save()

        # Determine which image to use
        active_image = verification_record.generated_image or verification_record.image
        image_original = verification_record.image
        image_generated = verification_record.generated_image
        avatar_provider = 'dicebear:avataaars'

        # If no image and avatar preset exists, regenerate
        if not active_image and verification_record.avatar_preset:
            avatar_content = build_random_avatar_content(
                seed=verification_record.avatar_preset,
                style='avataaars',
                hair_color=verification_record.avatar_hair_color,
                gender_vibe=verification_record.avatar_gender_vibe,
                skin_tone_level=verification_record.avatar_skin_tone,
                hair_length=verification_record.avatar_hair_length,
                glasses=verification_record.avatar_glasses,
                facial_hair_level=verification_record.avatar_facial_hair,
                facial_hair_color=verification_record.avatar_facial_hair_color,
                eyes=verification_record.avatar_eyes,
                mouth=verification_record.avatar_mouth,
                clothing=verification_record.avatar_clothing,
                accessories=verification_record.avatar_accessories,
                clothes_color=verification_record.avatar_clothes_color,
                accessories_color=verification_record.avatar_accessories_color,
            )
            avatar_bytes = avatar_content.read()
            avatar_name = avatar_content.name
            active_image = ContentFile(avatar_bytes, name=avatar_name)
            image_original = ContentFile(avatar_bytes, name=avatar_name)

        # Create profile
        from account.models import Profile
        profile = Profile.objects.create(
            user=new_user,
            email_confirmed=True,
            date_of_birth=verification_record.date_of_birth,
            mobile_number=normalize_to_domestic(verification_record.mobile_number),
            address_line_1=verification_record.address_line_1,
            address_line_2=verification_record.address_line_2,
            town=verification_record.town,
            county=verification_record.county,
            postcode=verification_record.postcode,
            image_original=image_original,
            image_generated=image_generated,
            avatar_provider=avatar_provider,
            image=active_image,
        )

        if profile.image:
            profile.saveWithImage()

        # Mark verification as used
        verification_record.is_used = True
        verification_record.save(update_fields=['is_used', 'updated_at'])

        return new_user, profile
