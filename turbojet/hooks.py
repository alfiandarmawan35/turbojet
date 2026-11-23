app_name = "turbojet"
app_title = "TurboJet"
app_publisher = "TurboJet"
app_description = "Template SaaS: akun, paket, kuota, pekerjaan latar belakang, dan engine Python/Rust"
app_license = "proprietary"

after_install = "turbojet.install.after_install"

scheduler_events = {
    "cron": {
        "* * * * *": [
            "turbojet.services.jobs.sweep",
        ],
    },
    "daily": [
        "turbojet.services.idempotency.purge_expired",
    ],
}
