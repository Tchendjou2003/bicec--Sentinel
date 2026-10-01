import re

from locust import HttpUser, task, between


class AuditeurLocust(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        login_page = self.client.get("/auth/login/")
        csrf_token = re.search(
            r'name="csrfmiddlewaretoken" value="([^"]+)"', login_page.text
        ).group(1)
        self.client.post(
            "/auth/login/",
            data={
                "username": "locust.test",
                "password": "LocustTest2026!",
                "csrfmiddlewaretoken": csrf_token,
            },
            headers={"Referer": f"{self.host}/auth/login/"},
        )

    @task(3)
    def liste_recos(self):
        self.client.get("/audit/recommandations/")

    @task(2)
    def dashboard(self):
        self.client.get("/tableau-de-bord/")

    @task(1)
    def detail_reco(self):
        self.client.get("/audit/recommandations/c0410519-a22e-4f32-bb15-d64cdd9e5d7d/")
