from django.urls import path
from . import views

urlpatterns = [
    path('', views.home),
    path('api-info', views.api_info),
    path('register', views.register),
    path('check-eligibility', views.check_eligibility),
    path('create-loan', views.create_loan),
    path('view-loan/<int:loan_id>', views.view_loan),
    path('view-loans/<int:customer_id>', views.view_loans),
    path('view-customer/<int:customer_id>', views.view_customer),
]
