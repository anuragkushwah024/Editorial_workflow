from rest_framework.permissions import BasePermission


class IsEditor(BasePermission):
    """Allows the request only if the logged-in user has the Editor role.

    This is the server-side check that backs goal 1: hiding a button in React
    is not enough, the API itself must refuse writers.
    """

    message = "Only editors can perform this action."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return user.is_editor
