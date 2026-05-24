"""Tests pour _get_gmail_service() — chemin env vars (headless) et fallback token.json."""

from unittest.mock import MagicMock, patch, mock_open


# ── chemin env vars (Cloud Run) ───────────────────────────────────────────────


def test_env_vars_path_builds_credentials_in_memory():
    """Quand les trois env vars sont présentes, credentials construites en mémoire (pas de lecture filesystem)."""
    import offerlens.notify.gmail as gmail_module

    mock_service = MagicMock()

    with (
        patch.object(
            gmail_module.settings,
            "gmail_refresh_token",
            "test-refresh-token",
            create=True,
        ),
        patch.object(
            gmail_module.settings,
            "gmail_client_id",
            "test-client-id",
            create=True,
        ),
        patch.object(
            gmail_module.settings,
            "gmail_client_secret",
            "test-client-secret",
            create=True,
        ),
        patch("offerlens.notify.gmail.Credentials") as mock_creds_cls,
        patch("offerlens.notify.gmail.Request"),
        patch("offerlens.notify.gmail.build", return_value=mock_service),
        # S'assurer qu'aucune lecture de fichier n'a lieu
        patch("builtins.open", side_effect=AssertionError("filesystem access detected")),
    ):
        mock_creds_instance = MagicMock()
        mock_creds_cls.return_value = mock_creds_instance

        result = gmail_module._get_gmail_service()

    # Credentials construites avec les bonnes valeurs
    mock_creds_cls.assert_called_once_with(
        token=None,
        refresh_token="test-refresh-token",
        token_uri="https://oauth2.googleapis.com/token",
        client_id="test-client-id",
        client_secret="test-client-secret",
        scopes=gmail_module._SCOPES,
    )
    # refresh() appelé pour obtenir un access_token
    mock_creds_instance.refresh.assert_called_once()
    # Le service Gmail est construit et retourné
    assert result is mock_service


def test_env_vars_path_does_not_read_token_json(tmp_path):
    """Le chemin env vars ne lit pas token.json même s'il existe."""
    import offerlens.notify.gmail as gmail_module

    token_file = tmp_path / "token.json"
    token_file.write_text('{"dummy": true}')
    read_calls = []

    original_open = open

    def tracked_open(path, *args, **kwargs):
        read_calls.append(str(path))
        return original_open(path, *args, **kwargs)

    with (
        patch.object(gmail_module.settings, "gmail_refresh_token", "rt"),
        patch.object(gmail_module.settings, "gmail_client_id", "cid"),
        patch.object(gmail_module.settings, "gmail_client_secret", "csec"),
        patch("offerlens.notify.gmail.Credentials") as mock_creds_cls,
        patch("offerlens.notify.gmail.Request"),
        patch("offerlens.notify.gmail.build"),
    ):
        mock_creds_cls.return_value = MagicMock()
        gmail_module._get_gmail_service()

    # Credentials.from_authorized_user_file n'est pas appelé
    assert not mock_creds_cls.from_authorized_user_file.called


# ── chemin fallback token.json (local dev) ────────────────────────────────────


def test_fallback_uses_token_json_when_env_vars_absent():
    """Quand les env vars sont vides, _get_gmail_service() utilise token.json."""
    import offerlens.notify.gmail as gmail_module

    mock_service = MagicMock()
    mock_creds = MagicMock()
    mock_creds.valid = True

    with (
        patch.object(gmail_module.settings, "gmail_refresh_token", ""),
        patch.object(gmail_module.settings, "gmail_client_id", ""),
        patch.object(gmail_module.settings, "gmail_client_secret", ""),
        patch("offerlens.notify.gmail._TOKEN_FILE") as mock_token_file,
        patch("offerlens.notify.gmail.Credentials") as mock_creds_cls,
        patch("offerlens.notify.gmail.build", return_value=mock_service),
    ):
        mock_token_file.exists.return_value = True
        mock_creds_cls.from_authorized_user_file.return_value = mock_creds

        result = gmail_module._get_gmail_service()

    # from_authorized_user_file utilisé pour lire token.json
    mock_creds_cls.from_authorized_user_file.assert_called_once()
    assert result is mock_service


def test_fallback_runs_interactive_flow_when_no_token_json():
    """Sans env vars et sans token.json, le flow interactif OAuth2 est déclenché."""
    import offerlens.notify.gmail as gmail_module

    mock_service = MagicMock()
    mock_creds = MagicMock()
    mock_flow = MagicMock()
    mock_flow.run_local_server.return_value = mock_creds
    mock_creds.to_json.return_value = "{}"

    with (
        patch.object(gmail_module.settings, "gmail_refresh_token", ""),
        patch.object(gmail_module.settings, "gmail_client_id", ""),
        patch.object(gmail_module.settings, "gmail_client_secret", ""),
        patch("offerlens.notify.gmail._TOKEN_FILE") as mock_token_file,
        patch("offerlens.notify.gmail.InstalledAppFlow") as mock_flow_cls,
        patch("offerlens.notify.gmail.Credentials") as mock_creds_cls,
        patch("offerlens.notify.gmail.build", return_value=mock_service),
    ):
        mock_token_file.exists.return_value = False
        mock_flow_cls.from_client_secrets_file.return_value = mock_flow

        result = gmail_module._get_gmail_service()

    mock_flow_cls.from_client_secrets_file.assert_called_once()
    mock_flow.run_local_server.assert_called_once_with(port=0)
    assert result is mock_service
