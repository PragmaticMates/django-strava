from django.urls import path
from strava import views


app_name = 'strava'

urlpatterns = [
    path('',              views.dashboard,   name='dashboard'),
    path('activities/',   views.ActivitiesView.as_view(),  name='activities'),
    path('gear/',         views.GearView.as_view(),  name='gear'),
    path('gallery/',      views.GalleryView.as_view(),  name='gallery'),
]
