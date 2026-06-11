from django.urls import path
from strava import views


app_name = 'strava'

urlpatterns = [
    path('',              views.dashboard,   name='dashboard'),
    path('activities/',   views.activities,  name='activities'),
    path('gear/',         views.gear,        name='gear'),
    path('gallery/',      views.gallery,     name='gallery'),
]
