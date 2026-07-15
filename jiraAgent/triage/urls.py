from django.urls import path, include
from rest_framework.routers import DefaultRouter
from triage import views

router = DefaultRouter()

urlpatterns = [
    path('health-check/', views.HealthCheck.as_view()),
    path('jira-agent/', views.JiraAgentApiView.as_view()),
    path('confirmed-jira-action/', views.ConfirmedJiraAction.as_view()),
    # path('triage-jira-ticket/', views.TriageJiraTicket.as_view()),
    path('', include(router.urls))
]
