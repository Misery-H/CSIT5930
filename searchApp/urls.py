# -*- coding:utf-8 -*-　
# Last modify: Liu Wentao
# Description: Skeleton for fine-tuning with SemEval data on track A
# Note:

from django.urls import path

from . import views

urlpatterns = [
    # ex: /polls/
    path("", views.search_page, name="search_page"),
    path('suggestions', views.search_suggestions, name='search_suggestions'),
    path('result/', views.search_results, name='search_results'),
    path('ai-analysis/', views.ai_analysis, name='ai_analysis'),
    path('pages/<int:page_number>/', views.pages, name='pages'),
    path('pages/', views.pages, {'page_number': 1}),  # 设置默认参数

]