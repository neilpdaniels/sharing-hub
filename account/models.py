from django.db import models
from django.conf import settings
from .validators import MinAgeValidator
from common.helpers import RandomFileName 
from PIL import Image
from io import BytesIO
from django.core.files.uploadedfile import InMemoryUploadedFile
import sys
from django.contrib.auth.models import User, models
from django.core.validators import MaxValueValidator, MinValueValidator

# make email address unique
User._meta.get_field('email').__dict__['_unique'] = True

class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL,
                                on_delete=models.CASCADE)
    email_confirmed = models.BooleanField(default=False)
    date_of_birth = models.DateField(validators=[MinAgeValidator])
    address_line_1 = models.CharField(max_length=255)
    address_line_2 = models.CharField(max_length=255, blank=True, null=True)
    town = models.CharField('Town/City', max_length=255)
    county = models.CharField(max_length=255, blank=True, null=True)
    postcode = models.CharField(max_length=8)
    
    # Cached GPS coordinates for postcode (to avoid repeated geocoding)
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text='Cached latitude from postcode lookup'
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text='Cached longitude from postcode lookup'
    )

    image = models.ImageField(upload_to=RandomFileName('users/'),
                            blank=True)
    user_rating = models.FloatField(default=0)
    user_successful_txns = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(999999)], default=0)
    user_failed_txns = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(999999)], default=0)
    create_date = models.DateTimeField('date created', auto_now_add=True)

    def __str__(self):
        return 'Profile for user {}'.format(self.user.username)

    def saveWithImage(self, *args, **kwargs):
        #Opening the uploaded image
        im = Image.open(self.image)
        output = BytesIO()
        fill_color = 'white'  # your background
        if im.mode in ('RGBA', 'LA'):
            background = Image.new(im.mode[:-1], im.size, fill_color)
            background.paste(im, im.split()[-1])
            im = background

        #Resize/modify the image
        max_h = 800
        if im.size[0] > max_h:
            ratio = im.size[0] / max_h
            v_height = im.size[1] / ratio
            im = im.resize( (max_h, int(v_height)) )
        max_v = 600
        if im.size[1] > max_v:
            ratio = im.size[1] / max_v
            h_height = im.size[0] / ratio
            im = im.resize( (int(h_height), max_v) )
		
        #after modifications, save it to the output
        im.save(output, format='JPEG', quality=100)
        output.seek(0)

        #change the imagefield value to be the newley modifed image value
        self.image = InMemoryUploadedFile(output,'ImageField', "%s.jpg" %self.image.name.split('.')[0], 'image/jpeg', sys.getsizeof(output), None)
        super(Profile, self).save(*args, **kwargs)