import pytest

from pharmacy_desktop.core.errors import AuthError, ValidationError


def test_first_run_creates_an_owner_account_that_must_change_its_password(app):
    user = app.auth.current_user
    assert user.username == "admin"
    assert user.role == "admin"
    assert user.must_change_password


def test_wrong_password_is_refused(app):
    with pytest.raises(AuthError):
        app.auth.login("admin", "wrong")


def test_disabled_user_cannot_sign_in(app):
    user_id = app.auth.create_user("saleem", "Saleem Akhtar", "counter1", "cashier")
    app.auth.set_active(user_id, False)
    with pytest.raises(AuthError):
        app.auth.login("saleem", "counter1")


def test_roles_gate_what_each_person_can_do(app):
    app.auth.create_user("saleem", "Saleem Akhtar", "counter1", "cashier")
    app.auth.logout()
    cashier = app.auth.login("saleem", "counter1")
    assert cashier.can("pos.sell")
    assert not cashier.can("reports.view")
    assert not cashier.can("users.manage")
    with pytest.raises(AuthError):
        app.auth.require("settings.manage")


def test_the_last_administrator_cannot_be_locked_out(app):
    admin_id = app.auth.current_user.id
    with pytest.raises(ValidationError):
        app.auth.update_user(admin_id, role="cashier")
    with pytest.raises(ValidationError):
        app.auth.set_active(admin_id, False)


def test_duplicate_usernames_are_refused(app):
    app.auth.create_user("saleem", "Saleem", "counter1", "cashier")
    with pytest.raises(ValidationError):
        app.auth.create_user("SALEEM", "Someone else", "counter2", "cashier")
