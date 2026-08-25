"""Custom permissions for monitors app."""

from rest_framework.permissions import BasePermission


class IsOwner(BasePermission):
    """
    Object-level permission: only the owner can access.

    This is a defense-in-depth layer — get_queryset() already filters by owner.
    This catches edge cases (e.g., if someone bypasses the queryset filter).

    Returns 404 behavior is achieved by the queryset filter returning empty,
    causing get_object() to raise Http404 before this permission is even checked.
    """

    def has_object_permission(self, request, view, obj):
        return obj.owner == request.user
