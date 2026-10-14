from rest_framework.test import APITestCase

from accounts.models import User

from .models import Section, SectionAssignment


class SectionApiTestCase(APITestCase):
    """Shared setup: two editors, two writers, two sections."""

    def setUp(self):
        self.editor = User.objects.create_user(
            email="editor@example.com", password="x", full_name="Asha Editor", role=User.Role.EDITOR
        )
        self.other_editor = User.objects.create_user(
            email="editor2@example.com", password="x", full_name="Bina Editor", role=User.Role.EDITOR
        )
        self.writer = User.objects.create_user(
            email="writer@example.com", password="x", full_name="Chirag Writer", role=User.Role.WRITER
        )
        self.other_writer = User.objects.create_user(
            email="writer2@example.com", password="x", full_name="Divya Writer", role=User.Role.WRITER
        )
        self.tech = Section.objects.create(name="Tech", description="Gadgets", owner=self.editor)
        self.politics = Section.objects.create(name="Politics", owner=self.editor)
        SectionAssignment.objects.create(section=self.tech, writer=self.writer, assigned_by=self.editor)

    def as_user(self, user):
        self.client.force_authenticate(user=user)

    def names(self, response):
        result = []
        for item in response.data:
            result.append(item["name"])
        return result


class VisibilityTests(SectionApiTestCase):
    def test_editor_sees_all_active_sections(self):
        self.as_user(self.editor)
        response = self.client.get("/api/sections/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.names(response), ["Politics", "Tech"])

    def test_writer_sees_only_assigned_sections(self):
        self.as_user(self.writer)
        response = self.client.get("/api/sections/")
        self.assertEqual(self.names(response), ["Tech"])

    def test_writer_with_no_assignments_sees_nothing(self):
        self.as_user(self.other_writer)
        response = self.client.get("/api/sections/")
        self.assertEqual(response.data, [])

    def test_writer_cannot_open_unassigned_section(self):
        self.as_user(self.writer)
        response = self.client.get("/api/sections/" + str(self.politics.id) + "/")
        self.assertEqual(response.status_code, 404)

    def test_writer_can_open_assigned_section_with_writer_list(self):
        self.as_user(self.writer)
        response = self.client.get("/api/sections/" + str(self.tech.id) + "/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["writers"][0]["email"], "writer@example.com")

    def test_writer_count_counts_all_writers_not_just_me(self):
        SectionAssignment.objects.create(section=self.tech, writer=self.other_writer, assigned_by=self.editor)
        self.as_user(self.writer)
        response = self.client.get("/api/sections/")
        self.assertEqual(response.data[0]["writer_count"], 2)

    def test_login_required(self):
        response = self.client.get("/api/sections/")
        self.assertEqual(response.status_code, 401)


class CreateAndEditTests(SectionApiTestCase):
    def test_editor_creates_section(self):
        self.as_user(self.editor)
        response = self.client.post(
            "/api/sections/",
            {"name": "Culture", "description": "Arts", "owner_id": self.other_editor.id},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["owner"]["email"], "editor2@example.com")
        self.assertEqual(response.data["writer_count"], 0)

    def test_writer_cannot_create_section(self):
        self.as_user(self.writer)
        response = self.client.post("/api/sections/", {"name": "Sport", "owner_id": self.editor.id}, format="json")
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Section.objects.filter(name="Sport").exists())

    def test_owner_must_be_an_editor(self):
        self.as_user(self.editor)
        response = self.client.post("/api/sections/", {"name": "Sport", "owner_id": self.writer.id}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("owner_id", response.data)

    def test_name_is_unique_ignoring_case(self):
        self.as_user(self.editor)
        response = self.client.post("/api/sections/", {"name": "tech", "owner_id": self.editor.id}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("name", response.data)

    def test_editor_edits_section(self):
        self.as_user(self.editor)
        url = "/api/sections/" + str(self.tech.id) + "/"
        response = self.client.patch(url, {"description": "Gadgets and AI", "owner_id": self.other_editor.id}, format="json")
        self.assertEqual(response.status_code, 200)
        self.tech.refresh_from_db()
        self.assertEqual(self.tech.description, "Gadgets and AI")
        self.assertEqual(self.tech.owner, self.other_editor)

    def test_renaming_to_own_name_is_allowed(self):
        self.as_user(self.editor)
        response = self.client.patch("/api/sections/" + str(self.tech.id) + "/", {"name": "Tech"}, format="json")
        self.assertEqual(response.status_code, 200)

    def test_writer_cannot_edit_even_assigned_section(self):
        self.as_user(self.writer)
        response = self.client.patch("/api/sections/" + str(self.tech.id) + "/", {"name": "Hacked"}, format="json")
        self.assertEqual(response.status_code, 403)

    def test_sections_cannot_be_deleted(self):
        self.as_user(self.editor)
        response = self.client.delete("/api/sections/" + str(self.tech.id) + "/")
        self.assertEqual(response.status_code, 405)
        self.assertTrue(Section.objects.filter(pk=self.tech.pk).exists())


class ArchiveTests(SectionApiTestCase):
    def archive(self, section):
        return self.client.post("/api/sections/" + str(section.id) + "/archive/")

    def test_archive_hides_section_but_keeps_data(self):
        self.as_user(self.editor)
        response = self.archive(self.tech)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["is_archived"])

        listed = self.client.get("/api/sections/")
        self.assertEqual(self.names(listed), ["Politics"])
        # Still in the database with its assignment.
        self.assertTrue(SectionAssignment.objects.filter(section=self.tech).exists())

    def test_editor_can_list_archived_sections(self):
        self.as_user(self.editor)
        self.archive(self.tech)
        response = self.client.get("/api/sections/?archived=true")
        self.assertEqual(self.names(response), ["Tech"])

    def test_writer_never_sees_archived_sections(self):
        self.as_user(self.editor)
        self.archive(self.tech)
        self.as_user(self.writer)
        self.assertEqual(self.client.get("/api/sections/?archived=true").data, [])
        self.assertEqual(self.client.get("/api/sections/" + str(self.tech.id) + "/").status_code, 404)

    def test_archive_twice_is_rejected_with_reason(self):
        self.as_user(self.editor)
        self.archive(self.tech)
        response = self.archive(self.tech)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "This section is already archived.")

    def test_restore_brings_section_back(self):
        self.as_user(self.editor)
        self.archive(self.tech)
        response = self.client.post("/api/sections/" + str(self.tech.id) + "/restore/")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["is_archived"])
        self.assertIsNone(response.data["archived_at"])
        self.assertEqual(self.names(self.client.get("/api/sections/")), ["Politics", "Tech"])

    def test_restore_active_section_is_rejected(self):
        self.as_user(self.editor)
        response = self.client.post("/api/sections/" + str(self.tech.id) + "/restore/")
        self.assertEqual(response.status_code, 400)

    def test_writer_cannot_archive(self):
        self.as_user(self.writer)
        response = self.archive(self.tech)
        self.assertEqual(response.status_code, 403)
        self.tech.refresh_from_db()
        self.assertFalse(self.tech.is_archived)


