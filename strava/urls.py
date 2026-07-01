from django.urls import path
from strava import views


app_name = 'strava'

urlpatterns = [
    path('',              views.DashboardView.as_view(),  name='dashboard'),
    path('refresh/',      views.RefreshView.as_view(),  name='refresh'),
    path('activity/<int:pk>/card/', views.ActivityCardView.as_view(),  name='activity_card'),
    path('activities/',   views.ActivitiesView.as_view(),  name='activities'),
    path('gear/',         views.GearView.as_view(),  name='gear'),
    path('gallery/',      views.GalleryView.as_view(),  name='gallery'),
    path('compare/',      views.CompareView.as_view(),  name='compare'),
]
