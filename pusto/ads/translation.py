from modeltranslation.translator import register, TranslationOptions
from .models import Lifestyle


@register(Lifestyle)
class LifestyleTranslationOptions(TranslationOptions):
    fields = ('name',)

