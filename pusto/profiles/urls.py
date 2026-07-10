from django.urls import path
from .views import *

app_name = 'profiles'

urlpatterns = [
    path('MyProfile/', MyProfile, name='MyProfile'),
    path('MyProfile/edit/', MyProfileEdit, name='MyProfileEdit'),
    path('OtherProfile/<int:idProfile>/', otherProfile, name='otherProfile'),

    path('regenerate-tg-code/', regenerate_tg_code, name='regenerate_tg_code'),

    path('EmployerVerificationForm/', EmployerVerificationView, name='EmployerVerificationForm'),
    path('StudentVerificationForm/', StudentVerificationView, name='StudentVerificationForm'),
    path('UserVerificationForm/', UserVerificationView, name='UserVerificationForm'),
    path('delete/<str:post_type>/<int:post_id>/', delete_post, name='delete_post'),
    path('edit/<str:post_type>/<int:post_id>/', edit_post, name='edit_post'),
    path('claim-posts/', claim_posts_by_email, name='claim_posts_by_email'),

]