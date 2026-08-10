from django.urls import path

from . import views

app_name = 'infection'

urlpatterns = [
    path('search/', views.search, name='search'),
    path('search/filters/', views.search_filters, name='search_filters'),
    path('search/patients/', views.patient_list, name='patient_list'),
    path('search/timeline/', views.patient_timeline, name='patient_timeline'),
    path('search/report/', views.event_report, name='event_report'),
    path('search/vitals/', views.vital_chart, name='vital_chart'),

    path('categorize/', views.categorize, name='categorize'),
    path('categorize/categories/', views.category_list, name='category_list'),
    path('categorize/tokens/', views.token_pool, name='token_pool'),
    path('categorize/review/', views.review_tokens, name='review_tokens'),
    path('categorize/conversion-categories/', views.conversion_categories,
         name='conversion_categories'),
    path('categorize/conversion-tokens/', views.conversion_tokens,
         name='conversion_tokens'),
    path('categorize/add/', views.add_to_conversion, name='add_to_conversion'),
    path('categorize/remove/', views.remove_from_conversion,
         name='remove_from_conversion'),

    path('tube/<str:variant>/', views.tube_mapping, name='tube_mapping'),
    path('tube/<str:variant>/data/', views.tube_data, name='tube_data'),
    path('tube/<str:variant>/map/', views.tube_map, name='tube_map'),
]
