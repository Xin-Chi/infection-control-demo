from django.urls import path

from . import views

app_name = 'accounts'

urlpatterns = [
    path('', views.index, name='index'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register, name='register'),

    path('admin-console/', views.auth_control, name='auth_control'),
    path('admin-console/users/', views.user_list, name='user_list'),
    path('admin-console/user/', views.user_detail, name='user_detail'),
    path('admin-console/topics/', views.topic_list, name='topic_list'),
    path('admin-console/toggle-section/', views.toggle_section, name='toggle_section'),
    path('admin-console/toggle-topic/', views.toggle_topic, name='toggle_topic'),
    path('admin-console/toggle-flag/', views.toggle_flag, name='toggle_flag'),
]
