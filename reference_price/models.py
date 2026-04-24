from django.db import models
from simple_history.models import HistoricalRecords
from django.core.validators import MaxValueValidator, MinValueValidator
from django.template.defaultfilters import slugify

class ReferencePrice(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=250, blank=True )
    create_date = models.DateTimeField('date created', auto_now_add=True)
    price = models.FloatField(validators=[MinValueValidator(0), MaxValueValidator(999999)])
    gbp_price = models.FloatField(validators=[MinValueValidator(0), MaxValueValidator(999999)])
    currency = models.CharField(max_length=3, default='GBP')
    default_for_metal = models.SlugField(max_length=200, blank=True, null=True)
    
    # used for non GBP FX - links to FX ref px for GBP to listed ccy
    # gbp_fx_rate = models.ForeignKey(ReferencePrice, on_delete=models.CASCADE)
    
    primary_url = models.URLField()
    backup_url = models.URLField(blank=True, null=True)    
    history = HistoricalRecords()
    # need to think of a way of doing a schedule - would be nice to contain
    # in the model
    
    def save(self, *args, **kwargs):
        self.slug = slugify(self.title)
        super(ReferencePrice, self).save(*args, **kwargs)

        # update all orders that use this price with the new reference price
        # would this be better using signals?

    def __str__(self):
        return self.title
        