class AssignmentTests(SectionApiTestCase):
    def assign(self, section, user):
        return self.client.post(
            "/api/sections/" + str(section.id) + "/writers/", {"writer_id": user.id}, format="json"
        )

    def remove(self, section, user):
        return self.client.delete("/api/sections/" + str(section.id) + "/writers/" + str(user.id) + "/")

    def test_editor_assigns_writer_and_writer_then_sees_section(self):
        self.as_user(self.editor)
        response = self.assign(self.politics, self.writer)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["writer_count"], 1)

        assignment = SectionAssignment.objects.get(section=self.politics, writer=self.writer)
        self.assertEqual(assignment.assigned_by, self.editor)

        self.as_user(self.writer)
        self.assertEqual(self.names(self.client.get("/api/sections/")), ["Politics", "Tech"])

    def test_writer_can_be_in_many_sections_and_section_has_many_writers(self):
        self.as_user(self.editor)
        self.assign(self.politics, self.writer)
        self.assign(self.tech, self.other_writer)
        self.assertEqual(SectionAssignment.objects.filter(writer=self.writer).count(), 2)
        self.assertEqual(SectionAssignment.objects.filter(section=self.tech).count(), 2)

    def test_cannot_assign_an_editor(self):
        self.as_user(self.editor)
        response = self.assign(self.tech, self.other_editor)
        self.assertEqual(response.status_code, 400)

    def test_cannot_assign_twice(self):
        self.as_user(self.editor)
        response = self.assign(self.tech, self.writer)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "This writer is already assigned to this section.")

    def test_cannot_change_writers_of_archived_section(self):
        self.as_user(self.editor)
        self.client.post("/api/sections/" + str(self.tech.id) + "/archive/")
        self.assertEqual(self.assign(self.tech, self.other_writer).status_code, 400)
        self.assertEqual(self.remove(self.tech, self.writer).status_code, 400)

    def test_editor_removes_writer(self):
        self.as_user(self.editor)
        response = self.remove(self.tech, self.writer)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["writers"], [])

        self.as_user(self.writer)
        self.assertEqual(self.client.get("/api/sections/").data, [])

    def test_removing_unassigned_writer_is_404(self):
        self.as_user(self.editor)
        response = self.remove(self.politics, self.writer)
        self.assertEqual(response.status_code, 404)

    def test_writer_cannot_assign_or_remove(self):
        self.as_user(self.writer)
        self.assertEqual(self.assign(self.tech, self.other_writer).status_code, 403)
        self.assertEqual(self.remove(self.tech, self.writer).status_code, 403)
        self.assertTrue(SectionAssignment.objects.filter(section=self.tech, writer=self.writer).exists())

    def test_editor_list_is_editor_only(self):
        self.as_user(self.writer)
        self.assertEqual(self.client.get("/api/auth/editors/").status_code, 403)
        self.as_user(self.editor)
        self.assertEqual(len(self.client.get("/api/auth/editors/").data), 2)
