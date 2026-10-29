from backend.airroute import create_app


def test_factory_starts_without_loading_coursework_module(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'factory.db'}",
        }
    )

    assert "airroute_legacy_module" not in app.extensions
    assert any(rule.rule == "/travel-plans/export" for rule in app.url_map.iter_rules())
