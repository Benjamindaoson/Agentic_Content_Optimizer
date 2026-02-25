def test_router_not_imported_at_module_import_time():
    import app.main as main_mod

    state = main_mod.app.state.startup_state
    assert state.get("routers_loaded", []) == []
    assert state.get("routers_skipped", []) == []
