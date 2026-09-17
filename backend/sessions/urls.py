from django.urls import path

from .views import (
    AnswersView, BackView, CustomRequirementsView, GenerateView,
    SessionCollectionView, SessionDetailView, SpecificationView,
)

urlpatterns = [
    path("", SessionCollectionView.as_view()),
    path("<uuid:session_id>/", SessionDetailView.as_view()),
    path("<uuid:session_id>/answers/", AnswersView.as_view()),
    path("<uuid:session_id>/custom-requirements/", CustomRequirementsView.as_view()),
    path("<uuid:session_id>/spec/", SpecificationView.as_view()),
    path("<uuid:session_id>/back/", BackView.as_view()),
    path("<uuid:session_id>/generate/", GenerateView.as_view()),
]
